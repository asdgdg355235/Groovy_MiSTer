"""No Quartus execution: provenance, evidence gates, Tcl models and comparisons."""
from pathlib import Path
import copy
import csv
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'tests/restart'))
from physical.control import create, digest, expected_build_id, freeze_generated, hardware_hashes, stage_inputs, verify_generated, verify_version, write_json
from physical.diagnostics import collect, logical_bits, metadata, retiming, table
from physical.overlays import render, validate_recipe
from physical.compare import compare
from physical.application import audit
from validate_timing_exports import validate
from experiments import BASE, source_archive


def evidence(root, experiment='A1', source_type='register'):
    """Synthetic reviewed evidence exercises the gate; never hardware targets."""
    root.mkdir()
    original = 'fixture|u_vsize|position[0]' if experiment == 'A1' else 'fixture|PoC_lz4_delta_index[3]'
    fitted = original + '~fixture_physical'
    table(root / 'node_inventory.tsv', ['stage', 'name', 'short_name', 'type', 'creator', 'source_file', 'query_status'],
          [['pre_synthesis', original, original, source_type, 'user_entered', 'fixture.sv', 'OBSERVED'],
           ['post_synthesis', original, original, 'register', 'user_entered', 'fixture.sv', 'OBSERVED'],
           ['post_fitter', fitted, fitted, 'register', 'compiler_generated', '', 'OBSERVED']])
    table(root / 'assignment_capabilities.tsv', ['module', 'scope', 'name', 'available', 'metadata'],
          [['fit', 'instance', 'ADV_NETLIST_OPT_ALLOWED', '1', 'fixture enum NEVER_ALLOW ALWAYS_ALLOW']])
    (root / 'tool_version.txt').write_text('Quartus Prime Shell\nVersion 17.0.2 Build 602 SJ Lite Edition\n')
    (root / 'reviewed_native_export.txt').write_text('Synthetic unit-test cross-probe only. Legal fixture site LC_X1_Y1_N0.\n')
    table(root / 'fanout_locations.tsv', ['source', 'source_type', 'source_location', 'destination', 'destination_type', 'destination_location', 'edge_type', 'expected_fanout', 'edge_id'],
          [[fitted, 'reg', 'FF_X2_Y2_N0', 'fixture|mux', 'comb', 'LABCELL_X1_Y1_N0', 'ic', 1, 10]])
    table(root / 'fanout_seeds.tsv', ['family', 'node', 'type', 'location'], [['delta', fitted, 'reg', 'FF_X2_Y2_N0']])
    write_json(root / 'diagnostic_status.json', {'fanout_graph_complete': True})
    for phase in ('before_map', 'before_fit'): write_json(root / f'input_gate_{phase}.json', {'pass': True})
    seal = {'hardware_baseline': BASE, 'experiment': 'R0', 'generated_input': {'sha256': digest(expected_build_id())},
            'files': {p.name: digest(p.read_bytes()) for p in root.iterdir() if p.is_file()}}
    write_json(root / 'evidence_manifest.json', seal)
    requires = ['source_to_physical_correspondence', 'register_movement', 'assignment_scope_and_value'] if experiment == 'A1' else ['complete_selector_footprint', 'refill_decode_paths', 'legal_site_and_target']
    recipe = {'format': 'physical-overlay-v1', 'experiment': experiment, 'review_status': 'reviewed', 'reviewed_by': 'unit-test fixture',
              'rationale': 'Synthetic gate test, never a physical result', 'r0_evidence_sha256': digest((root / 'evidence_manifest.json').read_bytes()),
              'mechanism_evidence': {r: {'file': 'reviewed_native_export.txt', 'explanation': 'fixture only'} for r in requires},
              'correspondence': [{'rtl_node': original, 'fitted_node': fitted, 'status': 'reviewed', 'register_scope_verified': True, 'explanation': 'fixture cross-probe'}],
              'assignments': [{'kind': 'instance', 'name': 'ADV_NETLIST_OPT_ALLOWED', 'value': 'NEVER_ALLOW', 'target': original}]}
    if experiment == 'D1':
        recipe['assignments'] = [{'kind': 'location', 'name': 'LOCATION', 'value': 'LC_X1_Y1_N0', 'target': fitted}]
        recipe['legal_sites'] = {'LC_X1_Y1_N0': 'reviewed_native_export.txt'}
    path = root.parent / 'recipe.json'; write_json(path, recipe)
    return path, recipe


def timing_fixture(output, setup=(-0.2, -0.1), other_slack=0.1, new_family=False, hold_slack=None):
    """Eight-corner compact fixtures; no tool executables or physical claims."""
    root = output / 'timing_closure'; root.mkdir(parents=True)
    corners, summaries = [], []
    for i, (model, temp) in enumerate(((m, t) for m in ('slow', 'fast') for t in ('-40', '0', '85', '100')), 1):
        directory = f'corner_{i:02d}'; folder = root / directory; folder.mkdir()
        corners.append([directory, directory, model, '7' if model == 'slow' else 'M', '1100', temp])
        for kind in ('setup', 'hold', 'recovery', 'removal'):
            values = setup if kind == 'setup' and model == 'slow' else (other_slack,)
            if kind == 'hold' and hold_slack is not None: values = (hold_slack,)
            if isinstance(values, dict): values = values.get(temp, (-0.1,))
            entries = []
            for j, slack in enumerate(values):
                sink = f'fixture|u_vsize|packed_ram[{j}].odd_ram|capture'
                source = 'fixture|wcol'
                if new_family and kind == 'setup': sink, source = f'fixture|lz4|window_addr[{j}]', 'fixture|lz4|counter'
                entries.append([sink, source, slack, 11.0, 6, -0.2])
            negative = [e for e in entries if e[2] < 0]
            summaries.append([directory, kind, len(negative), sum(e[2] for e in negative), min(values)])
            header = ['to', 'from', 'slack_ns', 'data_delay_ns', 'logic_levels', 'clock_skew_ns']
            table(folder / f'negative_{kind}_endpoints.tsv', header, negative)
            table(folder / f'all_{kind}_endpoints.tsv', header, entries)
            (folder / f'negative_{kind}_paths.txt').write_text('synthetic complete fixture\n')
            (folder / f'worst_{kind}.txt').write_text('synthetic fixture\n')
        (folder / 'min_pulse_width.txt').write_text('; 0.100 ; 0.2 ; 0.1 ; High Pulse Width ;\n')
        for name in ('clock_transfers', 'wcol_setup', 'hb_setup', 'poc_v_setup', 'vga_setup', 'delta_index_setup',
                     'delta_framebuffer_setup', 'lz4_counters_setup', 'lz4_counter_launch_setup', 'lz4_compressed_setup'):
            (folder / (name + '.txt')).write_text('synthetic report\n')
    table(root / 'corners.tsv', ['directory', 'name', 'model', 'speed', 'voltage', 'temperature'], corners)
    table(root / 'endpoint_summary.tsv', ['corner', 'check', 'failing_endpoints', 'endpoint_TNS_ns', 'worst_slack_ns'], summaries)
    (root / 'endpoint_distribution_format.txt').write_text('physical-endpoints-v1\n')
    for name in ('clocks', 'constraints', 'ignored_constraints', 'check_timing', 'unconstrained'):
        (root / (name + '.txt')).write_text('synthetic report\n')
    (root / 'filters.tsv').write_text('synthetic filters\n')


class PhysicalControls(unittest.TestCase):
    def test_generated_bytes_are_exact_and_rewrite_is_detected(self):
        self.assertEqual(expected_build_id(), b'`define BUILD_DATE "261112"')
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); (root / 'output_files').mkdir()
            (root / 'build_id.v').write_bytes(b'new current date')
            freeze_generated(root); verify_generated(root)
            info = json.loads((root / 'output_files/generated_input_freeze.json').read_text())
            self.assertFalse(info['clock_modified']); self.assertIn('actual_timestamp_utc', info)
            (root / 'build_id.v').write_bytes(expected_build_id() + b'\n')
            with self.assertRaisesRegex(ValueError, 'Generated'): verify_generated(root)

    def test_exact_version_and_edition_without_launching_any_vendor_command(self):
        verify_version('Quartus Prime Shell\nVersion 17.0.2 Build 602 SJ Lite Edition\n')
        for text in ('Version 25.1 Build 1 Lite Edition', 'Version 17.0.2 Build 602 Standard Edition', 'Version 17.0.1 Build 602 Lite Edition'):
            with self.assertRaises(ValueError): verify_version(text)

    def test_repository_hardware_is_byte_identical(self):
        self.assertEqual(len(hardware_hashes(ROOT)), 93)
        self.assertEqual(len(hardware_hashes(ROOT, 'q25')), 93)

    def test_additional_hardware_cannot_bypass_baseline_hashes(self):
        import shutil
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for rel in hardware_hashes(ROOT):
                target = root / rel; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / rel, target)
            (root / 'rtl/unreviewed.sv').write_text('module unreviewed; endmodule\n')
            with self.assertRaisesRegex(ValueError, 'additional hardware'): hardware_hashes(root)

    def test_unknown_or_ungated_experiment_does_not_create_build(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / 'build'
            for name in ('not-an-experiment', 'A1', 'D1'):
                with self.assertRaises(ValueError): create(ROOT, out, name)
                self.assertFalse(out.exists())

    def test_clean_snapshot_frozen_stages_and_assignment_drift(self):
        with tempfile.TemporaryDirectory() as t:
            parent = Path(t); source = parent / 'source'; source.mkdir()
            # Compilation inputs only; archived release bitstreams are not
            # necessary to exercise preparation or project-call validation.
            import shutil
            for rel in hardware_hashes(ROOT):
                target = source / rel; target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / rel, target)
            subprocess.run(['git', 'init', '-q'], cwd=source, check=True)
            subprocess.run(['git', 'add', '.'], cwd=source, check=True)
            subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'], cwd=source, check=True)
            out = parent / 'build'; create(source, out)
            freeze_generated(out); stage_inputs(out, 'before_map')
            self.assertEqual((out / 'output_files/source_inputs/before_map/build_id.v').read_bytes(), expected_build_id())
            with self.assertRaisesRegex(ValueError, 'new'): create(source, out)
            with (out / 'Groovy.qsf').open('a') as f: f.write('\nset_global_assignment -name SEED 9\n')
            with self.assertRaisesRegex(ValueError, 'Unapproved'): stage_inputs(out, 'before_map')
            # Pre-fit must independently compare all effective sourced
            # assignments against the prepared Q25 R0 configuration.
            with self.assertRaisesRegex(ValueError, 'Unapproved'): stage_inputs(out, 'before_fit')
            # Native map can serialize an approved sourced option a second
            # time. It remains one factor; a different value must still fail.
            (out / 'Groovy.qsf').write_bytes((ROOT / 'Groovy.qsf').read_bytes())
            assignment = dict(kind='instance', name='ADV_NETLIST_OPT_ALLOWED', value='NEVER_ALLOW', target='fixture|u_vsize|position[0]')
            provenance = json.loads((out / 'output_files/provenance.json').read_text())
            provenance['experiment']['name'] = 'A1'; provenance['physical_overlay'] = {'assignments': [assignment]}
            write_json(out / 'output_files/provenance.json', provenance)
            control = out / 'output_files/control_evidence'; control.mkdir()
            shutil.copy2(out / 'output_files/control_project_calls_prepared.json', control / 'project_calls_before_map.json')
            line = '\nset_instance_assignment -name ADV_NETLIST_OPT_ALLOWED NEVER_ALLOW -to {fixture|u_vsize|position[0]}\n'
            with (out / 'Groovy.qsf').open('a') as f: f.write(line * 2)
            stage_inputs(out, 'before_map')
            gate = json.loads((out / 'output_files/input_gate_before_map.json').read_text())
            self.assertEqual(gate['reviewed_assignment_occurrences'][0]['count'], 2)
            with (out / 'Groovy.qsf').open('a') as f: f.write(line.replace('NEVER_ALLOW', 'ALWAYS_ALLOW'))
            with self.assertRaisesRegex(ValueError, 'Unapproved'): stage_inputs(out, 'before_map')

    def test_shell_and_tcl_syntax_only(self):
        subprocess.run(['bash', '-n', str(ROOT / 'tests/run_physical_timing_quartus.sh')], check=True)
        for script in (ROOT / 'tests/physical').glob('*.tcl'):
            check = 'set f [open $::env(TEST_TCL_FILE)]; set s [read $f]; close $f; puts [info complete $s]\n'
            r = subprocess.run(['tclsh'], input=check, text=True, capture_output=True, env={**os.environ, 'TEST_TCL_FILE': str(script)}, check=True)
            self.assertEqual(r.stdout.strip(), '1', str(script))


class PhysicalEvidence(unittest.TestCase):
    def test_native_quoted_metadata_survives_tsv(self):
        with tempfile.TemporaryDirectory() as t:
            script = 'source {' + str(ROOT / 'tests/physical/common.tcl') + '}\n'
            script += 'set f [physical::table result.tsv {name metadata}]\nphysical::row $f [list quoted {"OFF" or "ON"}]\nclose $f\n'
            subprocess.run(['tclsh'], input=script, text=True, cwd=t, capture_output=True, check=True)
            with (Path(t) / 'result.tsv').open() as f: row = next(csv.DictReader(f, delimiter='\t'))
            self.assertEqual(row['metadata'], '"OFF" or "ON"')

    def test_installed_metadata_tcl_ok_unsupported_is_not_acceptance(self):
        with tempfile.TemporaryDirectory() as t:
            model = '''
array set quartus {args support version 17.0.2}
proc load_package {args} {}
proc get_all_assignment_names {args} {return {ADV_NETLIST_OPT_ALLOWED}}
proc get_assignment_name_info {args} {return {INFO: assignment is not supported in this edition}}
'''
            model += 'source {' + str(ROOT / 'tests/physical/report_project.tcl') + '}\n'
            subprocess.run(['tclsh'], input=model, text=True, cwd=t, capture_output=True, check=True)
            with (Path(t) / 'output_files/closure_diagnostics/assignment_capabilities.tsv').open() as stream:
                observed = list(csv.DictReader(stream, delimiter='\t'))
            self.assertTrue(observed); self.assertTrue(all(r['available'] == '0' for r in observed))

    def test_observed_fixture_overlay_and_tcl_rendering(self):
        for name in ('A1', 'D1'):
            with tempfile.TemporaryDirectory() as t:
                root = Path(t) / 'evidence'; path, spec = evidence(root, name)
                self.assertEqual(validate_recipe(path, root, name), spec)
                # Ordinary Tcl model, not Quartus. Literal bus indices remain exact.
                script = 'proc set_instance_assignment {args} {puts $args}\nproc set_location_assignment {args} {puts $args}\n' + render(spec)
                r = subprocess.run(['tclsh'], input=script, text=True, capture_output=True, check=True)
                self.assertIn(spec['assignments'][0]['target'], r.stdout)

    def test_unreviewed_tampered_unmatched_or_global_overlay_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / 'evidence'; path, valid = evidence(root)
            modifications = [
                lambda s: s.update(review_status='pending'),
                lambda s: s.update(mechanism_evidence={}),
                lambda s: s['assignments'][0].update(kind='global'),
                lambda s: s['assignments'][0].update(target='*position*'),
                lambda s: s['assignments'][0].update(name='UNKNOWN_ASSIGNMENT'),
                lambda s: s['correspondence'][0].update(status='unresolved'),
                lambda s: s['correspondence'][0].update(register_scope_verified=False),
                lambda s: s['correspondence'][0].update(fitted_node='unobserved_generated_name'),
            ]
            for change in modifications:
                spec = copy.deepcopy(valid); change(spec); write_json(path, spec)
                with self.assertRaises(ValueError): validate_recipe(path, root, 'A1')
            write_json(path, valid)
            (root / 'node_inventory.tsv').write_text('tampered\n')
            with self.assertRaisesRegex(ValueError, 'changed'): validate_recipe(path, root, 'A1')

    def test_d1_requires_native_site_and_complete_footprint(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / 'evidence'; path, spec = evidence(root, 'D1')
            spec['legal_sites'] = {}; write_json(path, spec)
            with self.assertRaisesRegex(ValueError, 'legal-site'): validate_recipe(path, root, 'D1')

    def test_a1_rejects_a_comb_node_with_a_register_like_name(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / 'evidence'; path, spec = evidence(root, source_type='combinational')
            with self.assertRaisesRegex(ValueError, 'register objects'): validate_recipe(path, root, 'A1')

    def test_all_logical_bits_without_invented_mlab_high_ports(self):
        rows = []
        for part in range(3):
            for bank in ('even', 'odd'):
                for bit in range(12 if part == 2 else 5):
                    rows.append(dict(direction='INPUT', node=f'fixture|packed_ram[{part}].{bank}_ram|memory', port='PORTBADDR', bit=str(bit), peer=f'driver{bit}', peer_port='COMBOUT', fanout='3'))
        bits = logical_bits(rows)
        self.assertEqual(len(bits), 72)
        self.assertEqual(sum(r[3] == 'UNRESOLVED' for r in bits), 28)
        self.assertTrue(all(r[4] == '' for r in bits if r[0] < 2 and r[2] > 4))

    def test_high_bit_shared_between_banks_is_traced_by_connection_not_rtl_prefix(self):
        driver = 'fixture|packed_ram[1].local_ra_odd[9]~fixture'
        common = dict(direction='INPUT', peer=driver, peer_port='COMBOUT', peer_bit='0', fanout='3')
        observed = [dict(common, node='fixture|packed_ram[2].odd_ram|memory', port='PORTBADDR', bit='9'),
                    dict(common, node='fixture|packed_ram[0].odd_ram|read_mux', port='DATAA', bit='0')]
        found = [r for r in logical_bits(observed) if r[:3] == [0, 'odd', 9]]
        self.assertEqual(found[0][3], 'OBSERVED_HIGH_BIT_FANOUT')
        self.assertEqual(found[0][6], driver)

    def test_generated_name_and_ram_bit_do_not_become_rtl_correspondence(self):
        inv = [dict(stage='post_fitter', name='fixture|advance_rows~NEW_REG', short_name='advance_rows~NEW_REG', type='register', source_file='')]
        result = retiming(inv, [])
        self.assertEqual(result[0][0], ''); self.assertEqual(result[0][3], 'UNRESOLVED_ORIGINAL_REGISTER')
        atom = dict(direction='INPUT', node='fixture|dv_hs1_rtl_0|memory', port='PORTADATA', bit='7', peer='fixture|control[0][0]', peer_port='Q', peer_bit='0')
        result = metadata([atom], [])
        self.assertEqual(result[0][7], '')
        self.assertEqual(result[0][8], 'OBSERVED_EDGE_STAGE_MAPPING_PENDING')

    def test_tcl_graph_model_exports_all_edges_and_stops_at_registers(self):
        with tempfile.TemporaryDirectory() as t:
            model = '''
proc project_open {args} {}
proc project_close {} {}
proc create_timing_netlist {} {}
proc delete_timing_netlist {} {}
proc read_sdc {} {}
proc update_timing_netlist {} {}
proc get_nodes {patterns} {return {1}}
proc foreach_in_collection {var values body} {uplevel 1 [list foreach $var $values $body]}
proc get_node_info {flag id} {
    if {$flag eq "-name"} {return "fixture|node$id"}
    if {$flag eq "-location"} {return "FF_X${id}_Y1_N0"}
    if {$flag eq "-type"} {return [expr {$id in {1 3} ? "reg" : "comb"}]}
    if {$flag eq "-fanout_edges"} {return [dict get {1 {10 11} 2 {12} 3 {13}} $id]}
}
proc get_edge_info {flag id} {
    if {$flag eq "-dst"} {return [dict get {10 2 11 3 12 3 13 4} $id]}
    if {$flag eq "-delay_type"} {return ic}
}
'''
            model += 'source {' + str(ROOT / 'tests/physical/report_fanout.tcl') + '}\n'
            subprocess.run(['tclsh'], input=model, text=True, cwd=t, capture_output=True, check=True)
            with (Path(t) / 'output_files/closure_diagnostics/fanout_locations.tsv').open() as f:
                edges = list(csv.DictReader(f, delimiter='\t'))
            self.assertEqual({r['edge_id'] for r in edges}, {'10', '11', '12'})
            status = collect(Path(t) / 'output_files')
            self.assertTrue(status['fanout_graph_complete'])
            self.assertFalse(status['coverage_release_qualified'])

    def test_missing_export_is_pending_not_a_successful_diagnostic(self):
        with tempfile.TemporaryDirectory() as t:
            output = Path(t) / 'output_files'; output.mkdir()
            result = collect(output)
            self.assertFalse(result['fanout_graph_complete'])
            self.assertEqual(result['unresolved_logical_bits'], 72)
            self.assertIn('PENDING', (output / 'closure_diagnostics/assignment_support.txt').read_text())

    def test_video_uncertainty_is_measured_not_assumed(self):
        # Synthetic vendor-format rows exercise positive-path parsing too.
        def report(uncertainty):
            rows = [['From Node', 'fixture|position'], ['To Node', 'fixture|capture'],
                    ['Launch Clock', 'emu|pll|fixture'], ['Latch Clock', 'emu|pll|fixture'],
                    ['Setup Relationship', '12.081', '', '', '', '', ''],
                    ['Clock Skew', '-0.4', '', '', '', '', ''], ['Data Delay', '11.1', '', '', '', '', ''],
                    ['Number of Logic Levels', '', '6', '', '', '', ''],
                    ['Data', '', '', '', '', '', ''], ['Cell', '', '', '3.3', '', '', ''],
                    ['Routing Element', '', '', '7.8', '', '', ''], ['', '', '', '', '', '', 'data path'],
                    ['0', '0', '', 'CELL', '1', 'FF_X1_Y1_N0', 'fixture|position'],
                    ['0', '0', '', 'CELL', '1', 'FF_X2_Y1_N0', 'fixture|capture'],
                    ['0', str(-uncertainty), '', '', '', '', 'clock uncertainty']]
            return 'Path #1: Setup slack is 0.010 (MET)\n' + ''.join('; ' + ' ; '.join(r) + ' ;\n' for r in rows)
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / 'output_files'; root = out / 'timing_closure'; root.mkdir(parents=True)
            table(root / 'corners.tsv', ['directory'], [[f'corner_{i:02d}'] for i in range(1, 9)])
            for i in range(1, 9):
                p = root / f'corner_{i:02d}'; p.mkdir(); (p / 'crt_capture_setup.txt').write_text(report(0.2))
            self.assertTrue(collect(out)['video_requirements_pass'])
            (root / 'corner_08/crt_capture_setup.txt').write_text(report(0.1))
            self.assertFalse(collect(out)['video_requirements_pass'])

    def test_unmatched_or_ignored_assignment_is_invalid(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t); (out / 'closure_diagnostics').mkdir()
            write_json(out / 'physical_recipe.json', {'experiment': 'A1', 'assignments': [{'name': 'ADV_NETLIST_OPT_ALLOWED', 'target': 'fixture|position'}]})
            path = out / 'closure_diagnostics/target_matches_map.tsv'
            table(path, ['target', 'stage', 'matches', 'names'], [['fixture|position', 'pre_synthesis', 0, '']])
            with self.assertRaisesRegex(ValueError, 'INVALID'): audit(out, 'map')
            table(path, ['target', 'stage', 'matches', 'names'], [['fixture|position', 'pre_synthesis', 1, 'fixture|position']])
            (out / 'crt_read_address_compile.log').write_text('Warning: ADV_NETLIST_OPT_ALLOWED ignored on fixture|position\n')
            with self.assertRaisesRegex(ValueError, 'INVALID'): audit(out, 'map')


class PhysicalComparisons(unittest.TestCase):
    def test_rank_change_is_not_a_regression_and_missing_mechanism_is_pending(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); a, b = root / 'a', root / 'b'
            timing_fixture(a); timing_fixture(b, setup=(-0.05, -0.1))
            result = compare(a, b, True)
            self.assertTrue(result['timing_vector_acceptable'])
            self.assertEqual(result['verdict'], 'PENDING_EVIDENCE')
            self.assertTrue(result['rank_changes_not_automatic_regressions'])

    def test_one_corner_regression_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); a, b = root / 'a', root / 'b'
            timing_fixture(a)
            timing_fixture(b, setup={'-40': (-0.3,), '0': (-0.05,), '85': (-0.05,), '100': (-0.05,)})
            result = compare(a, b, True)
            self.assertEqual(result['verdict'], 'REJECT'); self.assertEqual(len(result['setup_regressions']), 1)

    def test_new_control_cannot_hide_regression_against_original_measurement(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); original, r0, candidate = root / 'original', root / 'r0', root / 'candidate'
            timing_fixture(original, setup=(-0.05,)); timing_fixture(r0, setup=(-0.3,)); timing_fixture(candidate, setup=(-0.1,))
            result = compare(r0, candidate, True, original)
            self.assertEqual(result['verdict'], 'REJECT')
            self.assertIn('published hardware-baseline', result['invalid_experiment'][0])

    def test_new_family_or_hold_failure_is_rejected(self):
        for new_family, hold in ((True, 0.1), (False, -0.01)):
            with tempfile.TemporaryDirectory() as t:
                root = Path(t); a, b = root / 'a', root / 'b'
                timing_fixture(a); timing_fixture(b, setup=(-0.05,), new_family=new_family, hold_slack=hold)
                self.assertEqual(compare(a, b, True)['verdict'], 'REJECT')

    def test_complete_endpoint_inventory_cannot_drop_a_failure(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / 'output_files'; timing_fixture(out)
            f = out / 'timing_closure/corner_01/all_setup_endpoints.tsv'
            f.write_text(f.read_text().splitlines()[0] + '\n')
            with self.assertRaisesRegex(ValueError, 'inventories disagree'): validate(out / 'timing_closure')


if __name__ == '__main__': unittest.main()
