#!/usr/bin/env python3
"""Audit exact target matches and assignment warnings; not a retiming proof."""
import argparse
import csv
import json
from pathlib import Path
import re
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
from physical.control import write_json


def audit(output, phase):
    output = Path(output)
    recipe = output / 'physical_recipe.json'
    if not recipe.exists(): return {'experiment': 'R0', 'target_gate_pass': True, 'mechanism_status': 'control'}
    spec = json.loads(recipe.read_text())
    matches_path = output / 'closure_diagnostics' / f'target_matches_{phase}.tsv'
    if not matches_path.exists(): raise ValueError('Missing observed assignment-target matches')
    with matches_path.open() as stream: matches = list(csv.DictReader(stream, delimiter='\t'))
    errors = []
    for a in spec['assignments']:
        if sum(int(r['matches']) for r in matches if r['target'] == a['target']) == 0:
            errors.append('No exact observed match: ' + a['target'])
    needles = [a['target'] for a in spec['assignments']] + [a['name'] for a in spec['assignments']]
    bad = re.compile(r'ignored|not supported|unsupported|does not exist|can.t apply|cannot apply|not found', re.I)
    for log in [output / 'crt_read_address_compile.log', output / 'duplicate_fit.log']:
        if not log.exists(): continue
        # Stream a three-line context, avoiding giant fitter logs in memory.
        previous = ''
        pending = False
        with log.open(errors='replace') as stream:
            for number, line in enumerate(stream, 1):
                context = previous + line
                if (bad.search(context) and any(n in context for n in needles)) or (pending and any(n in line for n in needles)):
                    errors.append(f'{log.name}:{number}: {context.strip()}')
                pending = bool(bad.search(line))
                previous = line
    result = {'experiment': spec['experiment'], 'target_gate_pass': not errors, 'errors': errors,
              'mechanism_status': 'PENDING_POST_FIT_GRAPH_REVIEW',
              'limit': 'Nonempty names and accepted syntax do not prove that the intended boundary/locality changed.'}
    write_json(output / f'application_{phase}.json', result)
    if errors: raise ValueError('INVALID EXPERIMENT: ' + '; '.join(errors))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output_files', type=Path); p.add_argument('phase', choices=['map', 'cmp'])
    a = p.parse_args(); print(json.dumps(audit(a.output_files, a.phase), indent=2))
