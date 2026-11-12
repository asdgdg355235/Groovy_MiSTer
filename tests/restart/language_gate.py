#!/usr/bin/env python3
"""Independent language checks from the actual QSF assignments. Never Quartus."""
from pathlib import Path
import json,os,shlex,subprocess,tempfile,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests'))
from project_assignments import capture

def run(root):
 root=Path(root).resolve(); c=capture(root); modes={}
 for row in c['unique']:
  if row[0]=='global' and '-name' in row:
   i=row.index('-name'); kind=row[i+1]
   if kind in ('VERILOG_FILE','SYSTEMVERILOG_FILE'):modes[row[i+2]]=kind
 assert modes['rtl/vga.v']=='VERILOG_FILE'
 assert modes['Groovy.sv']==modes['rtl/CRT/crt_vsize_fixed.sv']=='SYSTEMVERILOG_FILE'
 iv=shlex.split(os.environ.get('IVERILOG','iverilog'))
 commands=[iv+['-g2001','-i','-tnull','-s','vga',str(root/'rtl/vga.v')],
           iv+['-g2012','-i','-tnull','-s','crt_vsize_fixed',str(root/'rtl/CRT/crt_vsize_fixed.sv'),str(root/'rtl/CRT/crt_packed_ram.sv')]]
 warnings=[]
 for cmd in commands:
  r=subprocess.run(cmd,capture_output=True,text=True)
  if r.returncode:raise RuntimeError(r.stdout+r.stderr)
  warnings.extend(r.stderr.splitlines())
 # Reproduce the actual failed expression: it MUST fail in Verilog mode.
 with tempfile.TemporaryDirectory() as d:
  p=Path(d)/'failure.v';p.write_text("module failure(input interlaced,field,input [9:0] V_blank);\nwire signed [10:0] V_blank_adjusted=$signed({1'b0,V_blank})-11'(interlaced && field);\nendmodule\n")
  bad=subprocess.run(iv+['-g2001','-tnull',str(p)],capture_output=True,text=True)
  sv=subprocess.run(iv+['-g2012','-tnull',str(p)],capture_output=True,text=True)
  assert bad.returncode!=0 and sv.returncode==0,'Language-mode negative control failed'
 return {'project_modes':modes,'checks':['vga Verilog-2001 parse/elaboration (missing unrelated modules ignored)','CRT SystemVerilog-2012 parse/elaboration','former sized cast rejected in Verilog, accepted in SystemVerilog'],
         'warnings':warnings,'limits':'Independent frontends, not Quartus acceptance. Inherited VGA [size] array declarations are accepted with warnings by Icarus and unchanged.'}
if __name__=='__main__':
 r=run(sys.argv[1] if len(sys.argv)>1 else ROOT);print(json.dumps(r,indent=2))
