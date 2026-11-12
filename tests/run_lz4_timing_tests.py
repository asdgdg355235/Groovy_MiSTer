#!/usr/bin/env python3
"""Compare complete LZ4 outputs/state with the best measured RTL; no Quartus."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = '00136c5f03de63d80d8e78208bb6802cfe53c53d'
with tempfile.TemporaryDirectory(prefix='lz4-timing-') as tmp:
    tmp = Path(tmp)
    reference = tmp/'reference.v'
    reference.write_text(subprocess.check_output(['git', 'show', BASE+':rtl/lz4.v'], cwd=ROOT, text=True)
                         .replace('module lz4 (', 'module lz4_reference (', 1))
    for disabled in (False, True):
        out = tmp/('byte-only' if disabled else 'full')
        command = shlex.split(os.environ.get('IVERILOG', 'iverilog'))
        subprocess.run(command+['-g2012', '-s', 'tb_lz4_timing', '-o', str(out)]
                       + (['-DMISTER_LZ4_DISABLE_64B'] if disabled else [])
                       + [str(ROOT/'tests/tb_lz4_timing.sv'), str(ROOT/'rtl/lz4.v'), str(reference)], check=True)
        subprocess.run(shlex.split(os.environ.get('VVP', 'vvp'))+[str(out)], check=True)
