"""Strict R0-relative acceptance, with complete endpoint distributions. Offline."""
import csv
import json
from pathlib import Path

from physical.q25_experiments import CONTROL, output_root, validate_baseline, checked_path
from physical.upper_selection import sha, bank_prefix
from physical.diagnostics import family, path_metrics
from validate_timing_exports import validate


def read(path):
    with Path(path).open() as f: return list(csv.DictReader(f, delimiter='\t'))


def path_family(source, sink):
    # Preserve direction: the V2 reverse control->VGA failure was not the old
    # VGA->root launch path merely becoming worst under a different name.
    if '|state[' in source and '|vga:vga|' in sink: return 'modeline-to-vga'
    return family(source, sink)


def timing_vectors(root):
    gate = validate(root / 'timing_closure')
    corners = {c['directory']: '/'.join(c[k] for k in ('model','speed','voltage','temperature'))
               for c in read(root / 'timing_closure/corners.tsv')}
    vectors = {}
    for r in read(root / 'timing_closure/endpoint_summary.tsv'):
        key = (corners[r['corner']], r['check'])
        if key in vectors: raise ValueError('Duplicate corner/check')
        vectors[key] = {'directory': r['corner'], 'wns': None if r['worst_slack_ns']=='NA' else float(r['worst_slack_ns']),
                        'tns': float(r['endpoint_TNS_ns']), 'count': int(r['failing_endpoints'])}
    return gate, vectors


def compare(control, candidate, destination, review=None):
    control, candidate, destination = output_root(control), output_root(candidate), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    identity = validate_baseline(control)
    cg, old = timing_vectors(control); ng, new = timing_vectors(candidate)
    if set(old) != set(new): raise ValueError('Different corner/check coverage')
    if not all((candidate/'timing_closure'/r['directory']/f'all_{k[1]}_endpoints.tsv').is_file() for k,r in new.items()):
        raise ValueError('Missing complete candidate endpoint distributions')
    vectors, regressions, improvements, ancillary = [], [], [], []
    new_families = []; prior = set()
    for (corner, check), r in old.items():
        if check == 'setup':
            for e in read(control/'timing_closure'/r['directory']/'negative_setup_endpoints.tsv'):
                prior.add(path_family(e['from'], e['to']))
    dist = destination / 'endpoint_comparison.tsv'
    changed_names = 0; targeted = []
    with dist.open('w', newline='') as f:
        w = csv.writer(f, delimiter='\t', lineterminator='\n')
        w.writerow(['corner','check','capture','R0_launch','candidate_launch','R0_slack_ns','candidate_slack_ns','delta_ns','identity'])
        for key in sorted(old):
            a,b = old[key],new[key]; corner,check=key
            vectors.append({'corner':corner,'check':check,'R0_WNS_ns':a['wns'],'candidate_WNS_ns':b['wns'],
                            'R0_TNS_ns':a['tns'],'candidate_TNS_ns':b['tns'],
                            'R0_failing':a['count'],'candidate_failing':b['count']})
            if check == 'setup':
                if a['wns'] is None or b['wns'] is None: raise ValueError('Unanalyzed setup')
                if b['wns'] < a['wns'] or b['tns'] < a['tns'] or b['count'] > a['count']: regressions.append(corner)
                if a['count'] and (b['wns'] > a['wns'] or b['tns'] > a['tns'] or b['count'] < a['count']): improvements.append(corner)
            elif b['count'] or b['tns'] < 0 or (b['wns'] is not None and b['wns']<0): ancillary.append('/'.join(key))
            left = {e['to']:e for e in read(control/'timing_closure'/a['directory']/f'all_{check}_endpoints.tsv')}
            right = {e['to']:e for e in read(candidate/'timing_closure'/b['directory']/f'all_{check}_endpoints.tsv')}
            for sink in sorted(set(left)|set(right)):
                x,y=left.get(sink),right.get(sink)
                xs=float(x['slack_ns']) if x else None;ys=float(y['slack_ns']) if y else None
                changed_names += not (x and y)
                w.writerow([corner,check,sink,x['from'] if x else '',y['from'] if y else '',xs,ys,
                            ys-xs if x and y else '', 'EXACT_NAME' if x and y else 'CORRESPONDENCE_REVIEW_REQUIRED'])
                if check=='setup' and y and ys<0 and path_family(y['from'],sink) not in prior:
                    new_families.append({'corner':corner,'launch':y['from'],'capture':sink,'family':path_family(y['from'],sink)})
                if check=='setup' and x and y and xs<0 and ys>xs:
                    targeted.append({'corner':corner,'capture':sink,'R0_launch':x['from'],'candidate_launch':y['from'],'R0_slack_ns':xs,'candidate_slack_ns':ys})
    invalid=[];pending=[]
    cp=json.loads((control/'provenance.json').read_text());p=json.loads((candidate/'provenance.json').read_text())
    spec=json.loads((candidate/'q25_experiment.json').read_text())
    if spec['control'] != identity: invalid.append('Control evidence changed since candidate preparation')
    if cp['hardware_hashes'] != p['hardware_hashes'] or p.get('compiler_profile')!='q25': invalid.append('Hardware/compiler profile changed')
    if p.get('generated_input') != cp.get('generated_input'): invalid.append('Generated input changed')
    from physical.control import verify_version
    for tool in ('quartus_sh','quartus_map','quartus_fit','quartus_asm','quartus_sta','quartus_cdb'):
        verify_version((candidate/(tool+'_version.txt')).read_text(),'q25')
    state=json.loads((candidate/'build_state.json').read_text())
    if not state.get('compilation_completed') or not state.get('physical_exports_complete'): invalid.append('Incomplete compilation or physical diagnostics')
    for phase in ('before_map','before_fit'):
        if not json.loads((candidate/f'input_gate_{phase}.json').read_text()).get('pass'): invalid.append('Source/assignment gate failed')
    resource=json.loads((candidate/'resource_clock_gate.json').read_text())
    if not resource.get('resource_clock_pass') or resource.get('mlab_bits')!=491520 or resource.get('m10k_used',554)>553:
        invalid.append('Resource/clock architecture failed')
    if not json.loads((candidate/'q25_window_ram_gate.json').read_text()).get('embedded_ram_inferred'): invalid.append('LZ4 window inference failed')
    local=json.loads((candidate/'crt_local_drivers_cmp.json').read_text())
    for bit in range(5):
        drivers=local.get('low_read_address_bits',{}).get(str(bit),[])
        if len(drivers)!=6 or any(len(r['banks'])!=1 for r in drivers): invalid.append('Low-bit separation failed')
    application=json.loads((candidate/'application_cmp.json').read_text())
    if not application.get('target_gate_pass'): invalid.append('Physical factor not applied')
    for factor in spec['factors']:
        if factor in ('U10','U9') and not any(r['experiment']==factor and r.get('split_verified') for r in application.get('copies',[])):
            invalid.append('Missing required upper split: '+factor)
    # Preserve host controls rather than attributing environment drift to RTL.
    for key in ('host','cpu_count','affinity','parallel_setting'):
        a=json.loads((control/'host_environment.json').read_text());b=json.loads((candidate/'host_environment.json').read_text())
        if a.get(key)!=b.get(key): invalid.append('Host control changed: '+key)
    if not review:
        pending.append('Targeted path correspondence and post-fit cycle/mechanism review required')
    else:
        review=json.loads(Path(review).read_text())
        if review.get('candidate_provenance_sha256')!=sha(candidate/'provenance.json') or review.get('control_provenance_sha256')!=sha(control/'provenance.json'):
            invalid.append('Review belongs to a different candidate/control')
        if not review.get('reviewed_by') or not all(review.get(k) is True for k in ('mechanism_verified','functional_cycles_verified')):
            pending.append('Incomplete physical/cycle review')
        for rel,wanted in review.get('evidence',{}).items():
            if sha(checked_path(candidate,rel))!=wanted:invalid.append('Changed review evidence: '+rel)
        if not review.get('evidence'):pending.append('No hashed review evidence')
        pairs=review.get('targeted_improvements',[])
        # Every factor needs an actual failing control endpoint and an observed
        # improved candidate endpoint. Renamed endpoints require the review's
        # separate correspondence evidence, not a fabricated disappearance.
        for factor in spec['factors']:
            pairs_for_factor=[r for r in pairs if r.get('factor')==factor]
            valid=False
            for pair in pairs_for_factor:
                dirs={r['name']:r['directory'] for r in read(control/'timing_closure/corners.tsv')}
                if pair.get('corner') not in dirs:continue
                oc=dirs[pair['corner']]
                nd={r['name']:r['directory'] for r in read(candidate/'timing_closure/corners.tsv')}[pair['corner']]
                a=next((r for r in read(control/'timing_closure'/oc/'all_setup_endpoints.tsv') if r['to']==pair.get('control_capture')),None)
                b=next((r for r in read(candidate/'timing_closure'/nd/'all_setup_endpoints.tsv') if r['to']==pair.get('candidate_capture')),None)
                if not a or not b or float(a['slack_ns'])>=0 or float(b['slack_ns'])<=float(a['slack_ns']):continue
                if factor in ('U10','U9'):
                    from physical.upper_selection import SPECS
                    s=SPECS[factor]
                    if bank_prefix(s['part'],s['parity']) not in a['to'] or bank_prefix(s['part'],s['parity']) not in b['to']:continue
                if not pair.get('correspondence_explanation'):continue
                valid=True
            if not valid: pending.append('No verified targeted failing-path improvement: '+factor)
    if regressions or new_families or ancillary or ng['pulse_failures'] or invalid:
        status='REJECTED'
    elif not improvements: status='REJECTED_NO_GLOBAL_IMPROVEMENT'
    elif pending: status='BLOCKED_REVIEW'
    else: status='ACCEPTED'
    result={'status':status,'timing_pass':ng['timing_pass'],'experiment':spec['experiment'],
            'source_commit':p['source_commit'],'compiler_profile':p['compiler_profile'],
            'setup_regressions':regressions,'improved_slow_corners':improvements,'new_failing_families':new_families,
            'ancillary_failures':ancillary,'pulse_failures':ng['pulse_failures'],'invalid':invalid,'pending':pending,
            'vectors':vectors,'endpoint_distribution':{'file':dist.name,'sha256':sha(dist),'unmatched_endpoint_records':changed_names},
            'critical_paths':path_metrics(candidate),'resources':resource,'application':application,
            'qualification':'Timing/experiment retention only. I/O coverage and CRT hardware acceptance remain separate.'}
    (destination/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
