#!/usr/bin/env python3
from pathlib import Path
import subprocess,tempfile,os,shlex
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as t:
 cmd=shlex.split(os.environ.get('VERILATOR','verilator'))+['--binary','--timing','-Wno-fatal','--top-module','tb_targeted_arithmetic','-j','2','--Mdir',t]
 cmd += [str(root/p) for p in ('tests/tb_targeted_arithmetic.sv','tests/rtl_models.sv','rtl/CRT/crt_vsize_fixed.sv','rtl/CRT/crt_packed_ram.sv','rtl/vga.v','rtl/binary_to_bcd.v')]
 r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 if r.returncode: print(r.stdout);r.check_returncode()
 subprocess.run([str(Path(t)/'Vtb_targeted_arithmetic')],check=True)
