"""Derived graph and selector fixtures, never vendor execution."""
import csv,json,tempfile,unittest
from pathlib import Path
from physical.graph import normalize,FIELDS
from physical.logical import resolve_registered,summarize,EXPECTED
from physical.diagnostics import table

class GraphRepair(unittest.TestCase):
 def row(self,edge='e1',dst='mux|a',expected='1'):
  return dict(zip(FIELDS,['ff|q','pin','FF_X1_Y1_N0',dst,'pin','LC_X1_Y2_N0','IC',expected,edge]))
 def run_graph(self,rows,processed=None):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'raw.tsv';table(p,FIELDS,[[r[k] for k in FIELDS] for r in rows]);before=p.read_bytes()
   if processed is not None:table(root/'processed.tsv',['source','source_type','source_location','expected_fanout','source_id'],processed)
   unique,result=normalize(p,root/'derived',root/'processed.tsv')
   self.assertEqual(before,p.read_bytes());return unique,result
 def test_exact_duplicate_is_lossless(self):
  row=self.row();u,a=self.run_graph([row,row]);self.assertEqual(len(u),1);self.assertEqual(a['duplicate_rows'],1);self.assertFalse(a['errors']);self.assertNotEqual(a['raw_sha256'],a['normalized_sha256'])
 def test_conflicting_global_edge_id_rejected(self):
  a=self.row();b=self.row(dst='mux|b');self.assertTrue(self.run_graph([a,b])[1]['errors'])
 def test_missing_and_inconsistent_fanout_rejected(self):
  self.assertTrue(self.run_graph([self.row(expected='2')])[1]['errors'])
  a=self.row();b=self.row('e2',expected='2');self.assertTrue(self.run_graph([a,b])[1]['errors'])
 def test_parallel_arcs_and_distinct_pins_preserved(self):
  a=self.row('e1','mux|a','3');b=self.row('e2','mux|b','3');c=self.row('e3','mux|a','3')
  u,r=self.run_graph([a,b,c]);self.assertEqual(len(u),3);self.assertFalse(r['errors'])
 def test_zero_source_is_observed_not_invented(self):
  u,r=self.run_graph([], [['empty|q','pin','FF_X1_Y1_N0','0','opaque_7']]);self.assertFalse(r['errors']);self.assertEqual(r['explicit_zero_fanout_sources'],1)
  self.assertTrue(self.run_graph([], [['empty|q','pin','FF_X1_Y1_N0','1','opaque_7']])[1]['errors'])
 def test_same_name_with_conflicting_type_location_rejected(self):
  a=self.row('e1',expected='2');b=self.row('e2',expected='2');b['source_location']='FF_X2_Y2_N0'
  self.assertTrue(self.run_graph([a,b])[1]['errors'])

class LogicalRepair(unittest.TestCase):
 def fixture(self):
  driver='physical|selected_bit';register='other_bank|retimed_selector'
  def row(node,port,peer,peer_port,bit=''):
   return dict(direction='INPUT',node=node,port=port,bit=bit,peer=peer,peer_port=peer_port,peer_bit='',fanout='1')
  target='physical|packed_ram[0].even_ram|rd_mux|last'
  fitted=[row('physical|packed_ram[2].even_ram|ram','PORTBADDR',driver,'COMBOUT','11'),row(register,'SDATA',driver,'COMBOUT'),row(register,'CLK','pll','OUTCLK'),row(target,'DATAB',register,'Q')]
  mapped=[row(target,'DATAC',driver,'COMBOUT')]
  return [[0,'even',11,'UNRESOLVED','','','','','','pending']],fitted,mapped
 def test_reviewed_register_dependency_without_name_guessing(self):
  b,f,m=self.fixture();out,chains=resolve_registered(b,f,m)
  self.assertEqual(out[0][3],'OBSERVED_REGISTERED_HIGH_BIT');self.assertEqual(chains[0]['register_crossings'],1);self.assertEqual(chains[0]['clock_node'],'pll')
  self.assertIn('PENDING',chains[0]['cycle_equivalence_status'])
 def test_missing_map_clock_or_q_is_unresolved(self):
  b,f,m=self.fixture()
  for fit,mapped in [(f,[]),([r for r in f if r['port']!='CLK'],m),([r for r in f if r['peer_port']!='Q'],m)]:
   self.assertEqual(resolve_registered(b,fit,mapped)[0][0][3],'UNRESOLVED')
 def test_actual_r0_selector_fixture(self):
  fixture=json.loads((Path(__file__).parent/'physical/fixtures/registered_bit11_r0.json').read_text())
  bits=[[0,b,11,'UNRESOLVED','','','','','','pending'] for b in ('even','odd')]
  result,chains=resolve_registered(bits,fixture['fitted'],fixture['mapped'])
  self.assertEqual(len(chains),2);self.assertTrue(all(r[3]=='OBSERVED_REGISTERED_HIGH_BIT' for r in result))
 def test_no_unrestricted_register_walk(self):
  b,f,m=self.fixture();f[-1]['peer']='a_second_register'
  self.assertFalse(resolve_registered(b,f,m)[1])
 def test_exact_key_set_not_physical_row_count(self):
  rows=[[p,b,n,'OBSERVED_RAM_PORT','ram','PORTBADDR','source','Q','1','observed'] for p,b,n in EXPECTED]
  summary,ok=summarize(rows+rows,[]);self.assertTrue(ok);self.assertEqual(len(summary),72)
  self.assertFalse(summarize(rows[:-1],[])[1]);self.assertFalse(summarize(rows+[['9','even','0','OBSERVED','','','','','','']],[])[1])
if __name__=='__main__':unittest.main()
