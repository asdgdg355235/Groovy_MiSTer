#!/usr/bin/env python3
"""Prepare one controlled user-run build variant; never invokes Quartus."""
from pathlib import Path
import argparse
import subprocess

VARIANTS = ('candidate', 'baseline', 'read-add', 'delta-flat', 'ready-shared', 'vga-old',
            'crt-new', 'transport-new', 'dup-off', 'hdmi-old', 'analysis-on', 'fitter-slow')
MEASURED = 'c8d4b3897c4ed98165d3ee862cabbdd9ab9a4f17'
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
    if variant in ('baseline','vga-old'):
        paths=['rtl/vga.v'] if variant=='vga-old' else ['Groovy.sv','rtl/CRT/crt_vsize_fixed.sv','rtl/vga.v']
        for path in paths:
            (dest/path).write_bytes(subprocess.check_output(['git','show',MEASURED+':'+path],cwd=source))
    if variant == 'read-add':
        path=dest/'rtl/CRT/crt_vsize_fixed.sv'; text=path.read_text()
        start=text.index('        if (LINE_PX == 2560 && LINE_WORDS == 512 && AW == 12)')
        end=text.index('\n    endfunction',start)
        path.write_text(text[:start]+'        read_address_word = address_word(s,word);'+text[end:])
    if variant == 'delta-flat':
        path=dest/'Groovy.sv'; text=path.read_text()
        start=text.index('// Two combinational mux levels:'); end=text.index('reg        PoC_lz4_delta_req;',start)
        path.write_text(text[:start]+'wire [63:0] PoC_lz4_delta_selected = PoC_lz4_delta_FB[PoC_lz4_delta_index];\n'+text[end:])
    if variant == 'ready-shared':
        path=dest/'rtl/CRT/crt_vsize_fixed.sv'; text=path.read_text()
        start=text.index('    // Select after tag lookup/comparison');end=text.index('\n    always @(posedge clk)',start)
        shared="    wire pair_ready = complete[slot_now] && tag[slot_now] == src_now\n                   && (last_row || (complete[bslot] && tag[bslot] == src_now+1'b1));\n"
        text=text[:start]+shared+text[end:]
        path.write_text(text.replace('line_begin ? valid_line : valid_current}', 'output_now && !hb_in && !vs_in && pair_ready && !dividing}'))
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
