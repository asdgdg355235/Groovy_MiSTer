#!/usr/bin/env python3
"""Verify an extracted measured archive and compare actual inputs with Git."""
import argparse
import csv
import hashlib
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import tempfile
import shutil
from project_assignments import capture

ROOT = Path(__file__).resolve().parents[1]
REFS = ('00136c5f03de63d80d8e78208bb6802cfe53c53d', '5d28cdabaab0d4dba22cdd0c5d8d1d749871279b')


def topology(directory):
    result = {}
    for stage in ('map', 'cmp'):
        groups = {}
        path = directory/f'crt_local_drivers_{stage}.tsv'
        if not path.is_file():
            continue
        with path.open() as stream:
            for row in csv.reader(stream, delimiter='\t'):
                if len(row)<8 or row[0]!='RAM_ADDRESS' or row[3]!='PORTBADDR' or row[4] not in ('0','1','2','3','4'):
                    continue
                bank = re.search(r'packed_ram\[(\d+)\]\.(even|odd)_ram',row[2])
                if bank:
                    key = '.'.join(bank.groups())+'.bit'+row[4]
                    groups.setdefault(key,set()).add((row[5],row[6],row[7]))
        result[stage] = {key:[{'id':r[0],'name':r[1],'fanout':int(r[2])} for r in sorted(value)] for key,value in sorted(groups.items())}
    return result


def compare(directory):
    directory = Path(directory).resolve()
    tree = directory/'build_tree'
    manifest = json.loads((directory/'metadata/manifest.json').read_text())
    included = manifest['files']
    for entry in included:
        path = tree/entry['path']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('Archive manifest mismatch: '+entry['path'])
    result = {'manifest_sha256': hashlib.sha256((directory/'metadata/manifest.json').read_bytes()).hexdigest(),
              'verified_included_files': len(included), 'excluded_files': manifest['excluded'],
              'source_directory_claim': manifest['source_directory'], 'comparisons': {}, 'archived_driver_topology': topology(tree/'output_files')}
    archived_config = capture(tree)
    result['archived_project_calls'] = {'ordered_calls_sha256': hashlib.sha256(json.dumps(archived_config['events']).encode()).hexdigest(), 'calls': [{'assignment':list(row),'count':n} for row,n in sorted(Counter(tuple(x) for x in archived_config['events']).items())]}
    for ref in REFS:
        tracked = set(subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', ref], cwd=ROOT, text=True).splitlines())
        compared = []
        for entry in included:
            name = entry['path']
            if name not in tracked or Path(name).suffix.lower() not in {'.v', '.sv', '.vhd', '.sdc', '.tcl', '.qsf', '.qip', '.qpf', '.py', '.sh'}:
                continue
            data = subprocess.check_output(['git', 'show', ref+':'+name], cwd=ROOT)
            kind = ('report_or_test' if name.startswith('tests/') else 'timing_constraint' if name.endswith('.sdc') else
                    'functional_rtl' if Path(name).suffix in {'.v', '.sv', '.vhd'} else 'synthesis_or_fitting')
            compared.append({'path': name, 'category': kind, 'archived_sha256': entry['sha256'],
                             'git_sha256': hashlib.sha256(data).hexdigest(), 'equal': data == (tree/name).read_bytes()})
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            # Every directly sourced file is from this ref. No Quartus execution.
            for name in tracked:
                if Path(name).suffix not in {'.qsf', '.qip', '.tcl'} or name.startswith(('old-builds/', 'test-builds/')):
                    continue
                dest = tmp/name; dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(subprocess.check_output(['git', 'show', ref+':'+name], cwd=ROOT))
            config = capture(tmp)
        result['comparisons'][ref] = {'files': compared, 'project_calls_sha256': hashlib.sha256(json.dumps(config['events']).encode()).hexdigest(),
            'archive_only_calls': [x for x in archived_config['unique'] if x not in config['unique']],
            'git_only_calls': [x for x in config['unique'] if x not in archived_config['unique']]}
    patterns = set()
    for f in (directory/'large_file_excerpts').rglob('*.excerpt'):
        patterns.update(re.findall(r'Can.t duplicate node "([^"]+)"', f.read_text(errors='replace')))
    result['unique_missing_sources_in_included_excerpts'] = sorted(patterns)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('directory', type=Path); p.add_argument('output', type=Path)
    a = p.parse_args(); a.output.write_text(json.dumps(compare(a.directory), separators=(',', ':'))+'\n')
