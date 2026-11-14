"""Explicit V1/C1 identities and synthetic evidence gates, no vendor programs."""
import copy,json,shutil,subprocess,tempfile,unittest
from pathlib import Path
from physical.control import create,hardware_hashes,digest,stage_inputs,freeze_generated,write_json,profile_spec
from physical.variants import variant,apply_variant
from physical.overlays import validate_recipe
from physical.diagnostics import table
from test_physical_experiments import evidence
ROOT=Path(__file__).resolve().parents[1]

class SourceVariants(unittest.TestCase):
 def test_r0_source_and_manifest_stay_unchanged(self):
  self.assertEqual(len(hardware_hashes(ROOT)),93)
  self.assertEqual((ROOT/'rtl/vga.v').read_bytes(),subprocess.check_output(['git','show','3b8d1ed:rtl/vga.v'],cwd=ROOT))
 def test_v1_requires_exact_patch_and_only_one_reviewed_source_hash(self):
  if not (ROOT/'tests/physical/variants/V1.json').exists():
   with self.assertRaisesRegex(ValueError,'not present'):variant()
   return
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for rel in hardware_hashes(ROOT):
    target=root/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,target)
   apply_variant(root);actual=hardware_hashes(root,'q25','V1')
   self.assertEqual([p for p,h in actual.items() if h!=hardware_hashes(ROOT)[p]],['rtl/vga.v'])
   with self.assertRaises(ValueError):hardware_hashes(root)
   with (root/'Groovy.sv').open('a') as f:f.write('// unapproved')
   with self.assertRaises(ValueError):hardware_hashes(root,'q25','V1')
 def test_fresh_v1_preparation_and_input_gate(self):
  if not (ROOT/'tests/physical/variants/V1.json').exists():return
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'candidate';p=create(ROOT,out,'V1')
   self.assertEqual(p['experiment']['name'],'V1');self.assertEqual(p['source_variant'],variant())
   freeze_generated(out);stage_inputs(out,'before_map')
   self.assertEqual(digest((out/'rtl/vga.v').read_bytes()),variant()['result_sha256'])
 def test_pending_c1_never_creates_an_ordinary_control(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'candidate'
   with self.assertRaisesRegex(ValueError,'evidence gate'):create(ROOT,out,'C1')
   self.assertFalse(out.exists())


def c1_fixture(root):
 path,recipe=evidence(root,'D1');recipe['experiment']='C1';recipe['compiler_profile']='q25'
 recipe['r0_source_commit']='3b8d1edb63f2d2fed05d23323c3ba1ae93eeed1a'
 original='fixture|u_vsize|local_ra_even[3]';fitted='fixture|u_vsize|crt_read_1_even_bit3';pin=fitted+'|combout'
 table(root/'node_inventory.tsv',['stage','name','short_name','type','creator','source_file','query_status'],
  [[stage,node,node,'comb','synthetic','fixture.sv','OBSERVED'] for stage,node in [('pre_synthesis',original),('post_synthesis',fitted),('post_fitter',fitted)]])
 table(root/'assignment_capabilities.tsv',['module','scope','name','available','metadata'],[['fit','instance','LOCATION','1','SYNTHETIC Quartus 25.1 Lite instance scope fixture']])
 (root/'tool_version.txt').write_text('Version 25.1std.0 Build 1129 Lite Edition')
 table(root/'fanout_locations.tsv',['source','source_type','source_location','destination','destination_type','destination_location','edge_type','expected_fanout','edge_id'],
  [[pin,'pin','LC_X1_Y1_N0','fixture|ram'+str(i),'pin','LC_X2_Y2_N0','IC',3840,str(i)] for i in range(3840)])
 table(root/'fanout_seeds.tsv',['family','node','type','location'],[['crt',pin,'pin','LC_X1_Y1_N0'],['crt','fixture|vga|hb|q','pin','FF_X1_Y1_N0']])
 table(root/'placement_binding.tsv',['fitted_node','footprint_source_node','status'],[[fitted,pin,'OBSERVED']])
 table(root/'fanout_processed_sources.tsv',['source','expected_fanout'],[[pin,3840]])
 write_json(root/'diagnostic_status.json',{'fanout_graph_complete':True,'export_queries_complete':True,'video_requirements_pass':True})
 write_json(root/'resource_clock_gate.json',{'resource_clock_pass':True});write_json(root/'q25_window_ram_gate.json',{'embedded_ram_inferred':True,'compiler_profile':'q25'})
 for phase in ('prepared','before_map','before_fit'):write_json(root/f'source_manifest_{phase}.json',{'synthetic':True})
 recipe['assignments']=[{'kind':'location','name':'LOCATION','value':'LC_X1_Y1_N0','target':fitted}]
 recipe['correspondence']=[{'rtl_node':original,'fitted_node':fitted,'status':'reviewed','explanation':'synthetic fixture, not a physical approval'}]
 recipe['footprint_source_node']=pin
 requires=json.loads((ROOT/'tests/physical/registry.json').read_text())['experiments']['C1']['requires']
 recipe['mechanism_evidence']={k:{'file':'reviewed_native_export.txt','explanation':'synthetic fixture only'} for k in requires}
 seal=json.loads((root/'evidence_manifest.json').read_text());seal.update(hardware_baseline=profile_spec('q25')['hardware_baseline'],compiler_profile='q25',source_commit=recipe['r0_source_commit'],hardware_manifest_sha256=digest((ROOT/'tests/physical/hardware_q25.json').read_bytes()))
 seal['files']={p.name:digest(p.read_bytes()) for p in root.iterdir() if p.is_file() and p.name!='evidence_manifest.json'}
 write_json(root/'evidence_manifest.json',seal);recipe['r0_evidence_sha256']=digest((root/'evidence_manifest.json').read_bytes());write_json(path,recipe)
 return path,recipe

class C1EvidenceGate(unittest.TestCase):
 def test_all_reviewed_synthetic_evidence_is_required(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'evidence';p,recipe=c1_fixture(root)
   self.assertEqual(validate_recipe(p,root,'C1','q25'),recipe)
   recipe['footprint_source_node']='unobserved';write_json(p,recipe)
   with self.assertRaisesRegex(ValueError,'binding'):validate_recipe(p,root,'C1','q25')
 def test_no_speculative_overlay_is_distributed(self):
  recipe=json.loads((ROOT/'tests/physical/candidates/C1.pending.json').read_text())
  self.assertEqual(recipe['assignments'],[]);self.assertEqual(recipe['review_status'],'pending')
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):validate_recipe(ROOT/'tests/physical/candidates/C1.pending.json',d,'C1','q25')
 def test_old_compiler_and_missing_stage_are_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'evidence';p,recipe=c1_fixture(root);recipe['compiler_profile']='q17';write_json(p,recipe)
   with self.assertRaisesRegex(ValueError,'Quartus 25'):validate_recipe(p,root,'C1','q25')
if __name__=='__main__':unittest.main()
