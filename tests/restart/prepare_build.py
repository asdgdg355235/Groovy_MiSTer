#!/usr/bin/env python3
"""Create a new source snapshot and preserve distinct pre-map/pre-fit inputs."""
import argparse,hashlib,io,json,os,shutil,subprocess,tarfile
from pathlib import Path
from experiments import apply,sha,source_archive,BUILD_EXCLUDE
EXCLUDE=BUILD_EXCLUDE

def source_paths(root):
 return sorted(p for p in root.rglob('*') if p.is_file() and not any(x in EXCLUDE for x in p.relative_to(root).parts))
def record(root,phase):
 root=Path(root).resolve();out=root/'output_files';entries=[]
 paths=source_paths(root)
 for name in ('crt_address_duplication_resolved.qsf','physical_overlay.qsf'):
  generated=out/name
  if generated.exists():paths.append(generated)
 for path in paths:
  rel=path.relative_to(root);data=path.read_bytes();target=out/'source_inputs'/phase/rel
  target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
  entries.append({'path':rel.as_posix(),'bytes':len(data),'sha256':sha(data)})
 identity=json.loads((out/'provenance.json').read_text()) if (out/'provenance.json').exists() else {}
 (out/f'source_manifest_{phase}.json').write_text(json.dumps({'phase':phase,'source_commit':identity.get('source_commit'),'experiment':identity.get('experiment'),'files':entries},indent=2)+'\n')
 return entries

def prepare(source,output,name,working=False,verified_physical=False):
 source=Path(source).resolve();output=Path(output).resolve()
 if output.exists() or source==output or source in output.parents:raise ValueError('Build directory must be new and outside source tree')
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
 raw=subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all'],cwd=source,text=True)
 status=[line for line in raw.splitlines() if not any(x in line for x in ('__pycache__/','.pyc'))]
 if status and not working:raise ValueError('Working tree differs from HEAD; commit it or explicitly pass --working-tree')
 output.mkdir(parents=True)
 data=source_archive(source,head)
 with tarfile.open(fileobj=io.BytesIO(data)) as archive:
  members=[m for m in archive.getmembers() if not any(x in EXCLUDE for x in Path(m.name).parts)]
  archive.extractall(output,members=members,filter='data')
 if working:
  listed=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=source).decode().split('\0')
  tracked=subprocess.check_output(['git','ls-files','-z'],cwd=source).decode().split('\0')
  for rel in listed:
   if not rel or any(x in EXCLUDE for x in Path(rel).parts):continue
   path=source/rel;target=output/rel
   if path.is_symlink():raise ValueError('Working-tree symlink requires explicit review: '+rel)
   if path.is_file():target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
   elif rel in tracked:target.unlink(missing_ok=True)
 if name=='working-tree':
  if not working:raise ValueError('working-tree experiment requires --working-tree')
  spec={'name':name,'controlled':False,'changes':'Actual explicit working-tree snapshot; not a one-factor baseline experiment'}
 elif verified_physical:
  if name!='baseline' or working:raise ValueError('Physical source must be committed baseline')
  spec={'name':'baseline','controlled':True,'hardware_validation':'tests/physical/control.py verified manifest before snapshot'}
 else:spec=apply(output,name)
 out=output/'output_files';out.mkdir()
 (out/'timing_candidate_commit.txt').write_text(head+'\n');(out/'build_variant.txt').write_text(name+'\n')
 diff=subprocess.check_output(['git','diff','HEAD','--binary'],cwd=source) if working else b''
 (out/'source_worktree_diff.patch').write_bytes(diff)
 provenance={'source_commit':head,'mode':'working-tree' if working else 'committed','dirty':bool(status),
             'source_status':status,'experiment':spec,'database_reuse':False,'excluded_directories':sorted(EXCLUDE)}
 (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
 record(output,'prepared')
 return provenance

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('output');p.add_argument('experiment',nargs='?',default='baseline');p.add_argument('--working-tree',action='store_true');p.add_argument('--record',action='store_true');a=p.parse_args()
 if a.record:record(a.source,a.output)
 else:prepare(a.source,a.output,a.experiment,a.working_tree)
