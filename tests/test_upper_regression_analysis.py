import hashlib,json,tempfile,unittest,subprocess
from pathlib import Path
from physical.analyze_upper_regressions import family,verify_extracted
class RegressionAnalysis(unittest.TestCase):
 def test_capture_does_not_erase_launch(self):
  self.assertEqual(family('delta','foo|r_vram_in2[2]'),'pixel decode capture; launch must be inspected')
 def test_partition_integrity(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'a').write_bytes(b'ab');(p/'b').write_bytes(b'cd')
   parts=[{'name':n,'bytes':2,'sha256':hashlib.sha256((p/n).read_bytes()).hexdigest()} for n in ['a','b']]
   (p/'report_archive_manifest.json').write_text(json.dumps({'files':[{'path':'x','bytes':4,'sha256':hashlib.sha256(b'abcd').hexdigest(),'parts':parts}]}))
   self.assertEqual(verify_extracted(p)['partitioned_files'],1)
   (p/'b').write_bytes(b'xx')
   with self.assertRaises(ValueError):verify_extracted(p)
 def test_tcl_complete_and_no_compile(self):
  p=Path(__file__).parent/'physical/report_upper_recovery.tcl';s=p.read_text()
  self.assertNotIn('execute_flow',s);self.assertIn('-through $pins',s)
  subprocess.run(['tclsh'],input='set f [open {'+str(p.resolve())+'}];if {![info complete [read $f]]} {exit 1}',text=True,check=True)
