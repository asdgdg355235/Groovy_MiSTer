#!/usr/bin/env python3
import hashlib
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = '735c777be2ec859afe3dc37cc448d49440447add'

class CabinetSource(unittest.TestCase):
    def test_framework_and_native_subsystems_unchanged(self):
        names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASE, 'sys', 'hps_linux'], cwd=ROOT, text=True).splitlines()
        names += ['rtl/vga.v', 'rtl/sound.v', 'rtl/hps_ext.v', 'Groovy.sdc']
        for name in names:
            expected = subprocess.check_output(['git', 'show', BASE + ':' + name], cwd=ROOT)
            self.assertEqual(hashlib.sha256(expected).digest(), hashlib.sha256((ROOT / name).read_bytes()).digest(), name)

    def test_status_fields_and_osd(self):
        sv = (ROOT / 'Groovy.sv').read_text()
        self.assertIn('wire [127:0] status;', sv)
        self.assertIn('P1O[60],CRT Adjust,Off,On;', sv)
        self.assertIn('HEP1O[64:61],Cabinet V-Size,', sv)
        fields = re.findall(r'O\[(\d+)(?::(\d+))?\]', sv[sv.index('localparam CONF_STR'):sv.index('// HPS is the module')])
        used = set()
        for high, low in fields:
            bits = set(range(int(low or high), int(high) + 1))
            self.assertFalse(used & bits)
            used |= bits
        # Match the HPS's byte-spanning read/write & signed OSD conventions.
        for raw in range(16):
            step = raw if raw < 8 else raw - 16
            self.assertLessEqual(abs(-3 * step), 24)

    def test_q25_pll_and_clock_constraints(self):
        self.assertEqual((ROOT / 'sys/pll_q17.qip').read_bytes(), (ROOT / 'sys/pll_q25.qip').read_bytes())
        qsf = (ROOT / 'Groovy_Q25_BASE.qsf').read_text()
        for setting in ('DEVICE 5CSEBA6U23I7', 'SEED 1', 'TIMEQUEST_MULTICORNER_ANALYSIS ON'):
            self.assertIn(setting, qsf)
        for source in (ROOT / 'tools/q25').glob('*.tcl'):
            self.assertNotIn('get_all_assignment_names', source.read_text())

    def test_source_reference_identity(self):
        manifest = __import__('json').loads((ROOT / 'docs/cabinet-sources.json').read_text())
        for name, expected in manifest['upstream_files_sha256'].items():
            self.assertEqual(expected, hashlib.sha256((ROOT / 'tests/reference' / name).read_bytes()).hexdigest())

if __name__ == '__main__':
    unittest.main()
