#!/usr/bin/env python3
"""Verify exact DUPLICATE_ATOM sources and destination groups in a saved map TSV.

Uses plain Tcl and Python only. Does not validate Quartus assignment acceptance.
"""
import csv
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def check(path):
    dump = subprocess.check_output(['tclsh', str(ROOT/'tests/test_crt_address_duplication.tcl'), '--dump'], text=True)
    assignments = [line.split('\t')[1:] for line in dump.splitlines() if line.startswith('ASSIGN\t')]
    sources = set()
    rows = []
    for row in csv.reader(Path(path).open(), delimiter='\t'):
        if row[0] == 'DRIVER':
            sources.add(row[2])
        elif row[0] == 'RAM_ADDRESS':
            sources.add(row[6])
            if row[3] == 'PORTBADDR' and int(row[4]) < 5:
                rows.append(row)
    for name, source, target in assignments:
        if source not in sources:
            raise ValueError(f'{name}: exact source is missing: {source}')
        if name.startswith('crt_read_word_'):
            created = {'emu:emu|crt_vsize_fixed:u_vsize|' + a[0] for a in assignments if re.fullmatch(r'crt_read_[012]_(even|odd)_bit3', a[0])}
            if target not in sources and target not in created:
                raise ValueError(f'{name}: destination is neither observed nor created: {target}')
            print(f'PASS {name}: source exists; destination observed or created by final-driver assignment (Fitter ordering unverified)')
            continue
        match = re.fullmatch(r'crt_read_([012])_(even|odd)_bit([0-4])', name)
        if not match or not target.endswith('|*'):
            raise ValueError(f'Unexpected target group: {name}: {target}')
        part, bank, bit = match.groups()
        prefix = target[:-1]  # Only a terminal *; array brackets are literal.
        selected = [row for row in rows if row[2].startswith(prefix) and row[4] == bit]
        expected = f'packed_ram[{part}].{bank}_ram|'
        if not selected or any(expected not in row[2] or row[6] != source for row in selected):
            raise ValueError(f'{name}: missing destinations or a different address source')
        count = len({row[2] for row in selected})
        print(f'PASS {name}: {count} RAM atoms connected to exact source, fanout={selected[0][7]}')
    print(f'PASS: all {len(assignments)} assignments checked against {path}')
    print('Quartus acceptance, upstream edge and fitted duplication still require local verification.')

if __name__ == '__main__':
    try:
        check(sys.argv[1])
    except (ValueError, IndexError) as error:
        raise SystemExit(str(error))
