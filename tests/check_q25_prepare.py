#!/usr/bin/env python3
"""Check clean, isolated preparation. No Quartus executable is required or run."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='groovy-q25-prepare-') as name:
    temp = Path(name)
    manifests = []
    for variant, hpos in [('BASE', 'content'), ('CABINET', 'content'), ('CABINET', 'sync')]:
        destination = temp / (variant + '-' + hpos)
        # An absent tool directory proves preparation doesn't require a
        # compiler installation. --run is never used by this test.
        command = [sys.executable, str(ROOT / 'tools/q25_build.py'), '--variant', variant,
                   '--hpos-mode', hpos, '--prepare-only', '--quartus-bin', str(temp / 'absent-tools'),
                   '--output', str(destination)]
        subprocess.run(command, cwd=ROOT, check=True)
        manifest = json.loads((destination / 'provenance.json').read_text())
        assert manifest['quartus_executed'] is False
        assert manifest['physical_status'] == 'UNMEASURED'
        assert manifest['device'] == '5CSEBA6U23I7' and manifest['seed'] == 1
        for relative, expected in manifest['sources_sha256'].items():
            assert hashlib.sha256((destination / relative).read_bytes()).hexdigest() == expected, relative
        refused = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        assert refused.returncode != 0 and 'Fresh build directory required' in refused.stderr
        manifests.append(manifest)
    assert manifests[0]['sources_sha256'] == manifests[1]['sources_sha256']
    changed = {path for path, digest in manifests[1]['sources_sha256'].items()
               if manifests[2]['sources_sha256'][path] != digest}
    assert changed == {'Groovy_Q25_CABINET.qsf'}
    print('PASS: BASE/CABINET/SYNCSHIFT isolated preparation, complete hashes, fresh-directory rejection; Quartus not executed')
