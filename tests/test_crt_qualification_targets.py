#!/usr/bin/env python3
"""Exercise final-driver resolution and stale/cross-bank rejection."""
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

    def test_accepts_final_groups(self):
        self.run_check(self.rows, self.dump)

    def test_rejects_missing_source(self):
        with self.assertRaisesRegex(ValueError, 'exact source is missing'):
            self.run_check([r for r in self.rows if not ('local_ra_odd[0]' in r)], self.dump)

    def test_rejects_cross_bank_source(self):
        bad = self.dump.replace('local_ra_odd[0]~0', 'local_ra_odd[1]~1', 1)
        with self.assertRaisesRegex(ValueError, 'missing destinations or a different address source'):
            self.run_check(self.rows, bad)

    def test_resolves_renamed_synthesis_sources(self):
        from resolve_crt_duplicate_sources import resolve
        rows = [r.replace('local_ra_odd[', 'renamed_read[') for r in self.rows]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'map.tsv'
            path.write_text('\n'.join(rows)+'\n')
            output = Path(tmp)/'resolved.qsf'
            output.write_text(resolve(path))
            with contextlib.redirect_stdout(io.StringIO()):
                check(path, output)
            self.assertEqual(output.read_text().count('DUPLICATE_ATOM'), 30)
            path.write_text('\n'.join(r+'\tREGOUT' if r.startswith('RAM_ADDRESS') else r for r in rows))
            with self.assertRaisesRegex(ValueError, 'non-combinational source'):
                resolve(path)
            path.write_text('\n'.join(r for r in rows if '.odd_ram|' not in r))
            with self.assertRaisesRegex(ValueError, 'expected one observed source'):
                resolve(path)


if __name__ == '__main__':
    unittest.main()
