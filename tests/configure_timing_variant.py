#!/usr/bin/env python3
"""Prepare one controlled user-run build variant; never invokes Quartus."""
from pathlib import Path
import argparse
import subprocess

VARIANTS = ('candidate', 'crt-new', 'transport-new', 'dup-off', 'hdmi-old', 'analysis-on', 'fitter-slow')
REF = '5d28cdabaab0d4dba22cdd0c5d8d1d749871279b'
HDMI = '''// With ascal absent, retain the mapped inactive value explicitly. The palette
// edge detector must not consume an undriven net. HDMI remains disabled.
`ifdef MISTER_DEBUG_NOHDMI
assign hdmi_vs = 1'b0;
`endif

'''


def configure(source, dest, variant):
    source, dest = Path(source).resolve(), Path(dest).resolve()
    if variant not in VARIANTS:
        raise ValueError(variant)
    paths = {'crt-new': ['rtl/CRT/crt_vsize_fixed.sv'],
             'transport-new': ['rtl/lz4.v', 'rtl/vga.v']}.get(variant, [])
    for path in paths:
        (dest/path).write_bytes(subprocess.check_output(['git', 'show', REF+':'+path], cwd=source))
    qsf = dest/'Groovy.qsf'
    text = qsf.read_text()
    if variant == 'analysis-on':
        text = text.replace('TIMEQUEST_MULTICORNER_ANALYSIS OFF', 'TIMEQUEST_MULTICORNER_ANALYSIS ON')
    if variant == 'fitter-slow':
        text = text.replace('OPTIMIZE_MULTI_CORNER_TIMING ON', 'OPTIMIZE_MULTI_CORNER_TIMING OFF')
    qsf.write_text(text)
    if variant == 'hdmi-old':
        path = dest/'sys/sys_top.v'
        text = path.read_text()
        if text.count(HDMI) != 1:
            raise ValueError('Inactive HDMI block changed')
        path.write_text(text.replace(HDMI, ''))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('dest', type=Path)
    parser.add_argument('variant', choices=VARIANTS)
    args = parser.parse_args()
    configure(args.source, args.dest, args.variant)
