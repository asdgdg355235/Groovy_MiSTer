#!/usr/bin/env python3
"""Compare complete eight-corner results. No Quartus or automatic promotion.

--timing-only analyzes historical archives without pretending their absent new
physical/provenance exports have passed. Retention always requires the separate
mechanism, source/configuration, resource and functional evidence gates.
"""
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
from validate_timing_exports import validate
from physical.control import digest, expected_build_id, write_json
from physical.diagnostics import family, read_rows, path_metrics


def load_timing(output):
    output = Path(output)
    gate = validate(output / 'timing_closure')
    corners = read_rows(output / 'timing_closure/corners.tsv')
    index = {r['directory']: (r['model'], r['speed'], r['voltage'], r['temperature']) for r in corners}
    checks = {}
    for row in read_rows(output / 'timing_closure/endpoint_summary.tsv'):
        key = (*index[row['corner']], row['check'])
        directory = output / 'timing_closure' / row['corner']
        negatives = read_rows(directory / f"negative_{row['check']}_endpoints.tsv")
        full = directory / f"all_{row['check']}_endpoints.tsv"
        endpoints = read_rows(full) if full.exists() else negatives
        checks[key] = {**row, 'wns': None if row['worst_slack_ns'] == 'NA' else float(row['worst_slack_ns']),
                       'tns': float(row['endpoint_TNS_ns']), 'count': int(row['failing_endpoints']),
                       'negative': {r['to']: r for r in negatives}, 'endpoints': {r['to']: r for r in endpoints},
                       'full_distribution': full.exists()}
    return gate, checks


def compare_versions(quartus17, quartus25):
    """Report compiler-configuration differences without equating node identities."""
    quartus17, quartus25 = Path(quartus17), Path(quartus25)
    left_gate, old = load_timing(quartus17)
    right_gate, new = load_timing(quartus25)
    if set(old) != set(new):
        raise ValueError('Cross-version timing corners/checks differ')
    def identity(root):
        path = root / 'provenance.json'
        return json.loads(path.read_text()) if path.exists() else {}
    old_source, new_source = identity(quartus17), identity(quartus25)
    if old_source.get('compiler_profile', 'q17') != 'q17' or new_source.get('compiler_profile') != 'q25':
        raise ValueError('Cross-version comparison requires q17 then q25 provenance')
    def resources(root):
        summary = root / 'Groovy.fit.summary'
        data = {}
        if summary.exists():
            for row in summary.read_text(errors='replace').splitlines():
                if ':' in row:
                    key, value = row.split(':', 1)
                    data[key.strip()] = value.strip()
        gate_path = root / 'resource_clock_gate.json'
        if gate_path.exists():
            data['validated_resource_gate'] = json.loads(gate_path.read_text())
        return data
    def families(rows):
        from collections import Counter
        return dict(sorted(Counter(family(row['from'], row['to'])
                                   for check in rows.values() if check['check'] == 'setup'
                                   for row in check['negative'].values()).items()))
    def physical(root):
        rows = read_rows(root / 'closure_diagnostics/critical_path_metrics.tsv')
        by_family = {}
        for row in rows:
            label = (row['corner'], row['family'])
            stats = by_family.setdefault(label, [])
            stats.append({'slack_ns': row['slack_ns'], 'cell_delay_ns': row['cell_delay_ns'],
                          'routing_delay_ns': row['routing_delay_ns'], 'clock_skew_ns': row['clock_skew_ns'],
                          'launch_fanout': row['launch_fanout']})
        return [{'corner': corner, 'family': family_name, 'paths': values}
                for (corner, family_name), values in sorted(by_family.items())]
    def register_count(root):
        from collections import Counter
        rows = read_rows(root / 'closure_diagnostics/node_inventory.tsv')
        return dict(Counter((r['stage'], r['type']) for r in rows))
    margins = [{'corner_and_check': '/'.join(key),
                'q17_wns_ns': old[key]['wns'], 'q25_wns_ns': new[key]['wns'],
                'q17_tns_ns': old[key]['tns'], 'q25_tns_ns': new[key]['tns'],
                'q17_failing_endpoints': old[key]['count'], 'q25_failing_endpoints': new[key]['count']}
               for key in sorted(old)]
    return {'format': 'physical-cross-version-v1',
            'q17_source': old_source.get('source_commit'), 'q25_source': new_source.get('source_commit'),
            'configuration_differences': {
                'lz4': 'q17 asynchronous window; q25 registered-read look-ahead and write-forwarding',
                'pll': 'sys/pll_q17.qip versus sys/pll_q25.qip (same four included QIP lists)',
                'compiler': 'Quartus Prime Lite 17.0.2 Build 602 versus 25.1std.0 Build 1129'},
            'timing_vectors': margins, 'q17_timing_pass': left_gate['timing_pass'],
            'q25_timing_pass': right_gate['timing_pass'],
            'negative_setup_families': {'q17': families(old), 'q25': families(new)},
            'critical_family_metrics': {'q17': physical(quartus17), 'q25': physical(quartus25)},
            'resource_counts': {'q17': resources(quartus17), 'q25': resources(quartus25)},
            'register_inventories': {'q17': [{'stage': stage, 'type': typ, 'count': count}
                                            for (stage,typ), count in sorted(register_count(quartus17).items())],
                                     'q25': [{'stage': stage, 'type': typ, 'count': count}
                                            for (stage,typ), count in sorted(register_count(quartus25).items())]},
            'identity_policy': 'Compiler-local physical node IDs must not be matched across versions.',
            'interpretation': 'RTL window and PLL profile change alongside the compiler; causal attribution to the compiler alone is unsupported.'}


def compare(control, candidate, timing_only=False, published_control=None):
    control, candidate = Path(control), Path(candidate)
    cg, a = load_timing(control); ng, b = load_timing(candidate)
    if set(a) != set(b): raise ValueError('Corner/check sets differ')
    prior_families = {family(r['from'], r['to']) for key, old in a.items() if key[-1] == 'setup'
                      for r in old['negative'].values()}
    regressions, improvements, new_families, endpoint_deltas, rankings, margins = [], [], [], [], [], []
    for key in sorted(a):
        old, new = a[key], b[key]
        label = '/'.join(key)
        margins.append({'corner': label, 'control_wns_ns': old['wns'], 'candidate_wns_ns': new['wns'],
                        'control_tns_ns': old['tns'], 'candidate_tns_ns': new['tns'],
                        'control_failures': old['count'], 'candidate_failures': new['count']})
        if key[-1] == 'setup':
            if old['wns'] is None or new['wns'] is None: raise ValueError('Unanalyzed setup corner')
            if new['wns'] < old['wns'] or new['tns'] < old['tns'] or new['count'] > old['count']:
                regressions.append({'corner': label, 'control': [old['wns'], old['tns'], old['count']],
                                    'candidate': [new['wns'], new['tns'], new['count']]})
            if old['count'] > 0 and (new['wns'] > old['wns'] or new['tns'] > old['tns'] or new['count'] < old['count']):
                improvements.append(label)
            for r in new['negative'].values():
                f = family(r['from'], r['to'])
                if f not in prior_families:
                    new_families.append({'corner': label, 'family': f, 'from': r['from'], 'to': r['to']})
        for sink in sorted(set(old['endpoints']) | set(new['endpoints'])):
            x, y = old['endpoints'].get(sink), new['endpoints'].get(sink)
            endpoint_deltas.append({'corner': label, 'to': sink,
                                    'control_slack': float(x['slack_ns']) if x else None,
                                    'candidate_slack': float(y['slack_ns']) if y else None,
                                    'delta_ns': float(y['slack_ns']) - float(x['slack_ns']) if x and y else None,
                                    'control_clock_skew_ns': x.get('clock_skew_ns') if x else None,
                                    'candidate_clock_skew_ns': y.get('clock_skew_ns') if y else None,
                                    'control_data_delay_ns': x.get('data_delay_ns') if x else None,
                                    'candidate_data_delay_ns': y.get('data_delay_ns') if y else None,
                                    'identity_status': 'EXACT_NAME' if x and y else 'CORRESPONDENCE_REVIEW_REQUIRED'})
        if key[-1] == 'setup' and old['endpoints'] and new['endpoints']:
            x = min(old['endpoints'].values(), key=lambda r: float(r['slack_ns']))
            y = min(new['endpoints'].values(), key=lambda r: float(r['slack_ns']))
            if x['to'] != y['to']: rankings.append({'corner': label, 'old_worst': x['to'], 'new_worst': y['to']})
    other_failures = [r for r in ng['failed_checks'] if r['check'] != 'setup']
    timing_retain = not regressions and not new_families and not other_failures and not ng['pulse_failures'] and bool(improvements)
    pending, invalid = [], []
    if timing_only:
        pending.append('Historical timing-only comparison: physical mechanism/provenance/resource acceptance not evaluated')
    else:
        # Every verdict retains the observations; absence is pending, drift is invalid.
        try:
            cp = json.loads((control / 'provenance.json').read_text())
            np = json.loads((candidate / 'provenance.json').read_text())
            if cp['experiment']['name'] != 'R0': invalid.append('Control is not R0')
            if cp['hardware_hashes'] != np['hardware_hashes']: invalid.append('Hardware baseline hashes changed')
            if cp.get('compiler_profile', 'q17') != np.get('compiler_profile', 'q17'):
                invalid.append('Cross-version candidate comparison is prohibited; use --cross-version')
            if cp.get('hardware_manifest_sha256') != np.get('hardware_manifest_sha256'):
                invalid.append('Physical compiler manifest changed')
            for p in (cp, np):
                if p['generated_input']['sha256'] != digest(expected_build_id()): invalid.append('Generated input mismatch')
            ce = json.loads((control / 'host_environment.json').read_text())
            ne = json.loads((candidate / 'host_environment.json').read_text())
            for k in ('cpu_count', 'affinity', 'host', 'parallel_setting'):
                if ce[k] != ne[k]: invalid.append('Changed execution control: ' + k)
            for phase in ('before_map', 'before_fit'):
                if not json.loads((candidate / f'input_gate_{phase}.json').read_text())['pass']:
                    invalid.append('Source/configuration input gate failed: ' + phase)
            resource = json.loads((candidate / 'resource_clock_gate.json').read_text())
            if not resource.get('resource_clock_pass'): invalid.append('Resource/clock gate failed')
            application = json.loads((candidate / 'application_cmp.json').read_text())
            if not application.get('target_gate_pass'): invalid.append('Physical assignment not applied')
            review = candidate / 'mechanism_review.json'
            if not review.exists():
                pending.append('Post-fit graph mechanism and mapped cycle/initialization review required')
            else:
                review = json.loads(review.read_text())
                if not (review.get('mechanism_verified') and review.get('functional_cycles_verified') and review.get('reviewed_by') and review.get('evidence')):
                    pending.append('Incomplete post-fit mechanism/functional review')
                if not review.get('targeted_path_improved'): invalid.append('No confirmed targeted path improvement')
                if review.get('candidate_provenance_sha256') != digest((candidate / 'provenance.json').read_bytes()):
                    invalid.append('Mechanism review belongs to a different candidate')
                if not isinstance(review.get('evidence'), dict):
                    invalid.append('Mechanism review needs actual evidence file hashes')
                else:
                    for rel, sha in review['evidence'].items():
                        path = candidate / rel
                        if Path(rel).is_absolute() or '..' in Path(rel).parts or not path.is_file() or digest(path.read_bytes()) != sha:
                            invalid.append('Mechanism review evidence changed: ' + rel)
        except (FileNotFoundError, KeyError) as error:
            pending.append('Missing acceptance evidence: ' + str(error))
        if not all(v['full_distribution'] for v in b.values()): pending.append('Complete endpoint distributions missing')
    published = None
    if published_control is not None:
        published_profile = 'q17'
        ppath = Path(published_control) / 'provenance.json'
        if ppath.exists():
            published_profile = json.loads(ppath.read_text()).get('compiler_profile', 'q17')
        candidate_profile = 'q17'
        cpath = candidate / 'provenance.json'
        if cpath.exists():
            candidate_profile = json.loads(cpath.read_text()).get('compiler_profile', 'q17')
        if published_profile != candidate_profile:
            published = compare_versions(published_control, candidate)
        else:
            second = compare(published_control, candidate, True)
            published = {k: second[k] for k in ('setup_regressions', 'new_failing_families', 'other_timing_failures', 'pulse_failures', 'all_corner_check_vectors')}
            if any(published[k] for k in ('setup_regressions', 'new_failing_families', 'other_timing_failures', 'pulse_failures')):
                invalid.append('Candidate fails the original published hardware-baseline comparison')
    retained = timing_retain and not invalid and not pending and not timing_only
    verdict = 'RETAIN_FOR_COMBINATION_TEST' if retained else 'REJECT' if regressions or new_families or other_failures or ng['pulse_failures'] or invalid else 'PENDING_EVIDENCE' if pending else 'NO_GLOBAL_IMPROVEMENT'
    def metrics(root):
        rows = read_rows(root / 'closure_diagnostics/critical_path_metrics.tsv')
        rows = rows if rows else path_metrics(root)
        lookup = {r['directory']: '/'.join(r[k] for k in ('model', 'speed', 'voltage', 'temperature'))
                  for r in read_rows(root / 'timing_closure/corners.tsv')}
        return [{**r, 'corner': lookup[r['corner']]} for r in rows]
    old_paths = {(r['corner'], r['launch'], r['capture']): r for r in metrics(control)}
    new_paths = {(r['corner'], r['launch'], r['capture']): r for r in metrics(candidate)}
    paths = [{'identity': list(k), 'control': old_paths.get(k), 'candidate': new_paths.get(k),
              'identity_status': 'EXACT_PHYSICAL_NAME' if k in old_paths and k in new_paths else 'CORRESPONDENCE_REVIEW_REQUIRED'}
             for k in sorted(set(old_paths) | set(new_paths))]
    def resources(root):
        path = root / 'Groovy.fit.summary'
        if not path.exists(): return None
        values = {}
        for line in path.read_text().splitlines():
            if ':' in line:
                key, value = line.split(':', 1); values[key.strip()] = value.strip()
        return values
    def placements(root):
        return {r['source']: r['source_location'] for r in read_rows(root / 'closure_diagnostics/fanout_locations.tsv')}
    px, py = placements(control), placements(candidate)
    movement = [{'node': k, 'control_location': px.get(k), 'candidate_location': py.get(k)}
                for k in sorted(set(px) | set(py)) if px.get(k) != py.get(k)]
    return {'format': 'physical-comparison-v1', 'verdict': verdict, 'timing_vector_acceptable': timing_retain,
            'control_timing_pass': cg['timing_pass'], 'candidate_timing_pass': ng['timing_pass'],
            'setup_regressions': regressions, 'setup_improvements': improvements, 'new_failing_families': new_families,
            'other_timing_failures': other_failures, 'pulse_failures': ng['pulse_failures'],
            'rank_changes_not_automatic_regressions': rankings, 'invalid_experiment': invalid,
            'pending_acceptance': pending, 'endpoint_slack_distribution': endpoint_deltas,
            'all_corner_check_vectors': margins, 'critical_path_physical_differences': paths,
            'driver_placement_changes': movement, 'control_resources': resources(control), 'candidate_resources': resources(candidate),
            'published_baseline_comparison': published,
            'status': 'Physical timing, coverage and CRT hardware acceptance remain separate gates.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('control', type=Path); p.add_argument('candidate', type=Path)
    p.add_argument('--output', required=True, type=Path); p.add_argument('--timing-only', action='store_true')
    p.add_argument('--published-control', type=Path)
    p.add_argument('--cross-version', action='store_true')
    a = p.parse_args()
    if a.cross_version:
        write_json(a.output, compare_versions(a.control, a.candidate))
        print('Cross-version observations written; no endpoint-identity or compiler-only attribution')
        sys.exit(0)
    result = compare(a.control, a.candidate, a.timing_only, a.published_control)
    # Complete structured distribution is a compact TSV, not repeated JSON keys.
    from physical.diagnostics import table
    distribution = result.pop('endpoint_slack_distribution')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    path = a.output.with_name(a.output.stem + '_endpoint_slacks.tsv')
    fields = ['corner', 'to', 'control_slack', 'candidate_slack', 'delta_ns', 'control_clock_skew_ns', 'candidate_clock_skew_ns', 'control_data_delay_ns', 'candidate_data_delay_ns', 'identity_status']
    table(path, fields, [[r.get(k) for k in fields] for r in distribution])
    result['endpoint_slack_distribution'] = {'file': path.name, 'rows': len(distribution), 'sha256': digest(path.read_bytes())}
    write_json(a.output, result); print(result['verdict'])
