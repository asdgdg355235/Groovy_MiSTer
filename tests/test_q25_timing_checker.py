#!/usr/bin/env python3
"""Synthetic fixtures test rejection behavior; these aren't measured timings."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('q25_check', ROOT / 'tools/q25/check_timing.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

class TimingChecker(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        names = ['corner_' + str(n) for n in range(8)]
        (self.root / 'corners.tsv').write_text('corner\n' + '\n'.join(names) + '\n')
        summary = ['corner\tcheck\tfailing_endpoints\ttns_ns\twns_ns']
        for name in names:
            path = self.root / name
            path.mkdir()
            (path / 'pulse_summary.tsv').write_text('complete\tfailing\twns_ns\n1\t0\t0.25\n')
            for kind in ('setup', 'hold', 'recovery', 'removal'):
                summary.append(f'{name}\t{kind}\t0\t0\t0.25')
                (path / ('all_' + kind + '_endpoints.tsv')).write_text('to\tslack_ns\nendpoint\t0.25\n')
        (self.root / 'summary.tsv').write_text('\n'.join(summary) + '\n')

    def test_complete(self):
        self.assertTrue(checker.check(self.root))

    def test_missing_corner(self):
        (self.root / 'corners.tsv').write_text('corner\ncorner_0\n')
        with self.assertRaises(ValueError): checker.check(self.root)

    def test_negative_hidden_by_summary(self):
        (self.root / 'corner_0/all_setup_endpoints.tsv').write_text('to\tslack_ns\nendpoint\t-0.01\n')
        with self.assertRaises(ValueError): checker.check(self.root)

    def test_empty_inventory(self):
        (self.root / 'corner_0/all_setup_endpoints.tsv').write_text('to\tslack_ns\n')
        with self.assertRaises(ValueError): checker.check(self.root)

    def test_nonfinite_slack(self):
        summary = self.root / 'summary.tsv'
        summary.write_text(summary.read_text().replace('0.25', 'nan', 1))
        with self.assertRaises(ValueError): checker.check(self.root)

    def test_pulse_failure(self):
        (self.root / 'corner_0/pulse_summary.tsv').write_text('complete\tfailing\twns_ns\n1\t1\t-0.01\n')
        with self.assertRaises(ValueError): checker.check(self.root)

if __name__ == '__main__': unittest.main()
