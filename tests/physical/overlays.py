#!/usr/bin/env python3
"""Validate reviewed physical evidence and render one safe assignment-only overlay.

The repository intentionally contains no approved A1/D1 targets or sites.
Names, scope and legal sites must come from the user's exact 17.0.2 R0 build.
Human source correspondence is retained as a review, never inferred from ~NEW_REG.
"""
import csv
import hashlib
import json
from pathlib import Path
import re

from physical.control import digest, expected_build_id, load_registry, verify_version, write_json


def rows(path):
    with Path(path).open() as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def safe_path(root, rel):
    p = Path(rel)
    if p.is_absolute() or '..' in p.parts:
        raise ValueError('Unsafe evidence path: ' + rel)
    path = Path(root) / p
    if not path.is_file() or path.is_symlink() or Path(root).resolve() not in path.resolve().parents:
        raise ValueError('Missing or unsafe evidence file: ' + rel)
    return path


def literal(value):
    if not isinstance(value, str) or not value or any(c in value for c in '{}\\\t\r\n'):
        raise ValueError('Unsafe or empty Tcl literal')
    return '{' + value + '}'


def exact_target(value):
    literal(value)
    # Natural bus subscripts are legal; wildcard target groups are not reviewed objects.
    if '*' in value or '?' in value or not re.fullmatch(r'[\w:|.\[\]~ /()+-]+', value):
        raise ValueError('Physical target must be an exact observed node: ' + value)
    return value


def validate_recipe(recipe_path, evidence_root, experiment, profile='q17'):
    recipe = json.loads(Path(recipe_path).read_text())
    if experiment not in ('A1', 'D1') or recipe.get('format') != 'physical-overlay-v1' or recipe.get('experiment') != experiment:
        raise ValueError('Unknown or mismatched physical overlay')
    if recipe.get('review_status') != 'reviewed' or not recipe.get('reviewed_by') or not recipe.get('rationale'):
        raise ValueError('Physical correspondence/site review is pending')
    evidence_root = Path(evidence_root).resolve()
    seal_path = safe_path(evidence_root, 'evidence_manifest.json')
    seal = json.loads(seal_path.read_text())
    from physical.control import profile_spec
    if profile == 'q25':
        if recipe.get('compiler_profile') != 'q25' or seal.get('compiler_profile') != 'q25':
            raise ValueError('Quartus 25 requires new Q25 R0 evidence and compiler-bound recipe')
        if not seal.get('source_commit') or seal.get('hardware_manifest_sha256') != digest(Path(__file__).with_name('hardware_q25.json').read_bytes()):
            raise ValueError('Q25 R0 source or hardware manifest identity incomplete')
    if recipe.get('r0_evidence_sha256') != digest(seal_path.read_bytes()):
        raise ValueError('Recipe is not tied to this exact R0 evidence')
    if seal.get('hardware_baseline') != profile_spec(profile)['hardware_baseline'] or seal.get('experiment') != 'R0':
        raise ValueError('Not an R0 hardware control')
    for rel, expected in seal['files'].items():
        if digest(safe_path(evidence_root, rel).read_bytes()) != expected:
            raise ValueError('R0 evidence changed: ' + rel)
    verify_version(safe_path(evidence_root, 'tool_version.txt').read_text(), profile)
    must_seal = {'tool_version.txt', 'node_inventory.tsv', 'assignment_capabilities.tsv',
                 'input_gate_before_map.json', 'input_gate_before_fit.json'}
    if profile == 'q25': must_seal |= {'resource_clock_gate.json', 'source_manifest_prepared.json', 'source_manifest_before_map.json', 'source_manifest_before_fit.json'}
    if experiment == 'D1': must_seal |= {'diagnostic_status.json', 'fanout_locations.tsv', 'fanout_seeds.tsv'}
    if not must_seal <= set(seal['files']):
        raise ValueError('Required evidence was not sealed: ' + ', '.join(sorted(must_seal - set(seal['files']))))
    if seal.get('generated_input', {}).get('sha256') != digest(expected_build_id()):
        raise ValueError('R0 generated input is not the measured byte sequence')
    for phase in ('before_map', 'before_fit'):
        if not json.loads(safe_path(evidence_root, f'input_gate_{phase}.json').read_text()).get('pass'):
            raise ValueError('R0 source/configuration stage failed')
    stages = {r['stage'] for r in rows(safe_path(evidence_root, 'node_inventory.tsv'))}
    if not {'pre_synthesis', 'post_synthesis', 'post_fitter'} <= stages:
        raise ValueError('Missing complete R0 node stages')
    required = load_registry()['experiments'][experiment]['requires']
    proof = recipe.get('mechanism_evidence', {})
    if set(proof) != set(required):
        raise ValueError('Missing physical-mechanism evidence: ' + ', '.join(required))
    for key in required:
        item = proof[key]
        if not isinstance(item, dict) or not item.get('explanation'):
            raise ValueError('Evidence must include an explicit source/physical explanation: ' + key)
        rel = item.get('file', '')
        if rel not in seal['files']:
            raise ValueError('Unsealed mechanism evidence: ' + rel)
        safe_path(evidence_root, rel)
    inventory = rows(safe_path(evidence_root, 'node_inventory.tsv'))
    identities = {(r['stage'], r['name']) for r in inventory} | {
        (r['stage'], r['short_name']) for r in inventory if r['short_name']}
    node_types = {(r['stage'], name): r['type'] for r in inventory for name in (r['name'], r['short_name']) if name}
    assignments = recipe.get('assignments', [])
    if not assignments or len(assignments) > 32:
        raise ValueError('Expected one reviewed register group or placement cluster, at most 32 exact objects')
    if len({a.get('target') for a in assignments}) != len(assignments):
        raise ValueError('Duplicate overlay target')
    mappings = recipe.get('correspondence', [])
    if len(mappings) != len(assignments):
        raise ValueError('Every assignment needs an independent source/physical correspondence')
    caps = rows(safe_path(evidence_root, 'assignment_capabilities.tsv'))
    group_names = set()
    for a, mapping in zip(assignments, mappings):
        target = exact_target(a.get('target'))
        original, fitted = mapping.get('rtl_node'), mapping.get('fitted_node')
        if mapping.get('status') != 'reviewed' or not mapping.get('explanation'):
            raise ValueError('Unresolved source-to-physical correspondence')
        if ('pre_synthesis', original) not in identities or ('post_fitter', fitted) not in identities:
            raise ValueError('Correspondence does not name observed original and fitted nodes')
        if target not in (original, fitted):
            raise ValueError('Assignment target is not its reviewed node')
        name, value = a.get('name'), a.get('value')
        group_names.add(name)
        if experiment == 'A1':
            if a.get('kind') != 'instance' or (name, value) not in {
                    ('PHYSICAL_SYNTHESIS_REGISTER_RETIMING', 'OFF'),
                    ('ADV_NETLIST_OPT_ALLOWED', 'NEVER_ALLOW')}:
                raise ValueError('A1 permits one scoped movement-control factor only')
            if 'position' not in original or 'u_vsize' not in original:
                raise ValueError('A1 source must be reviewed CRT position state')
            if not re.search(r'(?:\||\.)position(?:\[\d+\])?$', original):
                raise ValueError('A1 targets position state, not position_next or qualification wires')
            if node_types[('pre_synthesis', original)] not in ('reg', 'register') or node_types[('post_fitter', fitted)] not in ('reg', 'register'):
                raise ValueError('A1 correspondence must identify actual source and physical register objects')
            cap = [r for r in caps if r['name'] == name and r['scope'] == 'instance' and r['available'] == '1']
            if not cap or any('not supported' in r['metadata'].lower() for r in cap):
                raise ValueError('Assignment unsupported in the observed edition/scope')
            if not any(re.search(r'\b' + re.escape(value) + r'\b', r['metadata'], re.I) for r in cap):
                raise ValueError('Accepted value not established by installed assignment metadata')
            if not mapping.get('register_scope_verified'):
                raise ValueError('Individual-register scope has not been reviewed in 17.0.2')
        else:
            if a.get('kind') != 'location' or name != 'LOCATION':
                raise ValueError('D1 permits existing-node placement only')
            literal(value)
            if not re.fullmatch(r'(?:LC|FF|LABCELL)_X\d+_Y\d+_N\d+', value):
                raise ValueError('D1 site must use an exported device location spelling')
            legal = recipe.get('legal_sites', {})
            site_evidence = legal.get(value)
            if not site_evidence or site_evidence not in seal['files']:
                raise ValueError('Location lacks sealed native legal-site evidence')
            if value not in safe_path(evidence_root, site_evidence).read_text():
                raise ValueError('Selected site not present in its native export')
            graph = json.loads(safe_path(evidence_root, 'diagnostic_status.json').read_text())
            if not graph.get('fanout_graph_complete'):
                raise ValueError('D1 selector footprint is incomplete')
            drivers = {r['source'] for r in rows(safe_path(evidence_root, 'fanout_locations.tsv'))}
            if fitted not in drivers:
                raise ValueError('Placement target has no complete exported load footprint')
            seeds = {r['node'] for r in rows(safe_path(evidence_root, 'fanout_seeds.tsv')) if r['family'] == 'delta'}
            adjacent = {}
            for edge in rows(safe_path(evidence_root, 'fanout_locations.tsv')):
                adjacent.setdefault(edge['source'], set()).add(edge['destination'])
            reachable, todo = set(seeds), list(seeds)
            while todo:
                for dst in adjacent.get(todo.pop(), set()):
                    if dst not in reachable: reachable.add(dst); todo.append(dst)
            if fitted not in reachable:
                raise ValueError('D1 target is outside the observed original delta selector cone')
    if len(group_names) != 1:
        raise ValueError('Do not stack physical factors in one independent experiment')
    return recipe


def render(recipe):
    result = ['# Reviewed one-factor physical overlay; exact targets, no RTL changes.']
    for a in recipe['assignments']:
        if a['kind'] == 'instance':
            result.append('set_instance_assignment -name ' + a['name'] + ' ' + literal(a['value']) + ' -to ' + literal(a['target']))
        else:
            result.append('set_location_assignment ' + literal(a['value']) + ' -to ' + literal(a['target']))
    return '\n'.join(result) + '\n'


def materialize(root, recipe, evidence_root):
    root = Path(root); out = root / 'output_files'
    content = render(recipe)
    (out / 'physical_overlay.qsf').write_text(content)
    write_json(out / 'physical_recipe.json', recipe)
    # Preserve all bytes supporting the decision, not only an unauditable approval bit.
    import shutil
    destination = out / 'control_evidence'; destination.mkdir()
    seal = json.loads((Path(evidence_root) / 'evidence_manifest.json').read_text())
    for rel in [*seal['files'], 'evidence_manifest.json']:
        source = safe_path(evidence_root, rel)
        if source.suffix.lower() in ('.qdb', '.cdb', '.rbf', '.sof'):
            raise ValueError('Compiled databases/bitstreams are not experiment evidence inputs')
        target = destination / rel; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    with (root / 'Groovy.qsf').open('a') as stream:
        stream.write('\n# Independently reviewed physical factor\nsource output_files/physical_overlay.qsf\n')
    with (out / 'physical_targets.tcl').open('w') as stream:
        stream.write('set physical_targets {}\n')
        for a in recipe['assignments']:
            stream.write('lappend physical_targets ' + literal(a['target']) + '\n')
    write_json(out / 'physical_overlay_identity.json', {
        'experiment': recipe['experiment'], 'sha256': digest(content.encode()),
        'control_evidence_sha256': recipe['r0_evidence_sha256'], 'assignments': recipe['assignments']})
