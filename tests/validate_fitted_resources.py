#!/usr/bin/env python3
"""Record resource, RAM-type and video-clock gates from fresh vendor reports."""
import csv
import json
from pathlib import Path
import re
import sys


def inspect(root):
    root=Path(root)
    summary=(root/'Groovy.fit.summary').read_text()
    # Quartus 17 emits degree symbols using a legacy locale encoding.
    fit=(root/'Groovy.fit.rpt').read_text(errors='replace')
    failures=[]
    if not re.search(r'Fitter Status\s*:\s*Successful',summary): failures.append('Unsuccessful fitter')
    if not re.search(r'Device\s*:\s*5CSEBA6U23I7\b',summary): failures.append('Unexpected device')
    ram=re.search(r'Total RAM Blocks\s*:\s*([\d,]+)\s*/\s*([\d,]+)',summary)
    mlab=re.search(r';\s*Total MLAB memory bits\s*;\s*([\d,]+)\s*;',fit, re.I)
    if not ram or not mlab: raise ValueError('Missing RAM resource counts')
    used,capacity=(int(v.replace(',','')) for v in ram.groups())
    bits=int(mlab[1].replace(',',''))
    if used>553 or capacity!=553: failures.append('M10K device capacity exceeded or changed')
    if bits!=491520: failures.append('MLAB storage changed')
    banks={}
    for row in csv.DictReader((root/'crt_local_drivers_cmp.tsv').read_text().splitlines(),delimiter='\t'):
        if row['kind']!='RAM_ADDRESS' or row['port']!='PORTBADDR': continue
        name=row['name']; match=re.search(r'packed_ram\[(\d+)\]\.(even|odd)_ram',name)
        if match:
            kind='M10K' if re.search(r'altsyncram:block_ram|\bM10K\b', name, re.I) else 'MLAB' if re.search(r'altdpram:distributed|\bMLAB\b', name, re.I) else 'unknown'
            banks.setdefault('.'.join(match.groups()),set()).add(kind)
    expected={f'{n}.{p}':{'M10K' if n==2 else 'MLAB'} for n in range(3) for p in ('even','odd')}
    if banks!=expected: failures.append('Six-bank RAM implementation changed or unrecognized')
    clocks=(root/'timing_closure/clocks.txt').read_text()
    periods=[]
    for line in clocks.splitlines():
        cols=[c.strip() for c in line.split(';')]
        if len(cols)>3 and 'emu|pll|' in cols[1] and 'counter[0].output_counter|divclk' in cols[1]:
            periods.append(cols[3])
    if periods!=['12.081']: failures.append('Video clock is missing, ambiguous or changed')
    return {'resource_clock_pass':not failures,'failures':failures,'m10k_used':used,
            'm10k_capacity':capacity,'mlab_bits':bits,'banks':{k:sorted(v) for k,v in banks.items()},
            'video_period_ns':periods,
            'note':'RAM port behavior/latency needs functional regression; I/O/CDC and timing are separate gates.'}


if __name__=='__main__':
    root=Path(sys.argv[1]); result=inspect(root)
    (root/'resource_clock_gate.json').write_text(json.dumps(result,indent=2)+'\n')
    print('RESOURCE/CLOCK PASS' if result['resource_clock_pass'] else 'RESOURCE/CLOCK FAILED: inspect resource_clock_gate.json')
