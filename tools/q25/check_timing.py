#!/usr/bin/env python3
"""Check exported timing tables. Does not qualify RAM, resources or hardware."""
import argparse
import csv
import math
from pathlib import Path

def rows(path):
    with path.open() as stream:
        return list(csv.DictReader(stream, delimiter='\t'))

def check(root):
    corners = rows(root / 'corners.tsv')
    names = [row['corner'] for row in corners]
    if len(names) != 8 or len(set(names)) != 8:
        raise ValueError('Eight distinct corners required')
    summary = rows(root / 'summary.tsv')
    seen = set()
    for row in summary:
        key = (row['corner'], row['check'])
        if key in seen or key[0] not in names:
            raise ValueError('Invalid/duplicate timing summary row')
        seen.add(key)
        if int(row['failing_endpoints']) or float(row['tns_ns']) != 0:
            raise ValueError('Failing endpoints/TNS: ' + str(key))
        if row['wns_ns'] == 'NA':
            if row['check'] in ('setup', 'hold'):
                raise ValueError('Missing timing evidence: ' + str(key))
        elif not math.isfinite(float(row['wns_ns'])) or float(row['wns_ns']) < 0:
            raise ValueError('Negative slack: ' + str(key))
    if seen != {(name, kind) for name in names for kind in ('setup', 'hold', 'recovery', 'removal')}:
        raise ValueError('Incomplete timing coverage')
    for name in names:
        pulse = rows(root / name / 'pulse_summary.tsv')
        if len(pulse) != 1 or pulse[0]['complete'] != '1' or int(pulse[0]['failing']) or not math.isfinite(float(pulse[0]['wns_ns'])) or float(pulse[0]['wns_ns']) < 0:
            raise ValueError('Failed/incomplete pulse-width checks: ' + name)
        for kind in ('setup', 'hold', 'recovery', 'removal'):
            inventory = root / name / ('all_' + kind + '_endpoints.tsv')
            if not inventory.is_file():
                raise ValueError('Missing endpoint inventory: ' + str(inventory))
            endpoints = rows(inventory)
            reported = next(row for row in summary if row['corner'] == name and row['check'] == kind)
            if len({row['to'] for row in endpoints}) != len(endpoints):
                raise ValueError('Duplicate endpoint inventory: ' + str(inventory))
            slacks = [float(row['slack_ns']) for row in endpoints]
            if any(not math.isfinite(slack) or slack < 0 for slack in slacks):
                raise ValueError('Invalid/negative endpoint slack: ' + str(inventory))
            if not endpoints:
                if kind in ('setup', 'hold') or reported['wns_ns'] != 'NA':
                    raise ValueError('Empty endpoint inventory: ' + str(inventory))
            elif reported['wns_ns'] == 'NA' or abs(min(slacks) - float(reported['wns_ns'])) > 0.000001:
                raise ValueError('Summary/inventory mismatch: ' + str(inventory))
    return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('timing_directory', type=Path)
    args = parser.parse_args()
    check(args.timing_directory)
    print('PASS: exported eight-corner timing tables. Review constraint coverage, warnings, RAM/resources & hardware separately.')
