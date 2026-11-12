#!/usr/bin/env python3
"""Hash and preserve the actual compilation inputs, including A/B overrides."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import shutil

source, build = map(lambda p: Path(p).resolve(), sys.argv[1:3])
phase = sys.argv[3]
files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=source).decode().split('\0')
inputs = []
for name in files:
    if not name or Path(name).suffix.lower() not in {'.v', '.sv', '.vh', '.svh', '.vhd', '.qsf', '.qip', '.sdc', '.tcl', '.qpf', '.mif', '.hex', '.ip'}:
        continue
    path = build/name
    if not path.is_file():
        raise SystemExit(f'Missing compilation input {name}')
    data = path.read_bytes()
    inputs.append({'path': name, 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)})
    target = build/'output_files/source_inputs'/name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, target)
for name in ('build_id.v', 'output_files/crt_address_duplication_resolved.qsf'):
    path = build/name
    if path.is_file():
        inputs.append({'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size': path.stat().st_size})
        target = build/'output_files/source_inputs'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
result = {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip(),
          'phase': phase, 'variant': (build/'output_files/build_variant.txt').read_text().strip(), 'files': inputs}
(build/f'output_files/source_manifest_{phase}.json').write_text(json.dumps(result, indent=2)+'\n')
