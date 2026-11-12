#!/usr/bin/env python3
"""Extract supplied TimeQuest paths, not a replacement for a fitted netlist.

Usage: map_evidence.py HPS_OUTPUT_FILES NEWER_OUTPUT_FILES OUTPUT_JSON
No Quartus commands. Generated names remain physical names in this inventory.
"""
from pathlib import Path
import csv,hashlib,json,re,sys

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def table(path):return list(csv.DictReader(path.read_text().splitlines(),delimiter='\t'))
def extract(path):
 result=[]
 for block in re.split(r'(?m)^Path #\d+: ',path.read_text())[1:]:
  if '(VIOLATED)' not in block.splitlines()[0]:continue
  rows=[[c.strip() for c in line.split(';')[1:-1]] for line in block.splitlines() if line.startswith(';')]
  props={r[0]:r[1] for r in rows if len(r)==2}
  stats={r[0]:r for r in rows if len(r)==7}
  data=False;cell_delay=None;routing_delay=None;active=False;cells=[];ports=[]
  for r in rows:
   if len(r)==7 and r[0]=='Data':data=True
   elif len(r)==7 and r[0]=='Required Path':data=False
   if data and len(r)==7 and r[0]=='Cell':cell_delay=float(r[3])
   if data and len(r)==7 and r[0]=='Routing Element':routing_delay=float(r[3])
   if len(r)==7 and r[-1]=='data path':active=True;continue
   if active and len(r)==1 and 'Data Required Path' in r[0]:active=False
   if active and len(r)==7 and r[3] in ('IC','CELL'):
    item={'type':r[3],'fanout':int(r[4]),'location':r[5],'node':r[6]}
    ports.append(item)
    if r[3]=='CELL':cells.append(item)
  launch=props['From Node'];capture=props['To Node']
  if 'PoC_lz4_delta_index' in launch:
   family='delta-selection';mapping='Confirmed selector/byte-add/decode cone; baseline buffer read and unchanged LZ4 byte additions reach r_vram_in2.'
  elif 'PoC_V' in launch:
   family='vga-retimed';mapping='Partial: VGA arithmetic/comparator cells precede root Add17 carry chain. Ultimate RTL capture is unresolved; Add17 is not assumed to be V_total or field height.'
  elif 'dv_hs1' in capture:
   family='sync-retimed';mapping='Partial: hb_d/line qualification/tag compare/control reaches packed delay RAM. Physical RAM bit is not proof that the HS bit itself changes; sys_top capture and sync delays are preserved.'
  elif 'packed_ram' in capture:
   family='crt-read';mapping='Confirmed read-address/MLAB/output cone. Generated register aliases and RAM output packing remain physical artifacts.'
  else:
   family='row-retimed';mapping='Partial: delay_lines comparison/output qualification feeds position mux/Add1 carry then retimed advance_rows/Add2 capture, not a literal advance_rows RTL register.'
  result.append({'launch':launch,'capture':capture,'slack_ns':float(re.search(r'slack is ([-.0-9]+)',block).group(1)),
   'data_delay_ns':float(stats['Data Delay'][1]),'logic_levels':int(stats['Number of Logic Levels'][2]),
   'cell_delay_ns':cell_delay,'routing_delay_ns':routing_delay,'family':family,'source_mapping':mapping,
   'launch_cell':cells[0],'capture_cell':cells[-1],'data_cells':cells,
   'generated_register_ports':[r for r in ports if 'NEW_REG' in r['node']]})
 return result

def build(old,new):
 reports=[]
 for f in sorted((old/'timing_closure').glob('corner_*/negative_setup_paths.txt')):
  reports.append({'path':f.relative_to(old).as_posix(),'sha256':digest(f),'paths':extract(f)})
 assert sum(len(r['paths']) for r in reports)==13,'Unexpected baseline failure count'
 return {'format':'supplied-physical-evidence-v1',
  'hps_corrected_baseline':'c8d4b3897c4ed98165d3ee862cabbdd9ab9a4f17',
  'hps_archive_identity':(old/'timing_candidate_commit.txt').read_text().strip(),
  'hps_corners':table(old/'timing_closure/corners.tsv'),
  'hps_endpoint_summary':table(old/'timing_closure/endpoint_summary.tsv'),
  'hps_source_manifest_sha256':digest(old/'source_manifest_mapped_inputs.json'),
  'baseline_reports':reports,
  'newer_archive_identity':(new/'timing_candidate_commit.txt').read_text().strip(),
  'newer_source_snapshot':json.loads((new/'source_worktree_snapshot.json').read_text()),
  'newer_endpoint_summary':table(new/'timing_closure/endpoint_summary.tsv'),
  'limits':['Supplied textual TimeQuest exports, no vendor fitted database inspection.',
    'Newest archive has previously truncated detailed negative reports; endpoint TSV inventories remain the evidence for counts.',
    '6956285 failed synthesis. The newer local 6add25d build is separate and must not be called a timing result for 6956285.',
    'Original archived +0.177 ns result was one corner and a different effective configuration. It is not c8d4b38 eight-corner closure.']}

if __name__=='__main__':
 old,new,out=map(Path,sys.argv[1:]);out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(build(old,new),indent=2)+'\n')
