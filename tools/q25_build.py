#!/usr/bin/env python3
"""Prepare isolated Q25 builds; only --run executes the user's Quartus tools."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BASE = '735c777be2ec859afe3dc37cc448d49440447add'

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()

def prepare(destination, variant, hpos='content'):
    if git('status', '--porcelain', '--untracked-files=normal'):
        raise RuntimeError('Commit source changes before preparing a reproducible build')
    if destination.exists():
        raise RuntimeError('Fresh build directory required: ' + str(destination))
    subprocess.run(['git', 'merge-base', '--is-ancestor', BASE, 'HEAD'], cwd=ROOT, check=True)
    destination.mkdir(parents=True)
    names = git('ls-files', '-z').split('\0')
    copied = {}
    for name in names:
        path = Path(name)
        if not (name.startswith(('rtl/', 'sys/', 'tools/q25/'))
                or name in ('Groovy.sv', 'Groovy.qpf', 'Groovy.qsf', 'Groovy.sdc',
                            'Groovy_Q25_BASE.qsf', 'Groovy_Q25_CABINET.qsf', 'files.qip')):
            continue
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, target)
        copied[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    if hpos == 'sync':
        if variant != 'CABINET':
            raise ValueError('SYNCSHIFT is a CABINET-only compile-time alternative')
        name = 'Groovy_Q25_CABINET.qsf'
        with (destination / name).open('a') as stream:
            stream.write('set_global_assignment -name VERILOG_MACRO "GROOVY_CRT_HPOS_SYNCSHIFT=1"\n')
        copied[name] = hashlib.sha256((destination / name).read_bytes()).hexdigest()
    metadata = {
        'commit': git('rev-parse', 'HEAD'), 'base': BASE, 'variant': variant,
        'revision': 'Groovy_Q25_' + variant, 'device': '5CSEBA6U23I7',
        'compiler': '25.1std.0 Build 1129', 'seed': 1,
        'hpos_mode': hpos,
        'sources_sha256': copied,
        'assignments_sha256': {n: h for n, h in copied.items()
                               if Path(n).suffix in ('.qpf', '.qsf', '.qip', '.sdc', '.tcl')},
        'physical_status': 'UNMEASURED', 'quartus_executed': False,
    }
    (destination / 'provenance.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (destination / 'source.patch').write_text(git('diff', '--binary', BASE, 'HEAD') + '\n')
    return metadata

def package(destination):
    archive = destination.parent / (destination.name + '-reports.tar.gz')
    with tarfile.open(archive, 'w:gz') as tar:
        for path in sorted(destination.rglob('*')):
            if path.is_file() and (path.parts[len(destination.parts)] in ('output_files', 'logs')
                                   or path.suffix in ('.json', '.patch', '.qsf', '.qpf', '.qip', '.sdc', '.tcl')):
                tar.add(path, arcname=destination.name + '/' + str(path.relative_to(destination)))
    return archive

def execute(destination, metadata, quartus_bin):
    logs = destination / 'logs'
    logs.mkdir()
    def call(program, *args):
        executable = str(quartus_bin / program) if quartus_bin else program
        path = logs / (program + '-' + str(len(list(logs.iterdir()))) + '.log')
        with path.open('w') as output:
            result = subprocess.run([executable, *args], cwd=destination,
                                    stdout=output, stderr=subprocess.STDOUT)
        metadata['quartus_executed'] = True
        return result.returncode, path
    try:
        for program in ('quartus_sh', 'quartus_map', 'quartus_fit', 'quartus_sta', 'quartus_asm'):
            code, path = call(program, '--version')
            version = path.read_text()
            if code or not re.search(r'25\.1std\.0.*Build\s+1129', version, re.S) or 'Lite Edition' not in version:
                raise RuntimeError('Wrong compiler or failed version check: ' + str(path))
        code, _ = call('quartus_sh', '--flow', 'compile', 'Groovy', '-c', metadata['revision'])
        metadata['compile_exit'] = code
        # Preserve evidence even after failed compilation. Query failures are
        # recorded separately & cannot turn an incomplete run into acceptance.
        for program, script in [('quartus_sh', 'assignments.tcl'),
                                ('quartus_sta', 'timing.tcl')]:
            result, _ = call(program, '-t', 'tools/q25/' + script, metadata['revision'])
            metadata[script + '_exit'] = result
        metadata['physical_status'] = 'REQUIRES_REVIEW'
        if code or metadata['timing.tcl_exit'] or metadata['assignments.tcl_exit']:
            raise RuntimeError('Build/report stage failed; review retained logs')
    finally:
        (destination / 'provenance.json').write_text(json.dumps(metadata, indent=2) + '\n')
        print('Report archive:', package(destination), flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', choices=['BASE', 'CABINET'], required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--quartus-bin', type=Path)
    parser.add_argument('--hpos-mode', choices=['content', 'sync'], default='content')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare-only', action='store_true')
    action.add_argument('--run', action='store_true', help='USER RUN ONLY: execute Quartus locally')
    args = parser.parse_args()
    destination = (args.output or ROOT / 'q25-builds' / ('Q25-' + args.variant)).resolve()
    metadata = prepare(destination, args.variant, args.hpos_mode)
    print('Prepared', metadata['revision'], 'at', destination, flush=True)
    if args.run:
        execute(destination, metadata, args.quartus_bin.resolve() if args.quartus_bin else None)
    else:
        print('Quartus was not executed. Physical timing is unmeasured.')

if __name__ == '__main__':
    main()
