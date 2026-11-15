#!/usr/bin/env python3
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='groovy-av-') as name:
    output = str(Path(name) / 'test')
    reference = Path(name) / 'sound_reference.v'
    reference.write_text(subprocess.check_output(['git', 'show',
        '735c777be2ec859afe3dc37cc448d49440447add:rtl/sound.v'], cwd=ROOT, text=True)
        .replace('module sound (', 'module sound_reference (', 1))
    files = ['tests/tb_native_av.sv', 'tests/rtl_models.sv', 'rtl/vga.v', 'rtl/sound.v', 'rtl/binary_to_bcd.v']
    subprocess.run(shlex.split(os.environ.get('IVERILOG', 'iverilog')) +
                   ['-g2012', '-s', 'tb_native_av', '-o', output, str(reference)] + [str(ROOT / f) for f in files], check=True)
    subprocess.run(shlex.split(os.environ.get('VVP', 'vvp')) + [output], check=True)
