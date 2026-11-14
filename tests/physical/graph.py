"""Lossless derived fanout accounting. Native edge IDs have build-local scope."""
import csv,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path
FIELDS=['source','source_type','source_location','destination','destination_type','destination_location','edge_type','expected_fanout','edge_id']
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  while block:=f.read(1024*1024):h.update(block)
 return h.hexdigest()
def normalize(path,destination,processed=None,export_status=None):
 path,destination=Path(path),Path(destination);destination.mkdir(parents=True,exist_ok=True)
 if path.resolve()==(destination/'fanout_normalized.tsv').resolve():raise ValueError('Raw and derived graph must differ')
 errors=[];by_id={};unique=[];stats=defaultdict(lambda:{'raw':0,'duplicate':0,'unique':0,'expected':set(),'identity':set()})
 if path.exists():
  with path.open() as f:
   reader=csv.DictReader(f,delimiter='\t');headers=reader.fieldnames
   if not headers or not set(FIELDS)<=set(headers):raise ValueError('Incomplete fanout schema')
   for row in reader:
    if None in row or any(row.get(k) is None for k in headers):raise ValueError('Malformed fanout record')
    token=tuple(row[k] for k in headers);edge=row['edge_id'];s=stats[row['source']];s['raw']+=1
    try:s['expected'].add(int(row['expected_fanout']))
    except ValueError:errors.append('Invalid fanout for '+row['source'])
    s['identity'].add((row['source_type'],row['source_location']))
    if edge in by_id:
     if by_id[edge]!=token:errors.append('Conflicting native edge ID: '+edge)
     else:s['duplicate']+=1;continue
    else:by_id[edge]=token
    unique.append(row);s['unique']+=1
 else:headers=FIELDS
 processed_rows=[]
 if processed and Path(processed).is_file():
  with Path(processed).open() as f:processed_rows=list(csv.DictReader(f,delimiter='\t'))
  processed_names=set()
  for row in processed_rows:
   name=row['source'];processed_names.add(name);s=stats[name]
   s['identity'].add((row['source_type'],row['source_location']));s['expected'].add(int(row['expected_fanout']))
  for row in unique:
   if row['source'] not in processed_names:errors.append('Edge source absent from processed-source export: '+row['source'])
 for name,s in stats.items():
  if len(s['expected'])!=1 or s['unique']!=next(iter(s['expected']),-1):errors.append('Incomplete or inconsistent fanout: '+name)
  if len(s['identity'])!=1:errors.append('Conflicting canonical source identity: '+name)
 with (destination/'fanout_normalized.tsv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=headers,delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(unique)
 with (destination/'fanout_source_accounting.tsv').open('w',newline='') as f:
  w=csv.writer(f,delimiter='\t',lineterminator='\n');w.writerow(['source','raw_edges','duplicate_edges','unique_edges','expected_fanout'])
  for name,s in stats.items():w.writerow([name,s['raw'],s['duplicate'],s['unique'],','.join(map(str,sorted(s['expected'])))])
 raw_count=sum(s['raw'] for s in stats.values());duplicates=sum(s['duplicate'] for s in stats.values())
 status=[]
 if export_status and Path(export_status).is_file():
  with Path(export_status).open() as f:status=list(csv.DictReader(f,delimiter='\t'))
 unexplained=None
 if status and not processed_rows:
  # Historical rows identify every nonzero-fanout visit; never invent zero-source names.
  visits=int(status[0]['processed_nodes']);nonzero_visits=sum(s['raw']//s['unique'] for s in stats.values() if s['unique'])
  unexplained=visits-nonzero_visits
 result={'format':'fanout-normalization-v1','raw_rows':raw_count,'duplicate_rows':duplicates,'unique_rows':len(unique),
  'repeated_sources':sum(s['duplicate']>0 for s in stats.values()),'sources':len(stats),'errors':sorted(set(errors)),
  'raw_sha256':sha(path) if path.exists() else None,'normalized_sha256':sha(destination/'fanout_normalized.tsv'),
  'explicit_zero_fanout_sources':sum(s['expected']=={0} and s['unique']==0 for s in stats.values()),
  'historical_unidentified_zero_edge_visits':unexplained,'zero_source_identities_complete':bool(processed_rows),
  'edge_identity_scope':'one native timing netlist; not comparable across compilations'}
 (destination/'fanout_normalization.json').write_text(json.dumps(result,indent=2)+'\n')
 return unique,result
