#!/usr/bin/env python3
"""Capture sourced QSF/Tcl assignments independently of Quartus.

This models explicit assignment calls, not Quartus defaults, precedence of
wildcard instance assignments, or vendor IP elaboration. Raw order is retained.
"""
from pathlib import Path
import subprocess
import json
import sys
ROOT = Path(__file__).resolve().parents[1]


def capture(root):
    root = Path(root).resolve()
    events = []
    pending = [root/'Groovy.qsf']
    visited = set()
    missing = []
    while pending:
        path = pending.pop(0).resolve()
        if path in visited:
            continue
        visited.add(path)
        if not path.is_file():
            missing.append(str(path.relative_to(root)))
            continue
        lines = subprocess.check_output(['tclsh', str(ROOT/'tests/capture_project_assignments.tcl'), str(path)], cwd=root, text=True)
        rows = [[bytes.fromhex(value).decode('utf-8') for value in line.split('\t')] for line in lines.splitlines() if line]
        for row in rows:
            row = [str(Path(v).resolve().relative_to(root)) if v.startswith(str(root)+'/') else v for v in row]
            events.append(row)
            if len(row)>3 and row[:3] == ['global','-name','QIP_FILE']:
                pending.append(root/row[3])
    unique = sorted({tuple(row) for row in events})
    duplicates = [{'assignment': list(row), 'count': events.count(list(row))} for row in unique if events.count(list(row))>1]
    return {'scope': 'source-expanded project and recursive QIP calls; vendor defaults/precedence require fitter report', 'missing_qip_files': missing,
            'events': events, 'unique': [list(x) for x in unique], 'duplicates': duplicates}


if __name__ == '__main__':
    print(json.dumps(capture(sys.argv[1] if len(sys.argv)>1 else ROOT), indent=2))
