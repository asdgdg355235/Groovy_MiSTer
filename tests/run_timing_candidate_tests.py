#!/usr/bin/env python3
"""Non-Quartus regression entry point. Requires Verilator, Icarus, g++, Z3.

Pass --main /path/to/Main_MiSTer to also run the existing HPS controller suite.
"""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--main', type=Path)
args = parser.parse_args()
commands = [
    [sys.executable, 'tests/prove_timing_arithmetic.py'],
    [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'],
    [sys.executable, 'tests/check_crt_ram_extraction.py'],
    ['tclsh', 'tests/test_crt_address_duplication.tcl'],
    [sys.executable, 'tests/run_crt_read_address_rtl.py'],
    ['bash', 'tests/run_crt_group_address_rtl.sh'],
    [sys.executable, 'tests/run_lz4_timing_tests.py'],
    [sys.executable, 'tests/run_geometry_tests.py'],
]
if args.main:
    commands.append([sys.executable, 'tests/run_controller_tests.py', str(args.main.resolve())])
for command in commands:
    print('+', ' '.join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)
print('PASS: candidate non-Quartus checks; physical compilation/timing/hardware pending')
