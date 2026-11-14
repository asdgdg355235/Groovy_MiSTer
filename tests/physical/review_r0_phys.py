#!/usr/bin/env python3
"""Review returned Q25 R0 exports offline. Never approves physical assignments."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tests/restart')]
from physical.graph import sha,normalize
from physical.run_r0_phys import validate_exports,BASE
from physical.recovery_analysis import selected_footprints
from map_evidence import extract
EXPORTER='9275020236af5f37068073b73f2b76c3cc534280'

def rows(path):
    with Path(path).open() as stream:yield from csv.DictReader(stream,delimiter='\t')

def root_witness(mapped,fitted,source):
    origin=[r for r in source if r['stage']=='pre_synthesis' and r['name']=='emu:emu|Add17'
            and r['source_file'].endswith('/Groovy.sv(1078)') and r['type']=='comb']
    if len(origin)!=1:raise ValueError('Root arithmetic source correspondence incomplete')
    map_edges=[r for r in mapped if r['direction']=='INPUT' and re.match(r'^emu:emu\|Add17~\d+$',r['node'])
               and re.match(r'^emu:emu\|vga:vga\|v_cnt\[\d+\]$',r['peer']) and r['peer_port']=='Q']
    if {r['peer'] for r in map_edges}!={f'emu:emu|vga:vga|v_cnt[{i}]' for i in range(16)}:raise ValueError('Mapped root increment lacks counter inputs')
    captures=[r for r in fitted if r['direction']=='INPUT' and r['port']=='D'
              and r['peer']=='emu:emu|Add17~5' and r['peer_port']=='SUMOUT']
    witnesses=[]
    for capture in captures:
        reg=capture['node']
        clock=[r for r in fitted if r['direction']=='INPUT' and r['node']==reg and r['port']=='CLK']
        consumers=[r for r in fitted if r['direction']=='OUTPUT' and r['node']==reg and r['port']=='Q']
        if len(clock)!=1 or not consumers:raise ValueError('Root capture needs actual CLK and Q consumers')
        witnesses.append({'D':capture,'CLK':clock[0],'Q_connections':consumers})
    consumers={r['peer'].split('~')[0] for w in witnesses for r in w['Q_connections']}
    if not {'emu:emu|Mult0','emu:emu|Add18'}<=consumers:raise ValueError('Root multiplier/parity consumers are incomplete')
    if not witnesses:raise ValueError('No fitted root capture')
    counter=[r for r in fitted if r['direction']=='INPUT' and r['node']=='emu:emu|vga:vga|v_cnt[15]']
    if not {'CLK','D'}<={r['port'] for r in counter}:raise ValueError('Fitted vertical counter D/CLK incomplete')
    return {'source_observation':origin[0],'mapped_counter_inputs':map_edges,
            'fitted_root_captures':witnesses,'counter_bit15_connections':counter,
            'scope':'Observed root increment and consumers. Not complete original-register ancestry or a retiming-assignment approval.'}

def review(output,destination):
    output=Path(output).resolve();destination=Path(destination).resolve()
    if destination.exists():raise ValueError('Review destination must be new')
    state=json.loads((output/'export_state.json').read_text())
    if state.get('exit_code')!=0 or state.get('stage')!='exports-complete-mapping-review-pending' or state.get('prepare_only'):
        raise ValueError('Not completed native R0 exports')
    if state.get('exporter_source_commit')!=EXPORTER or state['r0_provenance']['source_commit']!=BASE:
        raise ValueError('Wrong R0/exporter identity')
    if sha(output/'provenance.json')!=state['r0_provenance_sha256']:raise ValueError('R0 provenance changed')
    for rel,wanted in state['export_source_hashes'].items():
        content=subprocess.check_output(['git','show',EXPORTER+':'+rel],cwd=ROOT)
        if hashlib.sha256(content).hexdigest()!=wanted:raise ValueError('Unreviewed exporter bytes: '+rel)
    validate_exports(output)
    status=json.loads((output/'corrected_diagnostics/diagnostic_status.json').read_text())
    if not status.get('export_queries_complete') or status.get('unresolved_logical_bits')!=0:
        raise ValueError('Native diagnostics incomplete')
    destination.mkdir(parents=True)
    _,graph=normalize(output/'fanout_locations.tsv',destination,
                     output/'fanout_processed_sources.tsv',output/'fanout_export_status.tsv')
    if graph['errors'] or graph['raw_sha256']!=status['graph_normalization']['raw_sha256']:
        raise ValueError('Fresh graph accounting differs')
    relevant=lambda r: bool(re.match(r'^emu:emu\|(Add17|Add18|Mult0|PoC_px_frameskip|vga:vga\|v_cnt)',r['node']))
    mapped=[r for r in rows(output/'atom_ports_map.tsv') if relevant(r)]
    fitted=[r for r in rows(output/'atom_ports_cmp.tsv') if relevant(r)]
    source=[r for r in rows(output/'source_correspondence.tsv') if r['name']=='emu:emu|Add17']
    witness=root_witness(mapped,fitted,source)
    footprints=selected_footprints(output/'fanout_locations.tsv',destination/'selected_loads.tsv')
    paths={}
    for corner in ['corner_01','corner_02']:
        paths[corner]={label:extract(output/f'recovery_paths/{corner}/{label}_setup.txt',False)[:2]
                       for label in ['vga_root','root_consumers','lz4_window_capture','lz4_window_counter','crt_hb','crt_advance']}
    names=['export_state.json','provenance.json','source_correspondence.tsv','atom_ports_map.tsv',
           'atom_ports_cmp.tsv','fanout_locations.tsv','recovery_paths/endpoints.tsv',
           'recovery_paths/filters.tsv','recovery_paths/query_errors.tsv',
           'corrected_diagnostics/diagnostic_status.json']
    result={'format':'q25-r0-physical-review-v1','r0_source_commit':BASE,'exporter_commit':EXPORTER,
            'file_hashes':{n:sha(output/n) for n in names},'graph':graph,'root_witness':witness,
            'selected_driver_summary':{k:{a:b for a,b in v.items() if a!='destination_locations'} for k,v in footprints.items()},
            'paths':paths,'physical_assignment_approved':False,'C1':'BLOCKED_LEGAL_SITE_AND_ASSIGNMENT_SCOPE',
            'V2_source_scope':'Root next-line operand only; no counter or register-control change',
            'coverage_release_qualified':False,'timing_closure':False}
    (destination/'review.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output_files',type=Path);p.add_argument('destination',type=Path)
    a=p.parse_args();review(a.output_files,a.destination);print('PASS: physical observations reviewed; placement/retiming assignment support remains unapproved')
