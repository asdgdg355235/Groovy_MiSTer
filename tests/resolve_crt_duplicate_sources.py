#!/usr/bin/env python3
"""Resolve final-driver DUPLICATE_ATOM sources from a fresh Quartus map audit.

No Quartus invocation. Refuse ambiguous/missing connections rather than guessing
synthesis-generated node suffixes after an RTL change.
"""
import csv
from pathlib import Path
import re
import sys

PREFIX = 'emu:emu|crt_vsize_fixed:u_vsize|'


def resolve(audit):
    groups = {}
    with Path(audit).open() as stream:
        for row in csv.reader(stream, delimiter='\t'):
            if len(row) < 8 or row[0] != 'RAM_ADDRESS' or row[3] != 'PORTBADDR':
                continue
            match = re.match(re.escape(PREFIX)+r'crt_packed_ram:packed_ram\[([012])\]\.(even|odd)_ram\|', row[2])
            if match and row[4] in ('0', '1', '2', '3', '4'):
                if len(row) >= 9 and row[8] not in ('COMBOUT', 'SUMOUT'):
                    raise ValueError(f'Refusing non-combinational source output {row[8]}: {row[6]}')
                groups.setdefault((*match.groups(), int(row[4])), set()).add(row[6])
    result = ['# Generated from fresh map RAM input connections; do not hand-edit.']
    for part in ('0', '1', '2'):
        for bank in ('even', 'odd'):
            for bit in range(5):
                sources = groups.get((part, bank, bit), set())
                if len(sources) != 1:
                    raise ValueError(f'bank {part} {bank} bit {bit}: expected one observed source, found {sources}')
                source = next(iter(sources))
                if not source.startswith(PREFIX) or any(c in source for c in '{}\\\r\n'):
                    raise ValueError(f'Unsupported source name: {source!r}')
                name = f'crt_read_{part}_{bank}_bit{bit}'
                sink = PREFIX+f'crt_packed_ram:packed_ram[{part}].{bank}_ram|*'
                result.append(f'set_instance_assignment -name DUPLICATE_ATOM {name} -from {{{source}}} -to {{{sink}}}')
    return '\n'.join(result)+'\n'


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: resolve_crt_duplicate_sources.py map.tsv resolved.qsf')
    content = resolve(sys.argv[1])
    Path(sys.argv[2]).write_text(content)
    print('PASS: resolved 30 bank/bit assignments from actual fresh-map input sources')
