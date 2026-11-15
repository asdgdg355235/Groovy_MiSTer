#!/usr/bin/env python3
"""Icarus functional regressions. This entry point never executes Quartus."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
IVERILOG = shlex.split(os.environ.get('IVERILOG', 'iverilog'))
VVP = shlex.split(os.environ.get('VVP', 'vvp'))

def run(top, files, params=()):
    with tempfile.TemporaryDirectory(prefix='groovy-cabinet-') as name:
        temp = Path(name)
        refs = []
        for module in ('crt_adjust', 'crt_vsize'):
            reference = temp / (module + '_reference.sv')
            source = (ROOT / 'tests/reference' / (module + '.sv')).read_text().replace(
                'module ' + module + ' #(', 'module ' + module + '_reference #(', 1)
            if os.environ.get('CRT_SIMULATOR') == 'verilator' and module == 'crt_vsize':
                # Verilator 5.032 crashes on a function call in the RAM-write
                # LHS. Hoist that identical expression into a wire for this
                # frontend only. Icarus uses the verbatim frozen reference.
                marker = 'wire [5:0] wl_next = (wl == RING_LINES-1) ? 6\'d0 : wl + 1\'d1;'
                source = source.replace(marker, marker + '\n    wire [RAW-1:0] reference_write_addr = line_base(wl) + wpx;')
                source = source.replace('ring[line_base(wl) + wpx] <=', 'ring[reference_write_addr] <=')
            reference.write_text(source)
            refs.append(str(reference))
        if os.environ.get('CRT_SIMULATOR') == 'verilator':
            obj = temp / 'obj'
            cmd = shlex.split(os.environ.get('VERILATOR', 'verilator'))
            cmd += ['--binary', '--timing', '-Wno-fatal', '-Wno-BLKANDNBLK',
                    '--top-module', top, '--Mdir', str(obj), '-j', '2']
            cmd += ['-G' + value for value in params]
            compiled = subprocess.run(cmd + [str(ROOT / f) for f in files] + refs,
                                      capture_output=True, text=True)
            if compiled.returncode:
                raise RuntimeError(compiled.stdout + compiled.stderr)
            subprocess.run([str(obj / ('V' + top))], check=True)
            return
        cmd = IVERILOG + ['-g2012', '-s', top, '-o', str(temp / 'test')]
        cmd += ['-P' + top + '.' + value for value in params]
        subprocess.run(cmd + [str(ROOT / f) for f in files] + refs, check=True)
        subprocess.run(VVP + [str(temp / 'test')], check=True)

if __name__ == '__main__':
    for mode in (0, 1):
        run('tb_crt_read_rate', ['tests/tb_crt_read_rate.sv', 'rtl/CRT/groovy_crt.sv',
                               'rtl/CRT/crt_adjust.sv', 'rtl/CRT/crt_vsize.sv'], ['MODE=' + str(mode)])
        run('tb_crt_adjust_upstream', ['tests/tb_crt_adjust_upstream.sv', 'rtl/CRT/crt_adjust.sv'], ['MODE=' + str(mode)])
        run('tb_groovy_crt', ['tests/tb_groovy_crt.sv', 'rtl/CRT/groovy_crt.sv',
                            'rtl/CRT/crt_adjust.sv', 'rtl/CRT/crt_vsize.sv'], ['MODE=' + str(mode)])
    for period in (8, 16):
        run('tb_cabinet_upstream', ['tests/tb_cabinet_upstream.sv', 'rtl/CRT/crt_vsize.sv'], ['PERIOD=' + str(period)])
    run('tb_cabinet_upstream', ['tests/tb_cabinet_upstream.sv', 'rtl/CRT/crt_vsize.sv'], ['TOP=32'])
    run('tb_cabinet_upstream', ['tests/tb_cabinet_upstream.sv', 'rtl/CRT/crt_vsize.sv'],
        ['PERIOD=8', 'WIDTH=640', 'CAPACITY=640', 'DIFFERENTIAL=0', 'END_FRAMES=8'])
