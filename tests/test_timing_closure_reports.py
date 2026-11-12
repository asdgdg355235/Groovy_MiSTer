#!/usr/bin/env python3
"""Exercise report control flow with Tcl stand-ins; never launches Quartus."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
set calls [open calls.txt w]
proc project_open {args} {if {$args ne {Groovy -revision Groovy}} {error "project/revision"}}
proc create_timing_netlist {} {}
proc read_sdc {} {}
proc update_timing_netlist {} {}
proc delete_timing_netlist {} {}
proc project_close {} {}
proc post_message {args} {error "Unexpected unmatched filter: $args"}
proc get_available_operating_conditions {args} {
    if {$args ne {-all}} {error "corner coverage"}
    return {slow_hot slow_cold slow_warm slow_zero fast_cold fast_zero fast_warm fast_hot}
}
proc foreach_in_collection {var collection body} {
    upvar 1 $var item
    foreach item $collection {uplevel 1 $body}
}
proc get_collection_size {collection} {llength $collection}
proc get_operating_conditions_info {flag op} {return $op}
proc set_operating_conditions {op} {puts $::calls "CORNER $op"}
proc get_registers {args} {return {matched_register}}
proc get_keepers {args} {return {keeper1 keeper2}}
proc get_ports {args} {return {port1}}
proc get_clocks {args} {return {clock1 clock2}}
proc get_node_info {flag id} {return $id}
proc get_timing_paths {args} {
    if {[lsearch -exact $args -less_than_slack]>=0} {
        if {[lsearch -exact $args -npaths]<0 || [lindex $args [expr {[lsearch -exact $args -npaths]+1}]]!=0} {error "truncated endpoint query"}
        if {[lsearch -exact $args -setup]<0} {return {}}
        set result {}; for {set i 1} {$i<=45} {incr i} {lappend result $i}; return $result
    }
    return {1}
}
proc get_path_info {flag id} {
    switch $flag {
        -to {return sink$id}
        -from {return launch$id}
        -slack {return -0.1}
        -data_delay {return 12.0}
        -num_logic_levels {return 6}
        default {error "unsupported path API $flag"}
    }
}
proc report {name args} {
    puts $::calls "$name $args"
    set ix [lsearch -exact $args -file]
    if {$ix<0} {error "missing report filename"}
    set f [open [lindex $args [expr {$ix+1}]] w]
    if {$name eq "report_min_pulse_width"} {
        set count [lindex $args [expr {[lsearch -exact $args -nworst]+1}]]
        # More failures than the initial bound: require adaptive expansion.
        for {set i 0} {$i < min($count,75)} {incr i} {
            puts $f "; [expr {$i<70 ? -0.1 : 0.1}] ; 1.0 ; 1.1 ; High Pulse Width ;"
        }
    } else {puts $f "$name $args"}
    close $f
}
foreach name {report_clocks report_sdc check_timing report_ucp report_timing report_min_pulse_width report_clock_transfers} {
    proc $name {args} [format {eval [linsert $args 0 report %s]} $name]
}
source [lindex $argv 0]
close $calls
'''


class ReportFlowTest(unittest.TestCase):
    def test_all_corners_and_more_than_thirty_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            harness = tmp/'standin.tcl'
            harness.write_text(HARNESS)
            subprocess.run(['tclsh', str(harness), str(ROOT/'tests/report_timing_closure.tcl')],
                           cwd=tmp, check=True, capture_output=True, text=True)
            root = tmp/'output_files/timing_closure'
            summary = (root/'endpoint_summary.tsv').read_text().splitlines()
            self.assertEqual(len(summary), 33)
            self.assertEqual(sum('\tsetup\t45\t-4.500000\t' in row for row in summary), 8)
            for corner in (f'corner_{n:02d}' for n in range(1,9)):
                self.assertEqual(len((root/corner/'negative_setup_endpoints.tsv').read_text().splitlines()), 46)
                for kind in ('setup', 'hold', 'recovery', 'removal'):
                    self.assertIn('-npaths 0', (root/corner/f'negative_{kind}_paths.txt').read_text())
                for family in ('wcol', 'column_flag', 'hb', 'poc_v', 'delta_index', 'lz4_compressed', 'lz4_counters'):
                    self.assertTrue((root/corner/f'{family}_setup.txt').exists())
                self.assertIn('\t70\t-0.1\t1', (root/corner/'min_pulse_coverage.tsv').read_text())
                self.assertEqual((root/corner/'negative_min_pulse_paths.txt').read_text().count('; -0.1 ;'),70)
                self.assertIn('-npaths 10',(root/corner/'lz4_counter_launch_setup.txt').read_text())
            self.assertEqual((tmp/'calls.txt').read_text().count('CORNER '), 8)
            self.assertIn('pll_cross_check', (root/'check_timing.txt').read_text())
            self.assertEqual(len((root/'corners.tsv').read_text().splitlines()), 9)

    def test_pulse_parser_rejects_truncation_and_unsorted_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp)
            for text in ('; 0.1 ;\nTRUNCATED\n','; 0.1 ;\n; -0.1 ;\n','no checks'):
                (tmp/'pulse.txt').write_text(text)
                script=f'source {{{ROOT}/tests/compact_pulse_report.tcl}}\npulse_slacks {{{tmp}/pulse.txt}}\n'
                (tmp/'test.tcl').write_text(script)
                p=subprocess.run(['tclsh',str(tmp/'test.tcl')],capture_output=True)
                self.assertNotEqual(p.returncode,0)


if __name__ == '__main__':
    unittest.main()
