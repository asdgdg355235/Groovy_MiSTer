"""Synthetic native API models and no-vendor preparation tests."""
import csv,json,os,subprocess,tempfile,unittest
from pathlib import Path
from physical.run_r0_phys import prepare,BASE
from physical.control import digest,expected_build_id
from test_physical_experiments import timing_fixture
ROOT=Path(__file__).resolve().parents[1]
class ReadOnlyExports(unittest.TestCase):
 def test_native_atoms_keep_inputs_outputs_and_tokens(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);env={**os.environ,'R0_PHYS_EXPORT_DIR':str(root/'new')}
   script='''
array set quartus {args cmp}
proc load_package {args} {}
proc project_open {args} {}
proc project_close {} {}
proc read_atom_netlist {args} {}
proc foreach_in_collection {var values body} {uplevel 1 [list foreach $var $values $body]}
proc get_atom_nodes {} {return {1}}
proc get_atom_node_info {args} {
 set id [lindex $args 1]
 if {$id==1} {return {emu:emu|vga:vga|v_cnt[12]_native}} else {return {emu:emu|Add17~actual}}
}
proc get_atom_iports {args} {return {10}}
proc get_atom_oports {args} {return {20}}
proc get_atom_port_info {args} {
 set key [lindex $args end]
 if {$key eq "type"} {return D}
 if {$key eq "literal_index"} {return 12}
 if {$key eq "fanin"} {return {2 20}}
 if {$key eq "fanout"} {return {{2 10}}}
}
'''
   script+='source {'+str(ROOT/'tests/physical/report_atoms.tcl')+'}\n'
   result=subprocess.run(['tclsh'],cwd=root,env=env,input=script,text=True,capture_output=True,check=True)
   with (root/'new/atom_ports_cmp.tsv').open() as f:rows=list(csv.DictReader(f,delimiter='\t'))
   self.assertEqual({r['direction'] for r in rows},{'INPUT','OUTPUT'});self.assertTrue(all(r['node_id']=='1' and r['peer_id']=='2' for r in rows))
 def test_prepare_never_probes_vendor_and_refuses_existing_outputs(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);build=root/'build';out=build/'output_files';out.mkdir(parents=True)
   provenance={'source_commit':BASE,'compiler_profile':'q25','experiment':{'name':'R0'},'generated_input':{'sha256':digest(expected_build_id())}}
   (out/'provenance.json').write_text(json.dumps(provenance));(out/'crt_read_address_tool_version.txt').write_text('Version 25.1std.0 Build 1129 Lite Edition')
   commands,request,reports=prepare(build,root/'new',True)
   self.assertEqual([c[0] for c in commands],['quartus_sh','quartus_cdb','quartus_sta'])
   self.assertFalse(request['quartus_executed']);self.assertIn('UNVERIFIED',request['assignment_capabilities'])
   with self.assertRaises(ValueError):prepare(build,root/'new',True)
   provenance['source_commit']='other';(out/'provenance.json').write_text(json.dumps(provenance))
   with self.assertRaisesRegex(ValueError,'exact Q25'):prepare(build,root/'other',True)
 def test_hazardous_assignment_enumeration_stays_disabled(self):
  text=(ROOT/'tests/physical/report_project.tcl').read_text()
  self.assertIn('safe_q17_enumeration',text);self.assertIn('enumeration disabled',text)
if __name__=='__main__':unittest.main()
