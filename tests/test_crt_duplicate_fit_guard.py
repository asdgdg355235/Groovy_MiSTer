#!/usr/bin/env python3
"""Exercise fitter-log failure handling with Python stand-ins, never Quartus."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest

from run_crt_duplicate_fit import run


class FitGuardTest(unittest.TestCase):
    def test_missing_source_stops_repeated_output(self):
        fake = "import time\nwhile True:\n print('Warning (171070): missing duplicate node', flush=True)\n time.sleep(.01)\n"
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            log = Path(tmp)/'fit.log'
            self.assertEqual(run([sys.executable, '-u', '-c', fake], log), 2)
            self.assertEqual(log.read_text().count('(171070)'), 1)

    def test_exit_status_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            log = Path(tmp)/'fit.log'
            self.assertEqual(run([sys.executable, '-c', "print('failed'); raise SystemExit(3)"], log), 3)
            self.assertEqual(log.read_text(), 'failed\n')


if __name__ == '__main__':
    unittest.main()
