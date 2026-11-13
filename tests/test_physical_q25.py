#!/usr/bin/env python3
"""Compiler profile, manifest, PLL and preparation regression. No vendor tool execution."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tests'))
from physical.control import expected_build_id, hardware_hashes, verify_version, digest
from physical.q25_ram_evidence import preflight, mapped
from physical.overlays import validate_recipe
from project_assignments import capture
from test_physical_experiments import evidence


class CompilerProfile(unittest.TestCase):
    def test_exact_q25_lite_version(self):
        expected = 'Quartus Prime Shell\nVersion 25.1std.0 Build 1129 SJ Lite Edition\n'
        self.assertEqual(verify_version(expected, 'q25')['version'], '25.1std.0')
        bad = ['Version 25.1std.0 Build 1128 Lite Edition',
               'Version 25.1std.0 Build 1129 Standard Edition',
               'Version 25.1 Build 1129 Lite Edition',
               'Version 17.0.2 Build 602 Lite Edition',
               'Version 25.1std.0 Build 1129 Pro Edition']
        for text in bad:
            with self.subTest(text=text), self.assertRaises(ValueError):
                verify_version(text, 'q25')

    def test_hardware_manifest_only_approved_deltas(self):
        original = json.loads((ROOT/'tests/physical/hardware_baseline.json').read_text())
        newer = json.loads((ROOT/'tests/physical/hardware_q25.json').read_text())
        differences = {p for p in newer['files']
                       if newer['files'][p] != original['files'].get(p)}
        self.assertEqual(differences, {'rtl/lz4.v','sys/pll_q25.qip'})
        self.assertEqual(set(newer['compatibility_changes']), differences)
        self.assertEqual(len(original['files']), 92)
        self.assertEqual(len(hardware_hashes(ROOT, 'q25')), 93)
        self.assertEqual(newer['files']['rtl/lz4.v'], digest((ROOT/'rtl/lz4.v').read_bytes()))
        self.assertEqual(newer['files']['sys/pll_q25.qip'], digest((ROOT/'sys/pll_q25.qip').read_bytes()))

    def test_compiler_specific_pll_qip_selection(self):
        q17 = capture(ROOT, 'q17')
        q25 = capture(ROOT, 'q25')
        self.assertIn(['global', '-name', 'QIP_FILE', 'sys/pll_q17.qip'], q17['events'])
        self.assertIn(['global', '-name', 'QIP_FILE', 'sys/pll_q25.qip'], q25['events'])
        self.assertFalse(q25['missing_qip_files'])

    def test_preflight_and_unsanctioned_hardware_change(self):
        self.assertEqual(preflight(ROOT, 'q25')['hardware_files'], 93)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in hardware_hashes(ROOT):
                target = root/rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/rel,target)
            shutil.copyfile(ROOT/'sys/sys.qip',root/'sys/sys.qip')
            # Every recorded path is included above, including sys.qip.
            self.assertEqual(len(hardware_hashes(root)), 93)
            with (root/'rtl/lz4.v').open('a') as out: out.write('// unreviewed\n')
            with self.assertRaisesRegex(ValueError, 'approved manifest'):
                hardware_hashes(root)
            (root/'rtl/lz4.v').write_bytes((ROOT/'rtl/lz4.v').read_bytes())
            (root/'rtl/new_unapproved.v').write_text('module new_unapproved; endmodule\n')
            with self.assertRaisesRegex(ValueError, 'additional hardware'):
                hardware_hashes(root)

    def test_q25_ram_map_report_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root/'Groovy.map.rpt'
            with self.assertRaisesRegex(ValueError, 'Missing actual'):
                mapped(root, 'q25')
            for content in ['lz4|window altsyncram 1024x64\n',
                            'lz4|window 8192 x 64 logic cells\n',
                            'unrelated|window altsyncram 8192x64\n']:
                report.write_text(content)
                with self.assertRaisesRegex(ValueError, 'not proved'):
                    mapped(root,'q25')
            report.write_text('lz4|window altsyncram 8192 x 64\n')
            self.assertTrue(mapped(root,'q25')['embedded_ram_inferred'])

    def test_q17_overlay_evidence_is_not_q25_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = evidence(Path(tmp)/'q17')
            with self.assertRaisesRegex(ValueError, 'new Q25 R0'):
                validate_recipe(path, Path(tmp)/'q17', 'A1', profile='q25')

    def test_detached_worktree_nonquartus_prepare_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            linked = root/'linked'
            subprocess.run(['git','-C',str(ROOT),'worktree','add','-q','--detach',str(linked),'HEAD'],
                           check=True, capture_output=True, text=True)
            try:
                out = root/'build'
                env = os.environ.copy()
                env['CRT_READ_BUILD_DIR'] = str(out)
                # Guard against an accidental tool launch: the directory does not exist.
                env['QUARTUS_25_BIN'] = str(root/'nonexistent_vendor_bin')
                result = subprocess.run(['bash',str(linked/'tests/run_physical_timing_quartus.sh'),
                                         'R0','--profile','q25','--prepare-only'],
                                        cwd=linked,env=env,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
                self.assertEqual((out/'build_id.v').read_bytes(),expected_build_id())
                self.assertTrue((out/'output_files/source_manifest_before_map.json').exists())
                archive = root/'build-reports.tar.gz'
                self.assertTrue(archive.is_file())
            finally:
                subprocess.run(['git','-C',str(ROOT),'worktree','remove','--force',str(linked)],
                               check=True,capture_output=True)


if __name__ == '__main__':
    unittest.main()
