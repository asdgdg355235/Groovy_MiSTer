"""Offline schemas & synthetic native interfaces. Never invoke vendor programs."""
import csv
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from physical.diagnostics import collect, table
from physical.graph import FIELDS
from physical.run_r0_phys import clone_database, validate_exports
from physical.recovery_analysis import endpoint_group, window_input, selected_footprints
ROOT=Path(__file__).resolve().parents[1]

class RecoveryExports(unittest.TestCase):
    def test_fresh_data_overrides_old_status_without_overwriting_old(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); old=root/'output'; raw=old/'closure_diagnostics'; raw.mkdir(parents=True)
            fresh=root/'fresh';fresh.mkdir()
            bad=['ff|q','pin','FF_X1_Y1_N0','mux|a','pin','LC_X1_Y2_N0','IC','2','edge']
            table(raw/'fanout_locations.tsv',FIELDS,[bad])
            good=list(bad);good[7]='1';table(fresh/'fanout_locations.tsv',FIELDS,[good])
            original=(raw/'fanout_locations.tsv').read_bytes()
            result=collect(old,root/'derived',raw_overrides=fresh)
            self.assertEqual(result['graph_errors'],[])
            self.assertEqual((raw/'fanout_locations.tsv').read_bytes(),original)
            self.assertIn('fanout_locations.tsv',json.loads((root/'derived/fresh_export_inputs.json').read_text()))
            self.assertNotEqual((root/'derived/fanout_locations.tsv').read_bytes(),original)
            with self.assertRaises(ValueError):collect(old,raw,raw_overrides=fresh)

    def test_database_snapshot_has_no_hardlinks_and_rejects_reuse(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);build=root/'build';(build/'db').mkdir(parents=True)
            (build/'db/state').write_text('sealed');(build/'Groovy.qsf').write_text('source')
            clone_database(build,root/'query')
            (root/'query/db/state').write_text('native metadata')
            self.assertEqual((build/'db/state').read_text(),'sealed')
            with self.assertRaises(ValueError):clone_database(build,root/'query')
            with self.assertRaises(ValueError):clone_database(build,build/'inside')

    def test_partial_native_exports_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with self.assertRaisesRegex(ValueError,'Missing fresh'):validate_exports(root)

    def test_synthetic_path_schema_and_all_corners(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            script='''
proc project_open {args} {}
proc project_close {} {}
proc create_timing_netlist {} {}
proc delete_timing_netlist {} {}
proc read_sdc {} {}
proc update_timing_netlist {} {}
proc get_available_operating_conditions {args} {return {1 2 3 4 5 6 7 8}}
proc get_operating_conditions_info {args} {return "native_corner_[lindex $args end]"}
proc set_operating_conditions {args} {}
proc foreach_in_collection {var values body} {uplevel 1 [list foreach $var $values $body]}
proc get_keepers {args} {return {native_object}}
proc get_collection_size {args} {return 1}
proc get_timing_paths {args} {return {native_path}}
proc get_node_info {args} {return [lindex $args end]}
proc get_path_info {field args} {
 switch -- $field {
  -from {return native_launch}
  -to {return native_capture}
  -slack {return 0.123}
  -data_delay {return 11.0}
  -num_logic_levels {return 7}
  -clock_skew {return -0.2}
  default {error "Unmodeled native field $field"}
 }
}
proc report_timing {args} {
 set i [lsearch -exact $args -file];set out [open [lindex $args [expr {$i+1}]] w]
 puts $out "SYNTHETIC ONLY";close $out
}
'''
            script+='source {'+str(ROOT/'tests/physical/report_recovery_paths.tcl')+'}\n'
            result=subprocess.run(['tclsh'],input=script,text=True,capture_output=True,
                                  env={**os.environ,'R0_PHYS_EXPORT_DIR':str(root)},check=True)
            self.assertEqual(result.stderr,'')
            def rows(name):
                with (root/'recovery_paths'/name).open() as f:return list(csv.DictReader(f,delimiter='\t'))
            self.assertEqual(len(rows('corners.tsv')),8)
            self.assertEqual(len(rows('endpoints.tsv')),72)
            self.assertTrue(all(r['status']=='OBSERVED' for r in rows('filters.tsv')))
            self.assertEqual(rows('query_errors.tsv'),[])
            # Prove partial native output cannot become a completed diagnostic run.
            schemas={'atom_ports_map.tsv':['direction','node','port','peer','peer_port','node_id','peer_id'],
                     'atom_ports_cmp.tsv':['direction','node','port','peer','peer_port','node_id','peer_id'],
                     'fanout_locations.tsv':['source','destination','edge_id','source_id','destination_id'],
                     'fanout_processed_sources.tsv':['source','expected_fanout','source_id'],
                     'source_correspondence.tsv':['stage','native_id','name','type','source_file','status']}
            for name,header in schemas.items():table(root/name,header,[['synthetic']*len(header)])
            (root/'fanout_export_status.tsv').write_text('header\n')
            table(root/'correspondence_errors.tsv',['stage','native_id','field','error'],[])
            validate_exports(root)
            table(root/'recovery_paths/query_errors.tsv',['corner','family','error'],[['corner_01','vga_root','unsupported']])
            with self.assertRaisesRegex(ValueError,'query failed'):validate_exports(root)

    def test_footprints_keep_parallel_arcs_and_reject_missing_loads(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);header=FIELDS
            a=['fixture|crt_read_1_even_bit3|combout','pin','LC_X1_Y1_N0',
               'load|a','pin','MLAB_X2_Y2_N0','IC','2','e1']
            b=a.copy();b[-1]='e2'
            table(root/'raw.tsv',header,[a,a,b])
            result=selected_footprints(root/'raw.tsv',root/'derived.tsv')
            self.assertEqual(next(iter(result.values()))['unique_pin_arcs'],2)
            table(root/'raw.tsv',header,[a,a])
            with self.assertRaisesRegex(ValueError,'Incomplete selected driver'):
                selected_footprints(root/'raw.tsv',root/'derived.tsv')

    def test_window_classification_does_not_accept_arbitrary_ram(self):
        self.assertFalse(window_input({'to':'other|ram|porta_datain_reg0'}))
        r={'to':'emu:emu|lz4:lz4|altsyncram:window_rtl_0|ram_block~porta_datain_reg0'}
        self.assertTrue(window_input(r));self.assertEqual(endpoint_group(r),'lz4-window-write')

if __name__=='__main__':unittest.main()
