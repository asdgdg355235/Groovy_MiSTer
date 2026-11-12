"""No vendor executables: source snapshots, language rejection & lossless caps."""
from pathlib import Path
import io,json,os,subprocess,sys,tarfile,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests/restart'))
from experiments import BASE,CORE,PROTECTED,apply,baseline,registry,sha,source_archive
from language_gate import run
from package_reports import MAX_MEMBER,pack,verify_or_restore
from prepare_build import prepare,record

class RestartWorkflow(unittest.TestCase):
 def test_lossless_size_caps_and_roundtrip(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);reports=root/'reports';reports.mkdir()
   (reports/'negative_setup_paths.txt').write_bytes(bytes(range(256))*50)
   (reports/'lz4_counter_launch_setup.txt').write_bytes(b'positive data\n'*500)
   (reports/'negative_setup_endpoints.tsv').write_text('to\tfrom\tslack\n'+'capture\tlaunch\t-1\n'*100)
   archive=root/'reports.tar.gz';m=pack(reports,archive,4096,2048)
   self.assertTrue(any(len(f['parts'])>1 for f in m['files']))
   with tarfile.open(archive) as a:self.assertTrue(all(x.size<=4096 for x in a.getmembers()))
   verify_or_restore(archive,root/'restored')
   for f in reports.iterdir():self.assertEqual(f.read_bytes(),(root/'restored/output_files'/f.name).read_bytes())

 def test_each_patch_changes_only_its_named_baseline_file(self):
  data=source_archive(ROOT,BASE)
  for name,spec in registry().items():
   with tempfile.TemporaryDirectory() as t:
    root=Path(t)
    with tarfile.open(fileobj=io.BytesIO(data)) as a:a.extractall(root,filter='data')
    apply(root,name)
    changed=[p for p in PROTECTED+CORE if (root/p).read_bytes()!=baseline(p)]
    self.assertEqual(changed,[spec['path']]);self.assertEqual(sha((root/spec['path']).read_bytes()),spec['result_sha256'])
    with self.assertRaises(ValueError):apply(root,name)

 def test_default_two_hundred_mib_cap(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);reports=root/'reports';reports.mkdir()
   with (reports/'negative_setup_paths.txt').open('wb') as f:f.truncate(MAX_MEMBER+7)
   archive=root/'large.tar.gz';result=pack(reports,archive)
   self.assertEqual([p['bytes'] for p in result['files'][0]['parts']],[MAX_MEMBER,7])
   verify_or_restore(archive)

 def test_failed_compile_is_archived_without_timing_claim(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'failed';out=root/'output_files';out.mkdir(parents=True)
   (out/'compile.log').write_text('Error (10170): Verilog HDL syntax error\n')
   subprocess.run([sys.executable,str(ROOT/'tests/restart/finalize_build.py'),str(root),'3','mapping'],check=True,capture_output=True)
   state=json.loads((out/'build_state.json').read_text())
   self.assertFalse(state['compilation_completed']);self.assertFalse(state['timing_results_available'])
   self.assertEqual(state['runner_exit_code'],3)
   result=verify_or_restore(str(root)+'-reports.tar.gz')
   self.assertIn('compile.log',[f['path'] for f in result['files']])

 def test_dirty_snapshot_requires_explicit_mode_and_hashes_actual_bytes(self):
  data=source_archive(ROOT,BASE)
  with tempfile.TemporaryDirectory() as t:
   parent=Path(t);source=parent/'source';source.mkdir()
   with tarfile.open(fileobj=io.BytesIO(data)) as a:a.extractall(source,filter='data')
   subprocess.run(['git','init','-q'],cwd=source,check=True)
   subprocess.run(['git','add','.'],cwd=source,check=True)
   subprocess.run(['git','-c','user.name=Fixture','-c','user.email=test@example.invalid','commit','-qm','source'],cwd=source,check=True)
   p=source/'rtl/vga.v';p.write_text(p.read_text()+'\n// explicit local test\n')
   (source/'db').mkdir();(source/'db/old.qdb').write_bytes(b'old database')
   with self.assertRaisesRegex(ValueError,'differs from HEAD'):prepare(source,parent/'rejected','baseline')
   result=prepare(source,parent/'build','working-tree',True)
   self.assertTrue(result['dirty']);self.assertFalse((parent/'build/db').exists())
   before=json.loads((parent/'build/output_files/source_manifest_prepared.json').read_text())
   row=next(x for x in before['files'] if x['path']=='rtl/vga.v')
   self.assertEqual(row['sha256'],sha(p.read_bytes()))
   (parent/'build/rtl/vga.v').write_text('later stage\n')
   record(parent/'build','after')
   self.assertEqual((parent/'build/output_files/source_inputs/prepared/rtl/vga.v').read_bytes(),p.read_bytes())
   self.assertEqual((parent/'build/output_files/source_inputs/after/rtl/vga.v').read_text(),'later stage\n')

 def test_actual_modes_reject_the_previous_sized_cast(self):
  result=run(ROOT)
  self.assertEqual(result['project_modes']['rtl/vga.v'],'VERILOG_FILE')
  self.assertIn('former sized cast rejected in Verilog, accepted in SystemVerilog',result['checks'])

 def test_default_hardware_is_unmodified_baseline(self):
  for p in PROTECTED+CORE:self.assertEqual((ROOT/p).read_bytes(),baseline(p))

if __name__=='__main__':unittest.main()
