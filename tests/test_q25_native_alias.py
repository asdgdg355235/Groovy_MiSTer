"""Plain Tcl model of distinct native tokens aliasing one physical pin."""
import csv,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class NativeAliases(unittest.TestCase):
 def test_seed_and_edge_token_alias_processed_once_with_explicit_zero(self):
  model='''
proc project_open {args} {}
proc project_close {} {}
proc create_timing_netlist {} {}
proc delete_timing_netlist {} {}
proc read_sdc {} {}
proc update_timing_netlist {} {}
proc get_nodes {args} {return {1 3 5}}
proc foreach_in_collection {var values body} {uplevel 1 [list foreach $var $values $body]}
proc get_node_info {flag id} {
 if {$flag eq "-name"} {return [dict get {1 A_q 2 B_pin 3 B_pin 4 C_reg 5 zero_q} $id]}
 if {$flag eq "-type"} {return [expr {$id==4 ? "reg" : "pin"}]}
 if {$flag eq "-location"} {return [expr {$id in {2 3} ? "LC_X2_Y2_N0" : "FF_X1_Y1_N0"}]}
 if {$flag eq "-fanout_edges"} {return [dict get {1 {e1} 2 {e2} 3 {e2} 5 {}} $id]}
}
proc get_edge_info {flag id} {
 if {$flag eq "-dst"} {return [dict get {e1 2 e2 4} $id]}
 if {$flag eq "-delay_type"} {return IC}
}
'''
  with tempfile.TemporaryDirectory() as d:
   model+='source {'+str(ROOT/'tests/physical/report_fanout.tcl')+'}\n'
   subprocess.run(['tclsh'],cwd=d,input=model,text=True,capture_output=True,check=True)
   root=Path(d)/'output_files/closure_diagnostics'
   def rows(name):
    with (root/name).open() as f:return list(csv.DictReader(f,delimiter='\t'))
   edges=rows('fanout_locations.tsv');self.assertEqual(len(edges),2)
   processed=rows('fanout_processed_sources.tsv');self.assertEqual(len(processed),3)
   self.assertEqual([r['source'] for r in processed if r['expected_fanout']=='0'],['zero_q'])
   self.assertEqual(len(rows('fanout_native_aliases.tsv')),1)
if __name__=='__main__':unittest.main()
