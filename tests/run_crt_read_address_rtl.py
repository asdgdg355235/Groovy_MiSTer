#!/usr/bin/env python3
"""Compare localized RAM drivers against the published pre-localization RTL."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DUT_ROOT=Path(os.environ.get('TIMING_DUT_ROOT',ROOT)).resolve()
BASE = os.environ.get('CRT_READ_BASELINE', 'c8d4b3897c4ed98165d3ee862cabbdd9ab9a4f17')

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
            '--default-language','1364-2001','+1800-2012ext+sv','--binary', '--timing', '-Wno-fatal', '--top-module', 'tb_crt_read_address',
            '-j', '2', '--Mdir', str(build), f'-GLINE_PX={width}',
            str(ROOT/'rtl/CRT/crt_packed_ram.sv'),
            str(DUT_ROOT/'rtl/CRT/crt_vsize_fixed.sv'), str(reference),
            str(ROOT/'tests/tb_crt_read_address.sv')],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if result.returncode:
            print(result.stdout)
            result.check_returncode()
        subprocess.run([str(build/'Vtb_crt_read_address')], check=True)
