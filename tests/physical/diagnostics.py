#!/usr/bin/env python3
"""Assemble observed physical exports; keep missing correspondence unresolved.

No Quartus execution. Supports offline assembly into a separate destination so
the supplied measured archives and extracted references need not be changed.
"""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'tests/restart'))
from physical.control import digest, load_registry, write_json
from report_io_coverage import report as io_report
from map_evidence import extract


def read_rows(path):
    if not Path(path).exists(): return []
    with Path(path).open() as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def table(path, header, data):
    with Path(path).open('w', newline='') as stream:
        writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
        writer.writerow(header)
        writer.writerows(data)


def xy(location):
    match = re.search(r'_X(\d+)_Y(\d+)', location)
    return tuple(map(int, match.groups())) if match else None


def family(source, sink):
    if 'PoC_lz4_delta' in source or 'PoC_lz4_delta' in sink: return 'delta-selection'
    if 'dv_hs1' in sink: return 'sync-metadata'
    if 'packed_ram' in sink: return 'crt-read'
    if any(x in source + sink for x in ('advance_rows', 'delay_lines', 'u_vsize|position')): return 'crt-row'
    if any(x in source + sink for x in ('|PoC_V', '|vga', '|Add17')): return 'vga-root'
    if 'lz4' in (source + sink).lower(): return 'lz4'
    return 'other:' + sink.split('|')[0]


def logical_bits(atom_rows):
    result = []
    known = defaultdict(set)
    for r in atom_rows:
        match = re.search(r'packed_ram\[[012]\]\.(even|odd)_ram\|', r['node'])
        if r['direction'] == 'INPUT' and r['port'] == 'PORTBADDR' and match:
            known[(match[1], r['bit'])].add((r['peer'], r['peer_port'], r.get('peer_bit', '')))
    for part in range(3):
        for bank in ('even', 'odd'):
            token = f'packed_ram[{part}].{bank}_ram|'
            for bit in range(12):
                physical = [r for r in atom_rows if r['direction'] == 'INPUT' and token in r['node']
                            and r['port'] == 'PORTBADDR' and r['bit'] == str(bit)]
                if physical:
                    for r in physical:
                        result.append([part, bank, bit, 'OBSERVED_RAM_PORT', r['node'], r['port'], r['peer'], r['peer_port'], r['fanout'],
                                       'Physical RAM input edge; this does not resolve source register movement.'])
                    continue
                # A named high-bit wire is evidence only when its actual mapped
                # fanout edge exists. Do not synthesize physical ports 5..11.
                candidates = [r for r in atom_rows if r['direction'] == 'INPUT' and token in r['node']
                              and (r['peer'], r['peer_port'], r.get('peer_bit', '')) in known[(bank, str(bit))]]
                if candidates:
                    for r in candidates:
                        result.append([part, bank, bit, 'OBSERVED_HIGH_BIT_FANOUT', r['node'], r['port'], r['peer'], r['peer_port'], r['fanout'],
                                       'Same observed output port as this logical bit on another bank RAM input; trace destination mux role.'])
                else:
                    reason = 'Mapped logical bit/output-selection correspondence pending'
                    if part < 2 and bit > 4:
                        reason += '; MLAB physical address width is five bits'
                    result.append([part, bank, bit, 'UNRESOLVED', '', '', '', '', '', reason])
    return result


def retiming(inventory, panels):
    pre = {r['name'] for r in inventory if r['stage'] == 'pre_synthesis'}
    report_hits = defaultdict(list)
    for r in panels:
        if 'retim' in r['panel'].lower() and r['value']:
            report_hits[r['value']].append(f"{r['panel']} row {r['row']} column {r['column']}")
    out = []
    for r in inventory:
        if r['stage'] != 'post_fitter' or r['type'] not in ('reg', 'register'): continue
        if not re.search(r'position|advance_rows|Add17|v_cnt|hb_d|control|NEW_REG', r['name']): continue
        exact = r['name'] if r['name'] in pre else ''
        status = 'SAME_NAME_NOT_MOVEMENT_PROOF' if exact else 'UNRESOLVED_ORIGINAL_REGISTER'
        hits = report_hits.get(r['name'], []) + report_hits.get(r['short_name'], [])
        out.append([exact, r['name'], r['source_file'], status, '; '.join(hits),
                    'Names and retiming actions require explicit pre/post fanin/capture cross-probing.'])
    if not out:
        out.append(['', '', '', 'PENDING_QUARTUS_EXPORT', '', 'No fitted register inventory supplied; no source mapping inferred.'])
    return out


def metadata(atom_rows, panels):
    out = []
    for r in atom_rows:
        if 'dv_hs1_rtl_0' in r['node']:
            out.append([r['direction'], r['node'], r['port'], r['bit'], r['peer'], r['peer_port'], r['peer_bit'],
                        '', 'OBSERVED_EDGE_STAGE_MAPPING_PENDING',
                        'Input and output edges are separate observations, not an assumed internal bit/tap pairing.'])
    for r in panels:
        if 'packed' in r['panel'].lower() and re.search(r'control\[|dv_hs|dv_vs|yc_out', r['value']):
            out.append(['PACKING_REPORT', '', '', '', r['value'], '', '', '', 'PACKED_ASSOCIATION_ONLY',
                        f"{r['panel']} row {r['row']} column {r['column']}"])
    if not out:
        out.append(['', '', '', '', '', '', '', '', 'PENDING_QUARTUS_EXPORT', 'Packed DATAA bit 7 and tap correspondence is unresolved.'])
    return out


def coverage(output):
    result = []
    check = output / 'timing_closure/check_timing.txt'
    if check.exists():
        for line in check.read_text(errors='replace').splitlines():
            cells = [x.strip() for x in line.split(';')[1:-1]]
            if len(cells) != 2 or 'No clock feeds' not in cells[1]: continue
            node = cells[0]
            owner = 'unclassified'
            for marker, name in [('sysmem_lite:sysmem', 'sysmem'), ('h2f_gp', 'h2f_gp'), ('hdmi_i2c', 'hdmi_i2c')]:
                if marker in node: owner = name; break
            result.append(['no_clock', node, owner, 'UNRESOLVED_IP_MODEL_OR_FABRIC_PATH', cells[1],
                           'Trace actual hard-IP timing model, clock pin and active fabric crossing; no blanket exception.'])
    ucp = output / 'timing_closure/unconstrained.txt'
    if ucp.exists():
        for r in io_report(ucp)['ports']:
            result.append(['io_' + r['direction'], r['port'], r['interface'], r['status'],
                           'timing_closure/unconstrained.txt', r['reason']])
    ignored = output / 'timing_closure/ignored_constraints.txt'
    if ignored.exists():
        for i, line in enumerate(ignored.read_text(errors='replace').splitlines(), 1):
            if re.search(r'create_clock|set_false_path|set_multicycle_path|set_clock_groups', line):
                result.append(['ignored_constraint', line.strip(), 'constraint owner', 'REVIEW_REQUIRED',
                               f'timing_closure/ignored_constraints.txt:{i}', 'Distinguish inactive/removed nodes from missing active constraints.'])
    return result


def path_metrics(output):
    """Vendor data-path cell/routing statistics from every negative setup path."""
    result = []
    output = Path(output)
    for path in sorted((output / 'timing_closure').glob('corner_*/negative_setup_paths.txt')):
        for p in extract(path):
            result.append(dict(corner=path.parent.name, launch=p['launch'], capture=p['capture'],
                               family=family(p['launch'], p['capture']), slack_ns=p['slack_ns'],
                               cell_delay_ns=p['cell_delay_ns'], routing_delay_ns=p['routing_delay_ns'],
                               data_delay_ns=p['data_delay_ns'], logic_levels=p['logic_levels'],
                               launch_fanout=p['launch_cell']['fanout'], launch_location=p['launch_cell']['location'],
                               capture_location=p['capture_cell']['location'], clock_skew_ns=p['clock_skew_ns'],
                               setup_relationship_ns=p['setup_relationship_ns'], setup_uncertainty_ns=p['setup_uncertainty_ns'],
                               report=path.relative_to(output).as_posix()))
    return result


def collect(output, destination=None):
    output = Path(output).resolve()
    out = Path(destination).resolve() if destination else output / 'closure_diagnostics'
    out.mkdir(parents=True, exist_ok=True)
    raw = output / 'closure_diagnostics'
    if out != raw and raw.exists():
        for p in raw.iterdir():
            if p.is_file() and p.name != 'evidence_manifest.json': shutil.copy2(p, out / p.name)
    inventory = read_rows(out / 'node_inventory.tsv')
    if not (out / 'node_inventory.tsv').exists():
        table(out / 'node_inventory.tsv', ['stage', 'name', 'short_name', 'type', 'creator', 'source_file', 'query_status'], [])
    if not (out / 'assignment_support.txt').exists():
        (out / 'assignment_support.txt').write_text('PENDING: installed compiler assignment metadata export has not been run.\n')
    if not (out / 'assignment_capabilities.tsv').exists():
        table(out / 'assignment_capabilities.tsv', ['module', 'scope', 'name', 'available', 'metadata'], [])
    panels = read_rows(out / 'report_panels_map.tsv') + read_rows(out / 'report_panels_cmp.tsv')
    atoms = read_rows(out / 'atom_ports_cmp.tsv')
    bits = logical_bits(atoms)
    table(out / 'crt_logical_read_bits.tsv', ['part', 'bank', 'logical_bit', 'status', 'destination', 'port', 'driver', 'driver_port', 'fanout', 'reason'], bits)
    table(out / 'retiming_correspondence.tsv', ['rtl_register', 'physical_register', 'source_file', 'status', 'movement_report', 'required_confirmation'], retiming(inventory, panels))
    table(out / 'metadata_bit_map.tsv', ['direction', 'memory', 'port', 'physical_bit', 'peer', 'peer_port', 'peer_bit', 'rtl_stage', 'status', 'evidence'], metadata(atoms, panels))
    edges = read_rows(out / 'fanout_locations.tsv')
    if not (out / 'fanout_locations.tsv').exists():
        table(out / 'fanout_locations.tsv', ['source', 'source_type', 'source_location', 'destination', 'destination_type', 'destination_location', 'edge_type', 'expected_fanout', 'edge_id'], [])
    grouped = defaultdict(list)
    for r in edges: grouped[r['source']].append(r)
    footprints = []
    graph_errors = []
    for source, connections in grouped.items():
        expected = {int(r['expected_fanout']) for r in connections}
        if len(expected) != 1 or len(connections) != next(iter(expected)) or len({r['edge_id'] for r in connections}) != len(connections):
            graph_errors.append(source + ': incomplete or duplicate fanout')
        coords = [xy(r['destination_location']) for r in connections]
        located = [v for v in coords if v is not None]
        bounds = [min(p[0] for p in located), max(p[0] for p in located), min(p[1] for p in located), max(p[1] for p in located)] if located else ['', '', '', '']
        footprints.append([source, len(connections), len(located), len(coords) - len(located), *bounds])
    table(out / 'driver_footprints.tsv', ['driver', 'loads', 'located_loads', 'unlocated_loads', 'min_x', 'max_x', 'min_y', 'max_y'], footprints)
    header = ['corner', 'launch', 'capture', 'family', 'slack_ns', 'cell_delay_ns', 'routing_delay_ns', 'data_delay_ns', 'logic_levels', 'launch_fanout', 'launch_location', 'capture_location', 'clock_skew_ns', 'setup_relationship_ns', 'setup_uncertainty_ns', 'report']
    table(out / 'critical_path_metrics.tsv', header, [[r[h] for h in header] for r in path_metrics(output)])
    video = []
    for corner in read_rows(output / 'timing_closure/corners.tsv'):
        directory = output / 'timing_closure' / corner['directory']
        report = directory / 'crt_capture_setup.txt'
        if not report.exists(): report = directory / 'wcol_setup.txt'
        observed = []
        if report.exists():
            observed = [r for r in extract(report, False) if 'emu|pll|' in (r['launch_clock'] or '')
                        and r['launch_clock'] == r['latch_clock']]
        valid = bool(observed) and all(r['setup_relationship_ns'] == 12.081 and r['setup_uncertainty_ns'] == 0.200 for r in observed)
        video.append({'corner': corner['directory'], 'observed_paths': len(observed), 'requirements_pass': valid,
                      'required_period_ns': 12.081, 'required_setup_uncertainty_ns': 0.200, 'report': report.name})
    write_json(out / 'video_requirements.json', {'corners': video, 'pass': len(video) == 8 and all(r['requirements_pass'] for r in video),
                                               'scope': 'Observed same-video-clock paths; source/clock/constraint audits remain mandatory.'})
    observations = coverage(output)
    table(out / 'coverage_disposition.tsv', ['finding', 'object', 'owner', 'status', 'evidence', 'required_information'], observations)
    routes = [r for r in panels if re.search(r'routing|congestion', r['panel'], re.I)]
    with (out / 'routing_footprint.txt').open('w') as stream:
        stream.write('Driver/load coordinate bounds: driver_footprints.tsv. Grid spans are not actual routed wire length.\n')
        stream.write('Measured cell/routing delays: critical_path_metrics.tsv; clock skew: per-corner all_setup_endpoints.tsv.\n')
        stream.write('Complete exported routing/congestion report cells follow; absent hotspots remain pending native inspection.\n')
        for r in routes: stream.write(json.dumps(r, sort_keys=True) + '\n')
        if not routes: stream.write('PENDING: no native routing-utilization/hotspot panel exported. Do not infer congestion from ALM count.\n')
    status_rows = read_rows(out / 'fanout_export_status.tsv')
    complete = bool(status_rows and status_rows[0]['complete'] == '1' and edges and not graph_errors)
    # Missing/native-query fields invalidate the export, not just its name.
    query_error_files = [out / ('project_query_errors_' + phase + '.tsv')
                         for phase in ('map', 'cmp')]
    partial_nodes = [r for r in inventory if r.get('query_status') != 'OBSERVED']
    query_errors = sum(len(read_rows(p)) for p in query_error_files if p.is_file())
    logical_complete = len(bits) == 72 and all(r[3] != 'UNRESOLVED' for r in bits)
    native_queries_complete = (all(p.is_file() for p in query_error_files)
                               and not partial_nodes and query_errors == 0
                               and logical_complete)
    # A complete graph can still contain unplaced/nonphysical nodes; D1 must
    # account for them rather than using one endpoint as the load distribution.
    status = {
        'format': 'physical-diagnostics-v1', 'fanout_graph_complete': complete,
        'export_queries_complete': bool(complete and native_queries_complete
                                        and {'pre_synthesis', 'post_synthesis', 'post_fitter'} <= {r['stage'] for r in inventory}
                                        and all((out / p).is_file() for p in ('atom_ports_map.tsv', 'atom_ports_cmp.tsv'))),
        'query_error_count': query_errors, 'partial_inventory_nodes': len(partial_nodes),
        'logical_ram_bits_complete': logical_complete,
        'graph_errors': graph_errors, 'unlocated_edges': sum(not r['destination_location'] for r in edges),
        'inventory_stages': dict(Counter(r['stage'] for r in inventory)),
        'unresolved_logical_bits': len({(r[0], r[1], r[2]) for r in bits if r[3] == 'UNRESOLVED'}),
        'retiming_correspondence': 'PENDING_SOURCE_CROSS_PROBE',
        'metadata_stage_correspondence': 'PENDING_DATAA_TO_TAP_MAPPING',
        'video_requirements_pass': len(video) == 8 and all(r['requirements_pass'] for r in video),
        'coverage_release_qualified': False,
        'coverage_reports_present': all((output / 'timing_closure' / p).is_file() for p in ('check_timing.txt', 'unconstrained.txt')),
        'coverage_review_status': 'PENDING_MODEL_INTERFACE_AND_CDC_DISPOSITION',
        'pending_experiments': {'A1': load_registry()['experiments']['A1']['reason'], 'D1': load_registry()['experiments']['D1']['reason']},
        'qualification': 'Observed exports only. A generated name is not source correspondence; no timing-closure or hardware claim.',
    }
    provenance = json.loads((output / 'provenance.json').read_text()) if (output / 'provenance.json').exists() else {}
    profile = provenance.get('compiler_profile', 'q17')
    ram_evidence = output / 'q25_window_ram_gate.json'
    if profile == 'q25':
        status['q25_lz4_ram_evidence_present'] = ram_evidence.is_file()
        status['q25_lz4_ram_inferred'] = (json.loads(ram_evidence.read_text()).get('embedded_ram_inferred', False)
                                        if ram_evidence.is_file() else False)
        status['export_queries_complete'] = bool(status['export_queries_complete'] and status['q25_lz4_ram_inferred'])
    write_json(out / 'diagnostic_status.json', status)
    if ram_evidence.is_file(): shutil.copy2(ram_evidence, out / 'q25_window_ram_gate.json')
    version = output / 'crt_read_address_tool_version.txt'
    if version.exists(): shutil.copy2(version, out / 'tool_version.txt')
    for name in ('project_calls_before_map.json', 'project_calls_before_fit.json', 'host_environment.json',
                 'source_manifest_prepared.json', 'source_manifest_before_map.json', 'source_manifest_before_fit.json',
                 'input_gate_before_map.json', 'input_gate_before_fit.json', 'resource_clock_gate.json', 'crt_local_drivers_cmp.json'):
        if (output / name).exists(): shutil.copy2(output / name, out / name)
    if (output / 'timing_closure/timing_gate.json').exists():
        shutil.copy2(output / 'timing_closure/timing_gate.json', out / 'timing_gate.json')
    identity = {
        'hardware_baseline': provenance.get('experiment', {}).get('hardware_baseline', load_registry()['hardware_baseline']),
        'compiler_profile': profile,
        'hardware_manifest_sha256': provenance.get('hardware_manifest_sha256'),
        'experiment': provenance.get('experiment', {}).get('name'), 'source_commit': provenance.get('source_commit'),
        'generated_input': provenance.get('generated_input'),
        'source_manifest_hashes': {p.name: digest(p.read_bytes()) for p in output.glob('source_manifest_*.json')},
    }
    write_json(out / 'r0_identity.json', identity)
    files = {p.relative_to(out).as_posix(): digest(p.read_bytes()) for p in sorted(out.rglob('*'))
             if p.is_file() and p.name != 'evidence_manifest.json'}
    write_json(out / 'evidence_manifest.json', {**identity, 'format': 'physical-evidence-v1', 'files': files})
    return status


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output_files', type=Path); p.add_argument('--destination', type=Path)
    a = p.parse_args(); print(json.dumps(collect(a.output_files, a.destination), indent=2))
