#!/usr/bin/env python3
"""Compiler profile, manifest, PLL and preparation regression. No vendor tool execution."""
import copy
import csv
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
from physical.control import (expected_build_id, hardware_hashes, verify_version, digest,
                              accepted_compiler_version_metadata,
                              accepted_q25_postmap_serialization,
                              Q25_R0_POSTMAP_SHA256, create, freeze_generated, stage_inputs)
from physical.q25_ram_evidence import preflight, mapped
from physical.overlays import validate_recipe
from physical.diagnostics import collect
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

    def test_incomplete_native_q25_reports_fail_diagnostic_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'output_files'
            output.mkdir()
            (output/'provenance.json').write_text(json.dumps({
                'compiler_profile': 'q25', 'experiment': {'name': 'R0'},
                'hardware_manifest_sha256': 'fixture',
                'source_commit': 'fixture-source'})+'\n')
            result = collect(output)
            self.assertFalse(result['export_queries_complete'])
            self.assertEqual(result['unresolved_logical_bits'], 72)
            self.assertFalse(result['logical_ram_bits_complete'])
            self.assertFalse(result['q25_lz4_ram_evidence_present'])

    def test_a1_q25_requires_resource_ram_and_diagnostic_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, recipe = evidence(Path(tmp)/'q25')
            root = path.parent/'q25'
            seal_path = root/'evidence_manifest.json'
            seal = json.loads(seal_path.read_text())
            seal.update(compiler_profile='q25',
                        hardware_baseline='248d48ab625b04418fab1bc369c4cb60ff47fff1',
                        source_commit='fixture-q25-source',
                        hardware_manifest_sha256=digest(
                            (ROOT/'tests/physical/hardware_q25.json').read_bytes()))
            recipe.update(compiler_profile='q25',
                          r0_source_commit='fixture-q25-source')
            (root/'tool_version.txt').write_text(
                'Quartus Prime Shell\nVersion 25.1std.0 Build 1129 SJ Lite Edition\n')
            for name in ('source_manifest_prepared.json',
                         'source_manifest_before_map.json',
                         'source_manifest_before_fit.json'):
                (root/name).write_text('{}\n')
            states = {
                'resource_clock_gate.json': {'resource_clock_pass': False},
                'q25_window_ram_gate.json': {'compiler_profile': 'q25',
                                            'embedded_ram_inferred': False},
                'diagnostic_status.json': {'export_queries_complete': False,
                                           'video_requirements_pass': False},
            }
            def reseal():
                for name, value in states.items():
                    (root/name).write_text(json.dumps(value)+'\n')
                seal['files'] = {p.name: digest(p.read_bytes())
                                 for p in root.iterdir() if p.is_file() and p != seal_path}
                seal_path.write_text(json.dumps(seal, sort_keys=True)+'\n')
                recipe['r0_evidence_sha256'] = digest(seal_path.read_bytes())
                path.write_text(json.dumps(recipe)+'\n')
            reseal()
            with self.assertRaisesRegex(ValueError, 'resource/clock gate'):
                validate_recipe(path, root, 'A1', profile='q25')
            states['resource_clock_gate.json']['resource_clock_pass'] = True
            reseal()
            with self.assertRaisesRegex(ValueError, 'memory inference'):
                validate_recipe(path, root, 'A1', profile='q25')
            states['q25_window_ram_gate.json']['embedded_ram_inferred'] = True
            reseal()
            with self.assertRaisesRegex(ValueError, 'physical/video diagnostics'):
                validate_recipe(path, root, 'A1', profile='q25')

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
                mode = 'V1' if (linked/'tests/physical/q25_targeted_experiment.json').exists() and json.loads((linked/'tests/physical/q25_targeted_experiment.json').read_text())['experiment'] == 'V1' else 'C1' if (linked/'tests/physical/q25_targeted_experiment.json').exists() else 'R0'
                result = subprocess.run(['bash',str(linked/'tests/run_physical_timing_quartus.sh'),
                                         mode,'--profile','q25','--prepare-only'],
                                        cwd=linked,env=env,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
                self.assertEqual((out/'build_id.v').read_bytes(),expected_build_id())
                self.assertTrue((out/'output_files/source_manifest_before_map.json').exists())
                archive = root/'build-reports.tar.gz'
                self.assertTrue(archive.is_file())
            finally:
                subprocess.run(['git','-C',str(ROOT),'worktree','remove','--force',str(linked)],
                               check=True,capture_output=True)


class AssignmentDiscoveryNoVendor(unittest.TestCase):
    """Exercise Quartus support-mode Tcl in a plain Tcl interpreter."""

    def run_support(self, version, profile=None, unsafe_enumeration=True):
        with tempfile.TemporaryDirectory() as tmp:
            script = f'''
set quartus(args) {{support}}
set quartus(version) {{{version}}}
proc load_package {{args}} {{}}
proc get_all_assignment_names {{args}} {{
    {'error "unsafe Quartus enumeration invoked"' if unsafe_enumeration else 'return {PHYSICAL_SYNTHESIS_REGISTER_RETIMING}'}
}}
proc get_assignment_name_info {{name}} {{return "Accepted: OFF ON NEVER_ALLOW"}}
source {{{ROOT/'tests/physical/report_project.tcl'}}}
'''
            env = os.environ.copy()
            env.pop('PHYSICAL_COMPILER_PROFILE', None)
            if profile is not None:
                env['PHYSICAL_COMPILER_PROFILE'] = profile
            result = subprocess.run(['tclsh'], input=script, cwd=tmp,
                                    text=True, capture_output=True, env=env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            root = Path(tmp) / 'output_files/closure_diagnostics'
            with (root/'assignment_capabilities.tsv').open(newline='') as stream:
                rows = list(csv.DictReader(stream, delimiter='\t'))
            return rows, (root/'assignment_support.txt').read_text()

    def test_q25_avoids_native_internal_error_and_fails_closed(self):
        rows, log = self.run_support('Version 25.1std.0 Build 1129 SC Lite Edition', profile='q25')
        self.assertEqual(len(rows), 16)
        self.assertTrue(all(r['available'] == '0' for r in rows))
        self.assertTrue(all('UNVERIFIED' in r['metadata'] for r in rows))
        self.assertIn('get_all_assignment_names not invoked', log)
        self.assertNotIn('unsafe Quartus enumeration invoked', log)

    def test_q17_retains_original_metadata_discovery(self):
        rows, log = self.run_support('Version 17.0.2 Build 602', profile='q17', unsafe_enumeration=False)
        self.assertEqual(len(rows), 16)
        self.assertEqual(sum(r['available'] == '1' for r in rows), 4)
        self.assertEqual(sum(r['available'] == '0' for r in rows), 12)
        self.assertIn('Accepted: OFF ON NEVER_ALLOW', log)

    def test_nonmatching_q25_version_does_not_hide_discovery_errors(self):
        # A future toolchain needs its own observed compatibility decision.
        rows, log = self.run_support('25.2std.0', profile='q25')
        self.assertEqual(len(rows), 16)
        self.assertFalse(any(r['available'] == '1' for r in rows))
        self.assertTrue(all('UNVERIFIED' in r['metadata'] for r in rows))
        self.assertIn('get_all_assignment_names not invoked', log)


    def test_missing_profile_never_invokes_native_enumeration(self):
        rows, log = self.run_support('Version 25.1std.0 Build 1129 SC Lite Edition')
        self.assertTrue(all(r['available'] == '0' for r in rows))
        self.assertIn('Compiler profile: unknown', log)

    def test_wrong_profile_version_cannot_enable_q17_enumeration(self):
        rows, log = self.run_support('Version 25.1std.0 Build 1129 SC Lite Edition', profile='q17')
        self.assertTrue(all(r['available'] == '0' for r in rows))
        self.assertIn('get_all_assignment_names not invoked', log)

    def test_runner_exports_explicit_verified_profile(self):
        source = (ROOT/'tests/run_physical_timing_quartus.sh').read_text()
        self.assertIn('export PHYSICAL_COMPILER_PROFILE="$PROFILE"', source)
        self.assertLess(source.index('verify-version'), source.index('export PHYSICAL_COMPILER_PROFILE'))

class Q25CompilerMetadataGate(unittest.TestCase):
    """Only the observed Q17 to Q25 version stamp may be normalized."""
    old = ['global', '-name', 'LAST_QUARTUS_VERSION', '17.0.2 Lite Edition']
    new = ['global', '-name', 'LAST_QUARTUS_VERSION', '25.1std.0 Lite Edition']
    seed = ['global', '-name', 'SEED', '1']

    def test_exact_q25_version_marker_only(self):
        expected = [self.seed, self.old, ['global', '-name', 'DEVICE', '5CSEBA6U23I7']]
        actual = [self.seed, self.new, expected[-1]]
        result, record = accepted_compiler_version_metadata(expected, actual, 'q25')
        self.assertEqual(result, expected)
        self.assertEqual(record['assignment'], 'LAST_QUARTUS_VERSION')
        self.assertEqual(record['observed'], '25.1std.0 Lite Edition')
        self.assertEqual(actual[1], self.new)  # raw evidence is never altered
        for profile in ('q17', 'unknown'):
            self.assertEqual(accepted_compiler_version_metadata(expected, actual, profile), (actual, None))

    def test_reordered_duplicate_other_version_and_unrelated_drift_fail(self):
        expected = [self.seed, self.old]
        mutations = [
            [self.new, self.seed],
            [self.seed, self.new, self.new],
            [self.seed, self.old, self.new],
            [self.seed, self.old],
            [self.seed, ['global', '-name', 'LAST_QUARTUS_VERSION', '25.2 Lite Edition']],
            [['global', '-name', 'SEED', '2'], self.new],
            [self.seed, self.new, ['global', '-name', 'PHYSICAL_SYNTHESIS_REGISTER_RETIMING', 'OFF']],
        ]
        for rows in mutations:
            with self.subTest(rows=rows):
                normalized, accepted = accepted_compiler_version_metadata(expected, rows, 'q25')
                self.assertTrue(accepted is None or normalized != expected)


class PostMapQ25SerializationGate(unittest.TestCase):
    """Fixture is the real Quartus 25.1 R0 before-fit insertion, not a guess."""

    @classmethod
    def setUpClass(cls):
        fixture = json.loads((ROOT/'tests/physical/fixtures/q25_r0_postmap_serialization.json').read_text())
        cls.baseline = capture(ROOT, 'q25')['events']
        cls.pivot = cls.baseline.index(['global', '-name', 'QIP_FILE', 'sys/pll_q25.qip'])
        cls.block = []
        for index in fixture['source_event_indices']:
            if isinstance(index, int):
                cls.block.append(cls.baseline[index])
            else:
                original = cls.baseline[cls.pivot - 3 + int(index[1:])]
                cls.block.append(['hps_location', original[3], '-to', original[7]])

    @classmethod
    def with_block(cls, block=None):
        return cls.baseline[:cls.pivot] + (cls.block if block is None else block) + cls.baseline[cls.pivot:]

    def test_actual_quartus_serialization_is_accepted_and_audited(self):
        self.assertEqual(len(self.block), 237)
        self.assertEqual(digest(json.dumps(self.block, ensure_ascii=False, separators=(',', ':')).encode()),
                         Q25_R0_POSTMAP_SHA256)
        events = self.with_block()
        normalized, record = accepted_q25_postmap_serialization(
            self.baseline, events, 'q25', 'R0', 'before_fit')
        self.assertEqual(normalized, self.baseline)
        self.assertEqual(record['inserted_events'], 237)
        self.assertEqual(record['source_assignment_repeats'], 234)
        self.assertEqual(record['verified_hps_location_aliases'], 3)
        self.assertTrue(record['raw_assignment_capture_preserved'])
        self.assertEqual(events[self.pivot:self.pivot+237], self.block)

    def test_q17_and_other_stages_and_experiments_are_unchanged(self):
        events = self.with_block()
        for profile, experiment, phase in [('q17', 'R0', 'before_fit'),
                                           ('q25', 'R0', 'before_map'),
                                           ('q25', 'A1', 'before_fit'),
                                           ('q25', 'D1', 'before_fit')]:
            with self.subTest(profile=profile, experiment=experiment, phase=phase):
                result, record = accepted_q25_postmap_serialization(
                    self.baseline, events, profile, experiment, phase)
                self.assertEqual(result, events)
                self.assertIsNone(record)

    def test_unknown_or_modified_serialization_is_rejected(self):
        original = self.block
        modifications = [
            original[:-1],
            original + [original[-1]],
            original[:1] + [original[2], original[1]] + original[3:],
            original[:1] + [original[0]] + original[2:],
            original[:2] + [['global', '-name', 'SEED', '9']] + original[3:],
            [[*original[0][:3], 'unknown-hook']] + original[1:],
        ]
        index_hps = next(i for i, row in enumerate(original) if row[0] == 'hps_location')
        modifications.append(original[:index_hps] + [['hps_location', 'WRONG_SITE', '-to', 'hdmi_i2c']] + original[index_hps+1:])
        for block in modifications:
            with self.subTest(block_len=len(block), first=block[0]):
                result, record = accepted_q25_postmap_serialization(
                    self.baseline, self.with_block(block), 'q25', 'R0', 'before_fit')
                self.assertIsNone(record)
                self.assertNotEqual(result, self.baseline)
        shifted = self.baseline[:4] + original + self.baseline[4:]
        result, record = accepted_q25_postmap_serialization(self.baseline, shifted, 'q25', 'R0', 'before_fit')
        self.assertIsNone(record)
        modified = [list(row) for row in self.baseline]
        modified[0] = ['global', '-name', 'TOP_LEVEL_ENTITY', 'intruder']
        result, record = accepted_q25_postmap_serialization(modified, self.with_block(), 'q25', 'R0', 'before_fit')
        self.assertIsNone(record)

    def test_stage_gate_accepts_only_native_block_and_preserves_raw_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'build'
            create(ROOT, out, profile='q25')
            freeze_generated(out)
            stage_inputs(out, 'before_map')
            qsf = out/'Groovy.qsf'
            qsf.write_text(qsf.read_text().replace(
                'set_global_assignment -name LAST_QUARTUS_VERSION "17.0.2 Lite Edition"',
                'set_global_assignment -name LAST_QUARTUS_VERSION "25.1std.0 Lite Edition"'))
            def tcl_row(row):
                return 'set_' + row[0] + '_assignment ' + ' '.join('{' + str(v) + '}' for v in row[1:])
            with qsf.open('a') as stream:
                stream.write('\n' + '\n'.join(map(tcl_row, self.block)) + '\n')
            stage_inputs(out, 'before_fit')
            gate = json.loads((out/'output_files/input_gate_before_fit.json').read_text())
            self.assertTrue(gate['pass'])
            self.assertEqual(gate['accepted_postmap_serialization']['inserted_events_sha256'],
                             Q25_R0_POSTMAP_SHA256)
            raw = json.loads((out/'output_files/project_calls_before_fit.json').read_text())['events']
            self.assertEqual(raw[self.pivot:self.pivot+237], self.block)
            self.assertEqual(len(raw), len(self.baseline)+237)
            with qsf.open('a') as stream:
                stream.write('set_global_assignment -name SEED 9\n')
            with self.assertRaisesRegex(ValueError, 'Unapproved effective assignment'):
                stage_inputs(out, 'before_fit')


if __name__ == '__main__':
    unittest.main()
