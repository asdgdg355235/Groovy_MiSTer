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
 # Elaborate the affected emu configuration in mixed project languages.
 with tempfile.TemporaryDirectory() as d:
  d=Path(d); original=(root/'Groovy.sv').read_text()
  # Existing Quartus unpacked-net initializer: syntax-equivalent frontend adapter.
  normalized=original.replace("wire [31:0] PLL_ARM_F[PLL_PARAM_F_COUNT * 2] = '{", "wire [31:0] PLL_ARM_F[PLL_PARAM_F_COUNT * 2];\nassign PLL_ARM_F = '{")
  top=d/'Groovy.sv';top.write_text(normalized)
  (d/'build_id.v').write_text('`define BUILD_DATE "independent-test"\n')
  files=[top,ROOT/'tests/rtl_models.sv',*sorted((root/'rtl/CRT').glob('*.sv')),*sorted((root/'rtl/JTFRAME').glob('*.v'))]
  files += [root/p for p in ('rtl/vga.v','rtl/hps_ext.v','rtl/ddram.sv','rtl/sound.v','rtl/lz4.v','rtl/binary_to_bcd.v','sys/hq2x.sv','sys/math.sv')]
  cmd=shlex.split(os.environ.get('VERILATOR','verilator'))+['--lint-only','--default-language','1364-2001','+1800-2012ext+sv','--bbox-unsup','-Wno-fatal','-Wno-PROCASSWIRE','-Wno-BLKANDNBLK','-DGROOVY_CRT_GEOMETRY','--top-module','emu','-I'+str(root),'-I'+str(root/'sys'),'-I'+str(d)]+[str(p) for p in files]
  r=subprocess.run(cmd,capture_output=True,text=True)
  if r.returncode:raise RuntimeError(r.stdout+r.stderr)
 # Reproduce the actual failed expression: it MUST fail in Verilog mode.
 with tempfile.TemporaryDirectory() as d:
  p=Path(d)/'failure.v';p.write_text("module failure(input interlaced,field,input [9:0] V_blank);\nwire signed [10:0] V_blank_adjusted=$signed({1'b0,V_blank})-11'(interlaced && field);\nendmodule\n")
  bad=subprocess.run(iv+['-g2001','-tnull',str(p)],capture_output=True,text=True)
  sv=subprocess.run(iv+['-g2012','-tnull',str(p)],capture_output=True,text=True)
  assert bad.returncode!=0 and sv.returncode==0,'Language-mode negative control failed'
 return {'project_modes':modes,'checks':['vga Verilog-2001 parse/elaboration (missing unrelated modules ignored)','CRT SystemVerilog-2012 parse/elaboration','mixed-language emu elaboration with explicit IP/VHDL models','former sized cast rejected in Verilog, accepted in SystemVerilog'],
         'warnings':warnings,'limits':'Independent frontends, not Quartus acceptance. Inherited VGA [size] array declarations are accepted with warnings by Icarus and unchanged.'}
if __name__=='__main__':
 r=run(sys.argv[1] if len(sys.argv)>1 else ROOT);print(json.dumps(r,indent=2))
