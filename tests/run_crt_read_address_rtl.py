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
        source_files = [str(ROOT/'rtl/CRT/crt_packed_ram.sv'),
                        str(DUT_ROOT/'rtl/CRT/crt_vsize_fixed.sv'),
                        str(reference), str(ROOT/'tests/tb_crt_read_address.sv')]
        simulator = os.environ.get('CRT_RTL_SIMULATOR', 'verilator')
        if simulator == 'iverilog':
            # Same golden SystemVerilog testbench and two width configurations.
            # This avoids the hosted Verilator 5.032 internal code-generation
            # fault without reducing the number of vectors or checked signals.
            build.mkdir(parents=True, exist_ok=True)
            # Icarus cannot elaborate an unpacked-array assignment pattern
            # initializer. Replace it with equivalent time-zero element
            # initialization in a throwaway simulator-only testbench copy.
            original_tb = (ROOT/'tests/tb_crt_read_address.sv').read_text()
            old_init = "integer advances[0:2]='{0,0,0};"
            if original_tb.count(old_init) != 1:
                raise ValueError('Cannot adapt unrecognized CRT testbench initializer')
            normalized = original_tb.replace(old_init,
                'integer advances[0:2];\n'
                '    initial begin advances[0]=0; advances[1]=0; advances[2]=0; end')
            local_tb = tmp/'tb_crt_read_address_icarus.sv'
            local_tb.write_text(normalized)
            source_files[-1] = str(local_tb)
            executable = build/'crt-read-address.vvp'
            cmd = shlex.split(os.environ.get('IVERILOG', 'iverilog')) + [
                '-g2012', '-s', 'tb_crt_read_address',
                '-Ptb_crt_read_address.LINE_PX='+str(width),
                '-o', str(executable), *source_files]
            subprocess.run(cmd, check=True)
            subprocess.run(shlex.split(os.environ.get('VVP', 'vvp')) + [str(executable)], check=True)
        elif simulator == 'verilator':
            cmd = shlex.split(os.environ.get('VERILATOR', 'verilator')) + [
                '--default-language','1364-2001','+1800-2012ext+sv','--binary',
                '--timing', '-Wno-fatal', '--top-module', 'tb_crt_read_address',
                '-j', '2', '--Mdir', str(build), f'-GLINE_PX={width}', *source_files]
            result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True)
            if result.returncode:
                print(result.stdout)
                result.check_returncode()
            subprocess.run([str(build/'Vtb_crt_read_address')], check=True)
        else:
            raise ValueError('Unknown CRT parity simulator: ' + simulator)
