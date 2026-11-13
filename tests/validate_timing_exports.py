#!/usr/bin/env python3
"""Reject incomplete eight-corner results and record timing gate failures."""
from pathlib import Path
import csv
import json
import re
import sys
import math

def contains_gap(path):
    pattern=re.compile(rb'TRUNCATED|REPORT_CAPPED|OMITTED_BYTES',re.I)
    tail=b''
    with Path(path).open('rb') as stream:
        while block:=stream.read(1024*1024):
            data=tail+block
            if pattern.search(data):return True
            tail=data[-32:]
    return False


def validate(root, strict_families=True):
    root = Path(root)
    distribution=root/'endpoint_distribution_format.txt'
    if distribution.exists() and distribution.read_text().strip()!='physical-endpoints-v1':
        raise ValueError('Unsupported endpoint distribution format')
    corners = list(csv.DictReader((root/'corners.tsv').read_text().splitlines(), delimiter='\t'))
    expected = {(m,t) for m in ('slow','fast') for t in ('-40','0','85','100')}
    if len(corners)!=8 or {(c['model'], c['temperature']) for c in corners}!=expected:
        raise ValueError('Missing or unexpected operating corners')
    if any(c.get('voltage')!='1100' for c in corners):
        raise ValueError('Unexpected or missing operating voltage')
    rows = list(csv.DictReader((root/'endpoint_summary.tsv').read_text().splitlines(), delimiter='\t'))
    wanted = {(c['directory'], k) for c in corners for k in ('setup','hold','recovery','removal')}
    if len(rows)!=32 or {(r['corner'],r['check']) for r in rows}!=wanted:
        raise ValueError('Missing/duplicate endpoint summaries')
    failed=[]
    for row in rows:
        tns=float(row['endpoint_TNS_ns']);count=int(row['failing_endpoints'])
        if not math.isfinite(tns) or count<0: raise ValueError('Invalid endpoint summary')
        if row['worst_slack_ns']=='NA':
            # Recovery/removal may have no applicable paths; setup/hold cannot.
            if row['check'] in ('setup','hold'): raise ValueError('Unanalyzed setup/hold')
        else:
            wns=float(row['worst_slack_ns'])
            if not math.isfinite(wns): raise ValueError('Invalid worst slack')
            if wns<0 or tns<0 or count!=0: failed.append(row)
        directory=root/row['corner']
        for name in (f"negative_{row['check']}_endpoints.tsv",f"negative_{row['check']}_paths.txt",f"worst_{row['check']}.txt"):
            if not (directory/name).is_file(): raise ValueError('Missing '+str(directory/name))
        entries=list(csv.DictReader((directory/f"negative_{row['check']}_endpoints.tsv").read_text().splitlines(),delimiter='\t'))
        if len(entries)!=int(row['failing_endpoints']): raise ValueError('Endpoint inventory count mismatch')
        slacks=[float(e['slack_ns']) for e in entries]
        if len({e['to'] for e in entries})!=len(entries): raise ValueError('Duplicate failing endpoint')
        if any(not math.isfinite(s) or s>=0 for s in slacks): raise ValueError('Invalid negative endpoint slack')
        if abs(sum(slacks)-float(row['endpoint_TNS_ns']))>0.0000011: raise ValueError('Endpoint TNS mismatch')
        if slacks and (row['worst_slack_ns']=='NA' or abs(min(slacks)-float(row['worst_slack_ns']))>0.0000011):
            raise ValueError('Endpoint WNS mismatch')
        if not slacks and row['worst_slack_ns']!='NA' and float(row['worst_slack_ns'])<0:
            raise ValueError('Missing failing endpoint inventory')
        if contains_gap(directory/f"negative_{row['check']}_paths.txt"): raise ValueError('Incomplete negative-path export')
        if (root/'endpoint_distribution_format.txt').exists():
            full=directory/f"all_{row['check']}_endpoints.tsv"
            if not full.is_file():raise ValueError('Missing complete endpoint distribution')
            complete=list(csv.DictReader(full.read_text().splitlines(),delimiter='\t'))
            if len({e['to'] for e in complete})!=len(complete):raise ValueError('Duplicate complete endpoint')
            if any(not math.isfinite(float(e['slack_ns'])) for e in complete):raise ValueError('Invalid complete endpoint slack')
            actual={e['to']:float(e['slack_ns']) for e in complete if float(e['slack_ns'])<0}
            if actual!={e['to']:float(e['slack_ns']) for e in entries}:raise ValueError('Complete/negative endpoint inventories disagree')
            if complete and abs(min(float(e['slack_ns']) for e in complete)-float(row['worst_slack_ns']))>0.0000011:
                raise ValueError('Complete endpoint WNS mismatch')
            if row['check'] in ('setup','hold') and not complete:raise ValueError('Empty complete setup/hold distribution')
    if strict_families:
        for name in ('clocks.txt','constraints.txt','ignored_constraints.txt','check_timing.txt','unconstrained.txt','filters.tsv'):
            if not (root/name).is_file(): raise ValueError('Missing '+name)
        for c in corners:
            for name in ('clock_transfers.txt','wcol_setup.txt','hb_setup.txt','poc_v_setup.txt','vga_setup.txt','delta_index_setup.txt','delta_framebuffer_setup.txt','lz4_counters_setup.txt','lz4_counter_launch_setup.txt','lz4_compressed_setup.txt'):
                if not (root/c['directory']/name).is_file(): raise ValueError('Missing '+str(root/c['directory']/name))
    # New runner requires the independent complete-prefix pulse certificate.
    modern=(root/'report_format.txt').exists()
    if modern and (root/'report_format.txt').read_text().strip()!='restart-v1':
        raise ValueError('Unsupported timing report format')
    pulse_failures=[]
    for c in corners:
        f=root/c['directory']/'min_pulse_width.txt'
        text=f.read_text(errors='replace')
        if re.search(r'TRUNCATED|REPORT_CAPPED|OMITTED_BYTES',text,re.I): raise ValueError('Incomplete pulse export')
        # Summary rows begin with Slack; preserve the full vendor report too.
        values=[float(m) for m in re.findall(r'^;\s*(-?\d+\.\d+)\s*;',text,re.M)]
        if not values: raise ValueError('No pulse-width checks parsed: '+str(f))
        if modern:
            folder=root/c['directory']
            pulse=list(csv.DictReader((folder/'pulse_summary.tsv').read_text().splitlines(),delimiter='\t'))
            if len(pulse)!=1: raise ValueError('Missing pulse certificate')
            p=pulse[0]
            if p['complete']!='1' or int(p['returned'])!=len(values) or int(p['failing'])!=sum(v<0 for v in values) or float(p['wns_ns'])!=min(values):
                raise ValueError('Pulse summary does not match certificate')
            if values!=sorted(values) or float(p['last_slack_ns'])!=values[-1] or int(p['returned'])>int(p['requested']):
                raise ValueError('Invalid sorted pulse prefix')
            if not (int(p['returned'])<int(p['requested']) or float(p['last_slack_ns'])>=0):
                raise ValueError('Pulse prefix omits possible failures')
            if not (folder/'negative_pulse_paths.txt').exists(): raise ValueError('Missing failing pulse details')
        if min(values)<0: pulse_failures.append({'corner':c['directory'],'slack':min(values)})
    return {'timing_pass': not failed and not pulse_failures, 'corners':8,
            'failed_checks':failed,'pulse_failures':pulse_failures,
            'qualification_note':'Timing status only; I/O, CDC, RAM/driver audits and hardware acceptance are separate gates.'}


if __name__=='__main__':
    root=Path(sys.argv[1]); result=validate(root)
    (root/'timing_gate.json').write_text(json.dumps(result,indent=2)+'\n')
    print('TIMING PASS' if result['timing_pass'] else 'TIMING FAILED: inspect timing_gate.json')
