"""Q25 upper selectors and evidence-gated counter boundary. No vendor calls."""
import argparse
import gzip
import csv
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
from physical.upper_selection import rows, resolve, compose, audit_fit, reject_ignored, sha, literal

CONTROL = '3b8d1edb63f2d2fed05d23323c3ba1ae93eeed1a'
NAMES = ('U10', 'U9', 'V3', 'U10_U9_V3')


class Blocked(ValueError):
    """Evidence is pending. Never replace a blocked factor with a control build."""


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def output_root(path):
    path = Path(path).resolve()
    return path / 'output_files' if (path / 'output_files/provenance.json').exists() else path


def validate_selection(source, experiment):
    path=Path(source)/'tests/physical/selected_experiment.json'
    if not path.exists():return
    selected=json.loads(path.read_text())
    if (selected.get('control_commit')!=CONTROL or selected.get('compiler_profile')!='q25'
            or selected.get('experiment')!=experiment or selected.get('factors')!=factors(experiment)):
        raise ValueError('Individual experiment branch selection differs; use the shared batch branch for other factors')


def checked_path(root, rel):
    p = Path(rel)
    target = Path(root) / p
    if p.is_absolute() or '..' in p.parts or target.is_symlink() or not target.is_file():
        raise ValueError('Missing/unsafe evidence: ' + str(rel))
    return target


def validate_baseline(path):
    from physical.control import expected_build_id, digest, verify_version
    b = output_root(path)
    p = json.loads(checked_path(b, 'provenance.json').read_text())
    if p.get('source_commit') != CONTROL or p.get('compiler_profile') != 'q25' or p.get('experiment', {}).get('name') != 'R0':
        raise ValueError('Requires exact original Q25 R0 control, not V1/V2 or a newer baseline')
    manifest = json.loads((Path(__file__).with_name('hardware_q25.json')).read_text())
    if p.get('hardware_hashes') != manifest['files'] or p.get('hardware_manifest_sha256') != sha(Path(__file__).with_name('hardware_q25.json')):
        raise ValueError('Q25 hardware manifest differs from the control')
    if p.get('generated_input', {}).get('sha256') != digest(expected_build_id()):
        raise ValueError('Frozen generated input differs')
    verify_version(checked_path(b, 'crt_read_address_tool_version.txt').read_text(), 'q25')
    needed = ['provenance.json', 'crt_read_address_tool_version.txt', 'resource_clock_gate.json',
              'q25_window_ram_gate.json', 'source_manifest_prepared.json',
              'source_manifest_before_map.json', 'source_manifest_before_fit.json',
              'closure_diagnostics/atom_ports_map.tsv']
    for phase in ('before_map', 'before_fit'):
        needed += ['input_gate_' + phase + '.json', 'project_calls_' + phase + '.json']
        if not json.loads(checked_path(b, needed[-2]).read_text()).get('pass'):
            raise ValueError('Baseline input gate failed: ' + phase)
    resource = json.loads(checked_path(b, 'resource_clock_gate.json').read_text())
    ram = json.loads(checked_path(b, 'q25_window_ram_gate.json').read_text())
    if not resource.get('resource_clock_pass') or resource.get('m10k_used') != 489 or resource.get('mlab_bits') != 491520:
        raise ValueError('Baseline memory/resource identity differs')
    if not ram.get('embedded_ram_inferred') or ram.get('compiler_profile') != 'q25':
        raise ValueError('Baseline registered LZ4 memory not established')
    # Old R0 export-completeness failure is preserved, not mistaken for a bad fit.
    # Validate actual timing inventories independently without writing to them.
    from validate_timing_exports import validate
    validate(b / 'timing_closure')
    for phase in ('prepared', 'before_map', 'before_fit'):
        m = json.loads(checked_path(b, 'source_manifest_' + phase + '.json').read_text())
        if m.get('source_commit') != CONTROL or m.get('experiment', {}).get('name') != 'R0':
            raise ValueError('Baseline source snapshot identity differs: ' + phase)
    prepared = {r['path']: r['sha256'] for r in json.loads((b / 'source_manifest_prepared.json').read_text())['files']}
    if any(prepared.get(rel) != wanted for rel, wanted in manifest['files'].items()):
        raise ValueError('Prepared baseline hardware bytes differ')
    return {'format': 'q25-original-control-v1', 'source_commit': CONTROL,
            'compiler_profile': 'q25', 'hardware_manifest_sha256': p['hardware_manifest_sha256'],
            'generated_input_sha256': p['generated_input']['sha256'],
            'files': {n: sha(checked_path(b, n)) for n in needed}}


def validate_v3(recipe_path, evidence):
    """A reviewed original-register boundary, not generated-name pattern matching."""
    if not recipe_path: raise Blocked('V3: original register ancestry and instance assignment scope/value remain unverified')
    recipe = json.loads(Path(recipe_path).read_text())
    if recipe.get('format') != 'q25-v3-boundary-v1' or recipe.get('status') != 'reviewed':
        raise Blocked('V3 recipe is blocked or has not been reviewed')
    seal = validate_baseline(evidence)
    if (recipe.get('control_commit') != CONTROL or recipe.get('compiler_profile') != 'q25'
            or recipe.get('hardware_manifest_sha256') != seal['hardware_manifest_sha256']
            or recipe.get('generated_input_sha256') != seal['generated_input_sha256']
            or recipe.get('control_provenance_sha256') != seal['files']['provenance.json']):
        raise ValueError('V3 recipe is bound to a different source/compiler/control')
    b = output_root(evidence)
    proof = recipe.get('evidence', {})
    proof_root = Path(recipe_path).resolve().parent / recipe.get('evidence_directory', 'V3-evidence')
    required = {'register_ancestry', 'clock_enable_reset_initialization', 'native_assignment_scope_values'}
    if set(proof) != required or not recipe.get('reviewed_by') or not recipe.get('mechanism'):
        raise Blocked('V3 source/cycle/scope review is incomplete')
    for item in proof.values():
        if not item.get('explanation') or sha(checked_path(proof_root, item.get('file', ''))) != item.get('sha256'):
            raise ValueError('V3 evidence bytes or explanation missing')
    support = recipe.get('support', {})
    if not all(support.get(k) is True for k in ('native_25_1_lite_verified', 'instance_register_scope_verified', 'accepted_value_verified')):
        raise Blocked('V3 native instance-register support has not been established')
    assignments = recipe.get('assignments', [])
    mappings = recipe.get('correspondence', [])
    if not 1 <= len(assignments) <= 16 or len(assignments) != len(mappings):
        raise ValueError('V3 requires one narrow reviewed register group')
    inv = rows(checked_path(b, 'closure_diagnostics/node_inventory.tsv'))
    identities = {(r['stage'], n): r['type'] for r in inv for n in (r['name'], r['short_name'])}
    factors, targets = set(), set()
    allowed = {('ADV_NETLIST_OPT_ALLOWED', 'NEVER_ALLOW'), ('PHYSICAL_SYNTHESIS_REGISTER_RETIMING', 'OFF')}
    for a, m in zip(assignments, mappings):
        target = a.get('target', ''); literal(target)
        if target in targets: raise ValueError('Duplicate V3 target')
        targets.add(target); factors.add((a.get('name'), a.get('value')))
        if a.get('kind') != 'instance' or (a.get('name'), a.get('value')) not in allowed:
            raise ValueError('V3 factor not allowed; global retiming must remain enabled')
        original, fitted = m.get('rtl_node', ''), m.get('fitted_node', '')
        if not re.fullmatch(r'emu:emu\|vga:vga\|v_cnt\[(?:[0-9]|1[0-5])\]', original):
            raise ValueError('V3 targets original VGA vertical-counter state only')
        if target not in (original, fitted) or not m.get('reviewed') or not m.get('ancestry_explanation'):
            raise ValueError('Unreviewed source-to-physical register correspondence')
        if identities.get(('pre_synthesis', original)) not in ('reg', 'register') or identities.get(('post_fitter', fitted)) not in ('reg', 'register'):
            raise ValueError('V3 target is not an observed original/fitted register')
    if len(factors) != 1: raise ValueError('Do not stack V3 physical factors')
    if support.get('name') != assignments[0]['name'] or support.get('value') != assignments[0]['value']:
        raise ValueError('V3 accepted value does not match assignment')
    native=json.loads(checked_path(proof_root,proof['native_assignment_scope_values']['file']).read_text())
    if (native.get('status')!='supported' or native.get('version')!='25.1std.0' or native.get('build')!=1129
            or native.get('edition')!='Lite' or native.get('scope')!='instance' or native.get('object_type')!='register'
            or native.get('name')!=support['name'] or support['value'] not in native.get('accepted_values',[])
            or not native.get('reviewed_by') or not native.get('native_evidence')):
        raise Blocked('V3 native scope/value certificate is incomplete or unsupported')
    if not isinstance(native['native_evidence'],dict):raise Blocked('V3 native scope certificate needs hashed native evidence files')
    for rel,wanted in native['native_evidence'].items():
        if sha(checked_path(proof_root,rel))!=wanted:raise ValueError('Native V3 metadata evidence changed')
    return recipe


def factors(experiment):
    if experiment not in NAMES: raise ValueError('Unknown Q25 experiment')
    return ['U10', 'U9', 'V3'] if experiment == 'U10_U9_V3' else [experiment]


def request(experiment, evidence, v3_recipe=None):
    seal = validate_baseline(evidence)
    needed = factors(experiment)
    resolutions = []
    if any(e in ('U10', 'U9') for e in needed):
        path = checked_path(output_root(evidence), 'closure_diagnostics/atom_ports_map.tsv')
        rr = rows(path)
        graph = {'kind':'control-archive', 'sha256':sha(path)}
        if not any(r['direction']=='OUTPUT' for r in rr):
            # The original sealed 3b8 archive predates complete output exports.
            # Use ONLY the committed complete R0-PHYS excerpt, never a partial
            # candidate graph or an arbitrary replacement supplied by filename.
            fixture=Path(__file__).with_name('fixtures')/'upper_selection_r0_map.tsv.gz'
            metadata=json.loads(fixture.with_suffix('').with_suffix('.json').read_text())
            if metadata.get('control_commit')!=CONTROL or metadata.get('fixture_sha256')!=sha(fixture):
                raise ValueError('Reviewed R0-PHYS fixture identity mismatch')
            with gzip.open(fixture,'rt') as stream:rr=list(csv.DictReader(stream,delimiter='\t'))
            graph={'kind':'actual-reviewed-R0-PHYS-complete-selected-excerpt',**metadata}
        for e in needed:
            if e in ('U10', 'U9'): resolutions.append(resolve(rr, e))
        compose(resolutions)
        seal['files']['closure_diagnostics/atom_ports_map.tsv'] = sha(path)
    v3 = validate_v3(v3_recipe, evidence) if 'V3' in needed else None
    return {'format': 'q25-timing-candidate-v1', 'experiment': experiment, 'factors': needed,
            'control': seal, 'assignments': v3['assignments'] if v3 else [],
            'v3': v3, 'baseline_upper_observations': resolutions,
            'baseline_upper_graph': graph if resolutions else None,
            'mechanism_status': 'PENDING_FRESH_MAP_AND_FIT',
            'source_rtl_changes': [], 'generated_input_changes': []}


def materialize(root, spec, evidence):
    from physical.overlays import render
    root, b = Path(root), output_root(evidence)
    out = root / 'output_files'
    write(out / 'q25_experiment.json', spec)
    target = out / 'control_evidence'; target.mkdir()
    for phase in ('before_map', 'before_fit'):
        shutil.copy2(b / ('project_calls_' + phase + '.json'), target)
    write(target / 'control_identity.json', spec['control'])
    (out / 'upper_address_duplication.qsf').write_text('# Empty before fresh map; resolver must run before fit.\n')
    with (root / 'Groovy.qsf').open('a') as f:
        f.write('\n# Q25 independently resolved upper selector experiment\nsource output_files/upper_address_duplication.qsf\n')
    if spec['v3']:
        (out / 'physical_overlay.qsf').write_text(render({'assignments': spec['assignments']}))
        with (root / 'Groovy.qsf').open('a') as f: f.write('source output_files/physical_overlay.qsf\n')
        with (out / 'physical_targets.tcl').open('w') as f:
            f.write('set physical_targets {}\n')
            for a in spec['assignments']: f.write('lappend physical_targets ' + literal(a['target']) + '\n')


def derived_assignments(out, actual, phase):
    """Do not let the historical low-bit policy filter hide arbitrary new DUPs."""
    out = Path(out)
    if not (out / 'q25_experiment.json').exists(): return
    expected = set()
    for rel in ('crt_address_duplication_resolved.qsf', 'upper_address_duplication.qsf'):
        path = out / rel
        if not path.exists(): continue
        for line in path.read_text().splitlines():
            if not line.startswith('set_instance_assignment'): continue
            m = re.fullmatch(r'set_instance_assignment -name DUPLICATE_ATOM (\w+) -from \{([^}]+)\} -to \{([^}]+)\}', line)
            if not m: raise ValueError('Unexpected generated duplication syntax')
            expected.add(tuple(['instance', '-name', 'DUPLICATE_ATOM', m[1], '-from', m[2], '-to', m[3]]))
    observed = {tuple(r) for r in actual['events'] if 'DUPLICATE_ATOM' in r}
    if expected != observed: raise ValueError('Unapproved or missing derived duplication assignments')
    if phase == 'before_fit':
        spec = json.loads((out / 'q25_experiment.json').read_text())
        upper = [e for e in spec['factors'] if e in ('U10','U9')]
        if len(expected) != 30 + len(upper): raise ValueError('Original 30 low-bit assignments or upper factors missing')
        rr = rows(out / 'closure_diagnostics/atom_ports_map.tsv')
        resolutions = [resolve(rr, e) for e in upper]
        if (out / 'upper_address_duplication.qsf').read_text() != compose(resolutions):
            raise ValueError('Upper assignment bytes differ from the current mapped graph')
        if json.loads((out / 'upper_resolution_map.json').read_text()) != resolutions:
            raise ValueError('Upper map correspondence changed')


def audit(out, phase):
    out = Path(out)
    spec = json.loads((out / 'q25_experiment.json').read_text())
    needed = [e for e in spec['factors'] if e in ('U10','U9')]
    rr = rows(out / f'closure_diagnostics/atom_ports_{phase}.tsv')
    if phase == 'map':
        resolutions = [resolve(rr, e) for e in needed]
        (out / 'upper_address_duplication.qsf').write_text(compose(resolutions))
        write(out / 'upper_resolution_map.json', resolutions)
        copies = []
    else:
        resolutions = json.loads((out / 'upper_resolution_map.json').read_text())
        if [r['experiment'] for r in resolutions] != needed: raise ValueError('Upper factors changed after map')
        copies = [audit_fit(rr, r) for r in resolutions]
    reject_ignored(out, resolutions)
    if spec['v3']:
        matches = rows(out / f'closure_diagnostics/target_matches_{phase}.tsv')
        for a in spec['assignments']:
            if not any(r['target'] == a['target'] and int(r['matches']) > 0 for r in matches):
                raise ValueError('V3 required register target not observed')
        # A named match is not an observation of the intended register boundary.
        # The shared application audit also inspects assignment warnings below.
        needles = [a['name'] for a in spec['assignments']] + [a['target'] for a in spec['assignments']]
        for rel in ('Groovy.map.rpt', 'Groovy.fit.rpt', 'duplicate_fit.log'):
            p = out / rel
            if p.exists():
                for line in p.read_text(errors='replace').splitlines():
                    if re.search(r'ignored|unsupported|not supported|cannot apply|does not exist', line, re.I) and any(n in line for n in needles):
                        raise ValueError('Required V3 assignment ignored: ' + line)
    result = {'experiment': spec['experiment'], 'target_gate_pass': True, 'copies': copies,
              'mechanism_status': 'UPPER_SPLIT_OBSERVED_TIMING_REVIEW_PENDING' if copies else 'FRESH_MAP_RESOLVED' if phase=='map' else 'V3_BOUNDARY_REVIEW_PENDING',
              'v3_boundary_verified': False if spec['v3'] else None}
    write(out / f'application_{phase}.json', result)
    if phase == 'cmp': write(out / 'upper_driver_gate.json', {'pass': True, 'copies': copies})
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=['map','cmp']); p.add_argument('output', type=Path)
    a = p.parse_args()
    try: print(json.dumps(audit(a.output, a.phase), indent=2))
    except (ValueError, FileNotFoundError, KeyError) as error:
        write(a.output / ('application_' + a.phase + '.json'), {'target_gate_pass': False, 'error': str(error)})
        raise SystemExit(3)
