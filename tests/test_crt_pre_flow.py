#!/usr/bin/env python3
"""Exercise the real build-ID callback in plain Tcl with project API stand-ins."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
set quartus(args) {pre_flow Groovy Groovy}
proc project_exists {name} {return [expr {$name eq "Groovy"}]}
proc project_open {name args} {
    if {$name ne "Groovy" || $args ne {-revision Groovy}} {error "Wrong project/revision"}
}
proc get_global_assignment {flag name} {
    switch $name {
        DEVICE {return 5CSEBA6U23I7}
        PROJECT_OUTPUT_DIRECTORY {return output_files}
        default {error "Unexpected assignment: $name"}
    }
}
proc is_project_open {} {return 1}
proc project_close {} {}
proc post_message {args} {puts $args}
source [lindex $argv 0]
set f [open build_id.v]; set content [read $f]; close $f
set expected "`define BUILD_DATE \"[clock format [clock seconds] -format %y%m%d]\""
if {$content ne $expected} {error "Wrong build ID"}
'''


class PreFlowTest(unittest.TestCase):
    def test_clean_directory_generates_real_build_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp)/'harness.tcl'
            script.write_text(HARNESS)
            subprocess.run(['tclsh', str(script), str(ROOT/'sys/build_id.tcl')], cwd=tmp, check=True, capture_output=True, text=True)
            self.assertIn('BUILD_DATE', (Path(tmp)/'build_id.v').read_text())
            cdf = (Path(tmp)/'jtag.cdf').read_text()
            self.assertIn('Device PartName(5CSEBA6U23I7)', cdf)
            self.assertIn('Path("output_files/") File("Groovy.sof")', cdf)
            stamp = (Path(tmp)/'build_id.v').stat().st_mtime_ns
            subprocess.run(['tclsh', str(script), str(ROOT/'sys/build_id.tcl')], cwd=tmp, check=True, capture_output=True, text=True)
            self.assertEqual((Path(tmp)/'build_id.v').stat().st_mtime_ns, stamp)


if __name__ == '__main__':
    unittest.main()
