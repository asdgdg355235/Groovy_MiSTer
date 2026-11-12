#!/usr/bin/env python3
"""User-run fitter wrapper: stop immediately when a duplicate source is missing."""
import os
from pathlib import Path
import signal
import subprocess
import sys

from check_crt_duplicate_targets import check


def run(command, log):
    with Path(log).open('w') as output:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, start_new_session=True)
        try:
            for line in proc.stdout:
                output.write(line)
                print(line, end='', flush=True)
                if '(171070)' in line:
                    output.flush()
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
                    print('ERROR: missing duplicate source; fitter stopped. Return the map TSV and this log.', file=sys.stderr)
                    return 2
            return proc.wait()
        finally:
            proc.stdout.close()
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()


if __name__ == '__main__':
    resolved = Path('output_files/crt_address_duplication_resolved.qsf')
    check('output_files/crt_local_drivers_map.tsv', resolved if resolved.exists() else None)
    raise SystemExit(run(['quartus_fit', 'Groovy', '-c', 'Groovy'], 'output_files/duplicate_fit.log'))
