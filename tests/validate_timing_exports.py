#!/usr/bin/env python3
"""Reject incomplete eight-corner results and record timing gate failures."""
from pathlib import Path
import csv
import json
import re
import sys


def validate(root, strict_families=True):
    root = Path(root)
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
        if row['worst_slack_ns']=='NA':
            # Recovery/removal may have no applicable paths; setup/hold cannot.
            if row['check'] in ('setup','hold'): raise ValueError('Unanalyzed setup/hold')
        elif float(row['worst_slack_ns'])<0 or float(row['endpoint_TNS_ns'])<0 or int(row['failing_endpoints'])!=0:
            failed.append(row)
        directory=root/row['corner']
        for name in (f"negative_{row['check']}_endpoints.tsv",f"negative_{row['check']}_paths.txt",f"worst_{row['check']}.txt"):
            if not (directory/name).is_file(): raise ValueError('Missing '+str(directory/name))
        entries=list(csv.DictReader((directory/f"negative_{row['check']}_endpoints.tsv").read_text().splitlines(),delimiter='\t'))
        if len(entries)!=int(row['failing_endpoints']): raise ValueError('Endpoint inventory count mismatch')
        path_text=(directory/f"negative_{row['check']}_paths.txt").read_text(errors='replace')
        if 'truncat' in path_text.lower(): raise ValueError('Truncated negative path export')
    if strict_families:
        for name in ('clocks.txt','constraints.txt','ignored_constraints.txt','check_timing.txt','unconstrained.txt','filters.tsv'):
            if not (root/name).is_file(): raise ValueError('Missing '+name)
        for c in corners:
            for name in ('clock_transfers.txt','wcol_setup.txt','hb_setup.txt','poc_v_setup.txt','vga_setup.txt','delta_index_setup.txt','delta_framebuffer_setup.txt','lz4_counters_setup.txt','lz4_counter_launch_setup.txt','lz4_compressed_setup.txt'):
                if not (root/c['directory']/name).is_file(): raise ValueError('Missing '+str(root/c['directory']/name))
    pulse_failures=[]
    version=(root/'report_format.txt').read_text().strip() if (root/'report_format.txt').is_file() else None
    if version not in (None,'compact-v2'): raise ValueError('Unknown timing report format')
    compact=version=='compact-v2'
    for c in corners:
        f=root/c['directory']/'min_pulse_width.txt'
        text=f.read_text()
        if 'truncat' in text.lower(): raise ValueError('Truncated pulse-width export')
        # Summary rows begin with Slack; preserve the full vendor report too.
        values=[float(m) for m in re.findall(r'^;\s*(-?\d+\.\d+)\s*;',text,re.M)]
        if not values: raise ValueError('No pulse-width checks parsed: '+str(f))
        if compact:
            if not (root/c['directory']/'min_pulse_coverage.tsv').is_file(): raise ValueError('Missing pulse coverage')
            coverage=list(csv.DictReader((root/c['directory']/'min_pulse_coverage.tsv').read_text().splitlines(),delimiter='\t'))
            if len(coverage)!=1 or coverage[0]['complete_negative_inventory']!='1': raise ValueError('Incomplete pulse inventory')
            row=coverage[0]
            if int(row['exported_checks'])!=len(values) or int(row['negative_checks'])!=sum(v<0 for v in values) or float(row['worst_slack_ns'])!=min(values):
                raise ValueError('Pulse coverage count/slack mismatch')
            details=(root/c['directory']/'negative_min_pulse_paths.txt').read_text()
            if 'truncat' in details.lower(): raise ValueError('Truncated negative pulse paths')
        if min(values)<0: pulse_failures.append({'corner':c['directory'],'slack':min(values)})
    return {'timing_pass': not failed and not pulse_failures, 'corners':8,
            'failed_checks':failed,'pulse_failures':pulse_failures,
            'qualification_note':'Timing status only; I/O, CDC, RAM/driver audits and hardware acceptance are separate gates.'}


if __name__=='__main__':
    root=Path(sys.argv[1]); result=validate(root)
    (root/'timing_gate.json').write_text(json.dumps(result,indent=2)+'\n')
    print('TIMING PASS' if result['timing_pass'] else 'TIMING FAILED: inspect timing_gate.json')
