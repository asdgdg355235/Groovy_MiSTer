#!/usr/bin/env python3
"""Exercise qualification preflight acceptance and stale/cross-bank rejection."""
import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from check_crt_duplicate_targets import ROOT, check


class QualificationTargetsTest(unittest.TestCase):
    def setUp(self):
        self.dump = subprocess.check_output(['tclsh', str(ROOT/'tests/test_crt_address_duplication.tcl'), '--dump'], text=True)
        self.rows = ['DRIVER\t1\temu:emu|crt_vsize_fixed:u_vsize|wa[3]~3\tCOMBOUT\t15400']
        self.qual_row = 'READ_CONTROL_EDGE\t2\tread\tDATAA\t-\t3\temu:emu|crt_vsize_fixed:u_vsize|LessThan13~1\t49'
        self.rows.append(self.qual_row)
        for part in range(3):
            for bank in ('even', 'odd'):
                for bit in range(5):
                    self.rows.append(f'RAM_ADDRESS\t10\temu:emu|crt_vsize_fixed:u_vsize|crt_packed_ram:packed_ram[{part}].{bank}_ram|leaf\tPORTBADDR\t{bit}\t20\temu:emu|crt_vsize_fixed:u_vsize|packed_ram[1].local_ra_odd[{bit}]~{bit}\t15440')

    def run_check(self, rows, dump):
        with tempfile.TemporaryDirectory() as tmp, patch('check_crt_duplicate_targets.subprocess.check_output', return_value=dump), contextlib.redirect_stdout(io.StringIO()):
            path = Path(tmp)/'map.tsv'
            path.write_text('\n'.join(rows)+'\n')
            check(path)

    def test_accepts_six_qualification_groups(self):
        self.run_check(self.rows, self.dump)

    def test_rejects_missing_comparator(self):
        with self.assertRaisesRegex(ValueError, 'exact source is missing'):
            self.run_check([row for row in self.rows if row != self.qual_row], self.dump)

    def test_rejects_cross_bank_qualification(self):
        prefix = 'emu:emu|crt_vsize_fixed:u_vsize|'
        bad = self.dump.replace(prefix+'LessThan13~1\t'+prefix+'crt_read_0_even_bit*',
                                prefix+'LessThan13~1\t'+prefix+'crt_read_1_even_bit*', 1)
        self.assertNotEqual(bad, self.dump)
        with self.assertRaisesRegex(ValueError, 'invalid destination prefix'):
            self.run_check(self.rows, bad)


if __name__ == '__main__':
    unittest.main()
