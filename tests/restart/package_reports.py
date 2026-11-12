#!/usr/bin/env python3
"""Losslessly split oversized reports; every tar member is <=200 MiB.

No Quartus commands. Originals stay untouched. The manifest maps byte parts
back to complete files and records SHA-256 for originals and archive members.
"""
import argparse,hashlib,io,json,os,tarfile
from pathlib import Path
MAX_MEMBER=200*1024*1024
POSITIVE_MEMBER=8*1024*1024

def digest_stream(stream,size):
 h=hashlib.sha256();left=size
 while left:
  block=stream.read(min(left,1024*1024))
  if not block:raise ValueError('Unexpected end of report')
  h.update(block);left-=len(block)
 return h.hexdigest()

def pack(root,output,limit=MAX_MEMBER,positive_limit=POSITIVE_MEMBER):
 root=Path(root).resolve();output=Path(output).resolve()
 if not 0<positive_limit<=limit<=MAX_MEMBER:raise ValueError('Invalid member size policy')
 if output==root or root in output.parents:raise ValueError('Archive must be outside report directory')
 manifest={'format':'groovy-lossless-parts-v1','max_member_bytes':limit,'positive_member_bytes':positive_limit,'files':[],'excluded':[]}
 temporary=output.with_name(output.name+'.partial')
 try:
  with tarfile.open(temporary,'w:gz') as archive:
   for path in sorted(root.rglob('*')):
    if not path.is_file():continue
    name=path.relative_to(root).as_posix()
    if path.is_symlink() or path.suffix.lower() in ('.sof','.rbf'):
     manifest['excluded'].append(name);continue
    bound=positive_limit if (path.name=='min_pulse_width.txt' or (path.name.endswith('_setup.txt') and not path.name.startswith('negative_')) or path.name.startswith('worst_')) else limit
    before=path.stat();total=before.st_size;parts=[];offset=0;number=0
    with path.open('rb') as source:
     while offset<total or (total==0 and number==0):
      number+=1;size=min(bound,total-offset)
      arcname='output_files/'+name if total<=bound else 'output_files/'+name+'.parts/'+f'{number:06d}.bin'
      position=source.tell();sha=digest_stream(source,size);source.seek(position)
      info=tarfile.TarInfo(arcname);info.size=size;info.mode=0o644
      archive.addfile(info,source)
      parts.append({'name':arcname,'bytes':size,'sha256':sha});offset+=size
    with path.open('rb') as source:fullsha=digest_stream(source,total)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Report changed while packaging: '+name)
    manifest['files'].append({'path':name,'bytes':total,'sha256':fullsha,'parts':parts})
   payload=json.dumps(manifest,separators=(',',':')).encode()
   if len(payload)>limit:raise ValueError('Archive inventory exceeds member limit')
   info=tarfile.TarInfo('report_archive_manifest.json');info.size=len(payload);info.mode=0o644
   archive.addfile(info,io.BytesIO(payload))
  os.replace(temporary,output)
 except BaseException:
  temporary.unlink(missing_ok=True);raise
 return manifest

def verify_or_restore(archive_path,destination=None):
 dest=Path(destination).resolve() if destination is not None else None
 if dest is not None and dest.exists():raise ValueError('Restore destination must be new')
 with tarfile.open(archive_path,'r:gz') as archive:
  info=json.load(archive.extractfile('report_archive_manifest.json'))
  members=archive.getmembers();names=[m.name for m in members]
  if not 0<info['max_member_bytes']<=MAX_MEMBER:raise ValueError('Invalid archive member cap')
  if len(names)!=len(set(names)):raise ValueError('Duplicate archive members')
  if any(not m.isfile() or m.size>info['max_member_bytes'] for m in members):raise ValueError('Oversized or unsupported member')
  if dest:dest.mkdir(parents=True)
  expected={'report_archive_manifest.json'}
  for row in info['files']:
   rel=Path(row['path'])
   if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe restore path')
   writer=None;h=hashlib.sha256();count=0
   if dest:
    target=dest/'output_files'/rel;target.parent.mkdir(parents=True,exist_ok=True);writer=target.open('wb')
   try:
    for part in row['parts']:
     expected.add(part['name']);m=archive.getmember(part['name'])
     if m.size!=part['bytes']:raise ValueError('Part size mismatch')
     ph=hashlib.sha256()
     with archive.extractfile(m) as data:
      while block:=data.read(1024*1024):
       h.update(block);ph.update(block);count+=len(block)
       if writer:writer.write(block)
     if ph.hexdigest()!=part['sha256']:raise ValueError('Part digest mismatch')
   finally:
    if writer:writer.close()
   if count!=row['bytes'] or h.hexdigest()!=row['sha256']:raise ValueError('Reassembled file mismatch')
  if expected!=set(names):raise ValueError('Unexpected/unlisted archive content')
 return info

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source');p.add_argument('output',nargs='?');p.add_argument('--verify',action='store_true');p.add_argument('--restore')
 a=p.parse_args()
 if a.verify or a.restore:r=verify_or_restore(a.source,a.restore)
 elif a.output:r=pack(a.source,a.output)
 else:p.error('Provide report directory and output archive, or --verify/--restore')
 print('PASS:',len(r['files']),'complete files; maximum member',r['max_member_bytes'],'bytes')
