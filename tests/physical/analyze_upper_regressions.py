"""Offline complete negative-endpoint accounting. Never infers register ancestry."""
import argparse,csv,hashlib,json,re
from collections import Counter
from pathlib import Path

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def verify_extracted(root):
 root=Path(root);m=json.loads((root/'report_archive_manifest.json').read_text())
 for row in m['files']:
  h=hashlib.sha256();size=0
  for part in row['parts']:
   p=root/part['name']
   if p.stat().st_size!=part['bytes'] or sha(p)!=part['sha256']:raise ValueError('Part identity mismatch: '+str(p))
   with p.open('rb') as f:
    while b:=f.read(1048576):h.update(b);size+=len(b)
  if size!=row['bytes'] or h.hexdigest()!=row['sha256']:raise ValueError('Full identity mismatch: '+row['path'])
 return {'files_verified':len(m['files']),'partitioned_files':sum(len(r['parts'])>1 for r in m['files'])}

def family(launch,capture):
 if 'packed_ram' in capture:return 'CRT read/mux capture'
 if any(s in capture for s in ['advance_rows','|Add2~']):return 'CRT row arithmetic capture; generated ancestry pending'
 if 'vga:vga' in launch and ('|Add17' in capture or '|Mult' in capture):return 'VGA/root arithmetic'
 if any(s in capture for s in ['r_vram_in2','g_vram_in2','b_vram_in2']):return 'pixel decode capture; launch must be inspected'
 if 'ddr_burst' in capture:return 'DDR burst capture'
 if re.search(r'\|(br|bg|bb)\[',capture):return 'registered RGB capture'
 return 'other; exact launch/capture retained'

def analyze(root,destination):
 root=Path(root);out=Path(destination);out.mkdir(parents=True,exist_ok=False)
 inventory=[];summaries={}
 for e in ['U10','U9']:
  r=root/e/'output_files';comp=json.loads((r/'batch_comparison/comparison.json').read_text())
  corners=list(csv.DictReader((r/'timing_closure/corners.tsv').open(),delimiter='\t'))
  groups=[];n=0
  for c in corners:
   with (r/'timing_closure'/c['directory']/'negative_setup_endpoints.tsv').open() as f:
    rows=list(csv.DictReader(f,delimiter='\t'))
   counts=Counter();launches=Counter()
   for row in rows:
    k=family(row['from'],row['to']);counts[k]+=1;launches[row['from']]+=1
    inventory.append({'experiment':e,'corner':c['directory'],'family':k,**row});n+=1
   groups.append({'corner':c, 'negative_endpoints':len(rows),'capture_families':dict(counts),'launch_counts':dict(launches)})
  metrics=list(csv.DictReader((r/'closure_diagnostics/critical_path_metrics.tsv').open(),delimiter='\t'))
  assert len(metrics)==n,'Detailed metric inventory incomplete'
  summaries[e]={'groups':groups,'complete_negative_records':n,'vectors':comp['vectors'],
   'control_physical':comp['control_physical'],'candidate_physical':comp['candidate_physical'],
   'control_critical_paths':comp['control_critical_paths'],'critical_metrics':metrics,
   'application':json.loads((r/'application_cmp.json').read_text()),
   'assignment':(r/'upper_address_duplication.qsf').read_text(),
   'target_correspondence':'PENDING: worst-per-capture exports do not establish timing through the selected upper driver; renamed retimed registers are not equivalent by name.'}
 keys=list(dict.fromkeys(k for row in inventory for k in row))
 with (out/'all_negative_endpoints.tsv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=keys,delimiter='\t');w.writeheader();w.writerows(inventory)
 (out/'regression_analysis.json').write_text(json.dumps(summaries,indent=2)+'\n')
 return summaries
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--reports',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--verify',action='store_true');a=p.parse_args()
 if a.verify:
  for e in ['U10','U9','V3']:print(e,verify_extracted(a.reports/e),flush=True)
 s=analyze(a.reports,a.output);print({e:r['complete_negative_records'] for e,r in s.items()})
