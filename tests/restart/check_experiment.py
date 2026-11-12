#!/usr/bin/env python3
"""Run independent gates for one baseline-derived experiment. Never Quartus."""
from pathlib import Path
import argparse,json,os,subprocess,sys,tarfile,tempfile,io
from experiments import ROOT,BASE,apply,registry,sha,PROTECTED,CORE
from language_gate import run

def check(name,output):
 with tempfile.TemporaryDirectory(prefix='groovy-independent-') as t:
  dest=Path(t)
  data=subprocess.check_output(['git','archive',BASE],cwd=ROOT)
  with tarfile.open(fileobj=io.BytesIO(data)) as archive:archive.extractall(dest,filter='data')
  spec=apply(dest,name)
  # Syntax first; no cycle test may bypass a language-mode failure.
  syntax=run(dest)
  env=dict(os.environ,TIMING_DUT_ROOT=str(dest),CRT_READ_BASELINE=BASE)
  commands=[]
  proof=spec.get('proof')
  if proof and proof not in ('delta','sync'):commands.append([sys.executable,str(ROOT/'tests/restart/prove.py'),proof])
  if proof=='sync':commands.append([sys.executable,str(ROOT/'tests/restart/prove.py'),'sync'])
  if spec.get('path')=='rtl/CRT/crt_vsize_fixed.sv':commands.append([sys.executable,str(ROOT/'tests/run_crt_read_address_rtl.py')])
  if proof in ('vga','delta'):commands.append([sys.executable,str(ROOT/'tests/run_geometry_tests.py')])
  if proof=='delta':commands.append([sys.executable,str(ROOT/'tests/restart/delta_compare.py'),str(dest)])
  for cmd in commands:
   print('+',' '.join(cmd),flush=True);subprocess.run(cmd,cwd=ROOT,env=env,check=True)
  manifest={p:sha((dest/p).read_bytes()) for p in PROTECTED+CORE}
  output.write_text(json.dumps(dict(experiment=spec,hardware_sources=manifest,syntax=syntax,commands=commands,
    result='PASS independent checks; Quartus acceptance and fitted timing pending'),indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--output',type=Path,required=True);a=p.parse_args();check(a.name,a.output)
