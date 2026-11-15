#!/usr/bin/env python3
"""Check logical synchronous RAM inference with Yosys, never Quartus."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = [('lz4', 'rtl/lz4.v', '', 'window', 8192, 64),
         ('crt_vsize', 'rtl/CRT/crt_vsize.sv', 'chparam -set LINE_PX 640 crt_vsize;', 'ring', 29440, 24),
         ('crt_adjust', 'rtl/CRT/crt_adjust.sv', 'chparam -set AW 11 crt_adjust;', 'mem', 2048, 24)]

def main():
    result = {}
    with tempfile.TemporaryDirectory(prefix='groovy-ram-') as name:
        temp = Path(name)
        for top, source, params, memory, depth, width in CASES:
            output = temp / (top + '.json')
            script = f'read_verilog -sv {source}; {params} hierarchy -top {top}; proc; opt; memory_dff; memory_collect; write_json {output}'
            run = subprocess.run(shlex.split(os.environ.get('YOSYS', 'yosys')) + ['-Q', '-T', '-p', script],
                                 cwd=ROOT, capture_output=True, text=True)
            if run.returncode:
                raise RuntimeError(run.stdout + run.stderr)
            module = json.loads(output.read_text())['modules'][top]
            cell = module['cells'][memory]
            assert cell['type'] == '$mem_v2', memory
            p = {k: int(v, 2) for k, v in cell['parameters'].items()
                 if k in ('SIZE', 'WIDTH', 'RD_PORTS', 'WR_PORTS', 'RD_CLK_ENABLE', 'WR_CLK_ENABLE')}
            assert p == dict(SIZE=depth, WIDTH=width, RD_PORTS=1, WR_PORTS=1,
                             RD_CLK_ENABLE=1, WR_CLK_ENABLE=1), p
            result[top] = dict(memory=memory, logical_bits=depth * width, **p)
    print(json.dumps(result, indent=2))
    print('PASS: synchronous 1R/1W memories. M10K packing & device fit require Quartus reports.')

if __name__ == '__main__':
    main()
