#!/usr/bin/env python3
"""Compare localized RAM drivers against the published pre-localization RTL."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get('CRT_READ_BASELINE', '00136c5f03de63d80d8e78208bb6802cfe53c53d')

with tempfile.TemporaryDirectory(prefix='crt-read-address-') as tmp:
    tmp = Path(tmp)
    reference = tmp/'reference.sv'
    reference.write_text(subprocess.check_output(
        ['git', 'show', BASE+':rtl/CRT/crt_vsize_fixed.sv'], cwd=ROOT, text=True
    ).replace('module crt_vsize_fixed #(', 'module crt_vsize_fixed_reference #(', 1))
    for width in (32, 2560):
        build = tmp/str(width)
        cmd = shlex.split(os.environ.get('VERILATOR', 'verilator'))
        result = subprocess.run(cmd+[
            '--binary', '--timing', '-Wno-fatal', '--top-module', 'tb_crt_read_address',
            '-j', '2', '--Mdir', str(build), f'-GLINE_PX={width}',
            str(ROOT/'rtl/CRT/crt_packed_ram.sv'),
            str(ROOT/'rtl/CRT/crt_vsize_fixed.sv'), str(reference),
            str(ROOT/'tests/tb_crt_read_address.sv')],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if result.returncode:
            print(result.stdout)
            result.check_returncode()
        subprocess.run([str(build/'Vtb_crt_read_address')], check=True)
