#!/usr/bin/env python3
"""Offline R0/V1 comparison. Native identities stay local to each compilation."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'restart'))
from map_evidence import extract

R0 = '3b8d1edb63f2d2fed05d23323c3ba1ae93eeed1a'
V1 = '26cb6b9b7528f14a7cbeed92740fa28c2c23fa1e'

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
    return h.hexdigest()

def rows(path):
    with path.open() as stream: yield from csv.DictReader(stream, delimiter='\t')

def window_input(row):
    return 'lz4:lz4|' in row['to'] and 'window_rtl_0|' in row['to'] and 'porta_datain_reg' in row['to']

def endpoint_group(row):
    sink = row['to']
    return ('lz4-window-write' if window_input(row) else 'crt-read' if 'packed_ram[' in sink
            else 'crt-row' if 'u_vsize' in sink else 'vga-root' if 'Add17' in sink else 'other')

def analyze(build, source):
    build = Path(build)
    provenance = json.loads((build/'provenance.json').read_text())
    if provenance['source_commit'] != source or provenance.get('compiler_profile') != 'q25':
        raise ValueError('Wrong source/compiler provenance')
    report_hashes = {}
    def tracked(rel):
        path = build/rel
        if not path.is_file(): raise ValueError('Missing evidence: '+rel)
        report_hashes[rel] = sha(path)
        return path
    corners = list(rows(tracked('timing_closure/corners.tsv')))
    if len(corners) != 8 or len({r['name'] for r in corners}) != 8:
        raise ValueError('Expected eight distinct timing corners')
    summary = list(rows(tracked('timing_closure/endpoint_summary.tsv')))
    data = {}
    for corner in corners:
        name = corner['directory']
        inventory = list(rows(tracked(f'timing_closure/{name}/all_setup_endpoints.tsv')))
        if len({r['to'] for r in inventory}) != len(inventory): raise ValueError('Duplicate endpoints')
        negative = [r for r in inventory if float(r['slack_ns']) < 0]
        table = next(r for r in summary if r['corner']==name and r['check']=='setup')
        if int(table['failing_endpoints']) != len(negative): raise ValueError('Incomplete endpoint inventory')
        if abs(sum(float(r['slack_ns']) for r in negative)-float(table['endpoint_TNS_ns'])) > .00001:
            raise ValueError('Endpoint TNS mismatch')
        windows = sorted((r for r in inventory if window_input(r)), key=lambda r:float(r['slack_ns']))
        if not windows: raise ValueError('Missing window input capture inventory')
        details = {}
        for label in ['lz4_counter_launch','hb','bank_1_even','vga','negative_setup_paths']:
            rel = f'timing_closure/{name}/'+(label+'.txt' if label=='negative_setup_paths' else label+'_setup.txt')
            paths = extract(tracked(rel), violations_only=False)
            # Detail exports are bounded observations, never the complete endpoint inventory.
            details[label] = [{k:v for k,v in p.items() if k not in ('family','source_mapping')}
                              for p in paths[:8]]
        groups = {}
        for row in negative:
            key = endpoint_group(row); groups[key] = groups.get(key,0)+1
        data[name] = {'corner':corner,'setup_summary':table,'negative_families':groups,
                      'window_input_captures':len(windows),'worst_window_input':windows[0],
                      'window_input_failures':sum(float(r['slack_ns'])<0 for r in windows),
                      'detailed_observations':details}
    return {'source_commit':source, 'provenance_sha256':sha(build/'provenance.json'),
            'hardware_hashes':provenance['hardware_hashes'],'generated_input':provenance['generated_input'],
            'corners':data,'report_hashes':report_hashes}

def selected_footprints(raw, output):
    """Keep every observed pin-level arc for selected drivers, with exact dedup."""
    selected = {}
    groups = ('crt_read_1_even_bit3|combout', 'local_ra_even[10]~2|combout',
              'wa[3]~3|combout', 'line_begin~0', '|vga|hb', '|lz4|block_read_total')
    header = None
    for row in rows(Path(raw)):
        header = list(row)
        if any(token in row['source'] for token in groups):
            selected.setdefault(row['source'], {})[tuple(row[k] for k in header)] = row
    summary = {}
    with Path(output).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=header, delimiter='\t');writer.writeheader()
        for source, unique in sorted(selected.items()):
            arcs = list(unique.values())
            expected = {int(r['expected_fanout']) for r in arcs}
            if expected != {len(arcs)}:raise ValueError('Incomplete selected driver: '+source)
            locations = sorted({r['destination_location'] for r in arcs})
            summary[source] = {'source_location':arcs[0]['source_location'],
                'source_type':arcs[0]['source_type'],'unique_pin_arcs':len(arcs),
                'destination_locations':locations,'location_count':len(locations),
                'scope':'Observed load coordinates, not routed length or legal placement sites'}
            writer.writerows(arcs)
    return summary

def compare(r0,v1,destination,archives=()):
    destination = Path(destination)
    if destination.exists(): raise ValueError('Comparison output must be new')
    old,new = analyze(r0,R0),analyze(v1,V1)
    if old['generated_input']['sha256'] != new['generated_input']['sha256']:
        raise ValueError('Generated inputs differ')
    changed = sorted(k for k in old['hardware_hashes'].keys() | new['hardware_hashes'].keys()
                     if old['hardware_hashes'].get(k) != new['hardware_hashes'].get(k))
    if changed != ['rtl/vga.v']: raise ValueError('Unexpected hardware changes: '+repr(changed))
    destination.mkdir(parents=True)
    result = {'format':'q25-v1-rejection-v1','decision':'REJECT_V1_KEEP_R0',
              'hardware_changes':changed,'r0':old,'v1':new,
              'original_archives':{Path(a).name:sha(a) for a in archives},
              'limits':['Endpoint groups are comparisons, not cross-build register correspondence.',
                        'Bounded path reports do not establish all write-address/enable path details.',
                        'Positive R0 window-input slack is measured from complete endpoint inventories.',
                        'A physical regression in unchanged LZ4 does not prove a new decoder logic defect.',
                        'C1/V2 remain blocked pending R0 physical correspondence and installed assignment scope.']}
    (destination/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    # Keep complete physical connections for both bank-selection layers and window ports.
    for label,build in [('r0',Path(r0)),('v1',Path(v1))]:
        src=build/'closure_diagnostics/atom_ports_cmp.tsv'
        with (destination/(label+'_bank_window_ports.tsv')).open('w',newline='') as out:
            it=rows(src); first=next(it); writer=csv.DictWriter(out,fieldnames=list(first),delimiter='\t');writer.writeheader()
            import itertools
            for row in itertools.chain([first],it):
                if any(s in row['node']+' '+row['peer'] for s in ('window_rtl_0','packed_ram[1].','crt_read_1_even','local_ra_even','next_aslot')):
                    writer.writerow(row)
        result.setdefault('physical_subset_hashes',{})[label]={'raw_atoms_sha256':sha(src),'derived_sha256':sha(destination/(label+'_bank_window_ports.tsv'))}
    result['selected_footprints']={}
    for label,build in [('r0',Path(r0)),('v1',Path(v1))]:
        target=destination/(label+'_selected_fanout.tsv')
        result['selected_footprints'][label]=selected_footprints(build/'closure_diagnostics/fanout_locations.tsv',target)
        result['physical_subset_hashes'][label]['selected_fanout_sha256']=sha(target)
    (destination/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('r0',type=Path);p.add_argument('v1',type=Path);p.add_argument('output',type=Path);p.add_argument('--archive',action='append',default=[])
    a=p.parse_args();r=compare(a.r0,a.v1,a.output,a.archive);print(r['decision'])
