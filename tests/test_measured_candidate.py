import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from project_assignments import ROOT, capture
from report_io_coverage import report
from configure_timing_variant import configure, VARIANTS, HDMI
from validate_timing_exports import validate
from validate_fitted_resources import inspect


class MeasuredCandidateTest(unittest.TestCase):
    def test_archive_hashes_retained(self):
        evidence=json.loads((ROOT/'docs/evidence/measured_plus0177_comparison.json').read_text())
        records=evidence['comparisons']['00136c5f03de63d80d8e78208bb6802cfe53c53d']['files']
        for name in ('rtl/CRT/crt_vsize_fixed.sv','rtl/CRT/crt_packed_ram.sv','rtl/lz4.v','rtl/vga.v'):
            row=next(r for r in records if r['path']==name)
            self.assertTrue(row['equal'])
            # The archived baseline stays immutable in Git; candidate CRT/VGA
            # transformations are checked by RTL comparison and arithmetic SMT.
            baseline=subprocess.check_output(['git','show','00136c5f03de63d80d8e78208bb6802cfe53c53d:'+name],cwd=ROOT)
            self.assertEqual(hashlib.sha256(baseline).hexdigest(), row['archived_sha256'])
            if name in ('rtl/CRT/crt_packed_ram.sv','rtl/lz4.v'):
                self.assertEqual((ROOT/name).read_bytes(),baseline)

    def test_effective_configuration(self):
        c=capture(ROOT)
        self.assertIn(['global','-name','TIMEQUEST_MULTICORNER_ANALYSIS','OFF'],c['unique'])
        self.assertIn(['global','-name','OPTIMIZE_MULTI_CORNER_TIMING','ON'],c['unique'])
        self.assertIn(['global','-name','DEVICE','5CSEBA6U23I7'],c['unique'])
        self.assertFalse(any('DUPLICATE_ATOM' in x for x in c['events']))
        self.assertEqual(len({tuple(x) for x in c['events'] if 'HPS_LOCATION' in x}),3)
        evidence=json.loads((ROOT/'docs/evidence/measured_plus0177_comparison.json').read_text())
        def canonical(row):
            if row[0]=='hps_location':
                return ('instance','-name','HPS_LOCATION',row[1],'-entity','sys_top',*row[2:])
            return tuple(row)
        measured={canonical(row['assignment']) for row in evidence['archived_project_calls']['calls'] if 'DUPLICATE_ATOM' not in row['assignment']}
        current={tuple(row) for row in c['unique'] if 'DUPLICATE_ATOM' not in row}
        self.assertEqual(measured-current,set())
        self.assertEqual(current-measured,{('global','-name','OPTIMIZE_MULTI_CORNER_TIMING','ON')})
        self.assertEqual(c['missing_qip_files'],[])

    def test_variants_only_change_the_named_factor(self):
        for variant in VARIANTS:
            with tempfile.TemporaryDirectory() as temp:
                dest=Path(temp)
                (dest/'sys').mkdir()
                shutil.copyfile(ROOT/'Groovy.qsf',dest/'Groovy.qsf')
                shutil.copyfile(ROOT/'sys/sys_top.v',dest/'sys/sys_top.v')
                for name in ('Groovy.sv','rtl/CRT/crt_vsize_fixed.sv','rtl/lz4.v','rtl/vga.v'):
                    (dest/name).parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(ROOT/name,dest/name)
                before={str(p.relative_to(dest)):p.read_bytes() for p in dest.rglob('*') if p.is_file()}
                configure(ROOT,dest,variant)
                changed={n for n,b in before.items() if (dest/n).read_bytes()!=b}
                expected={'candidate':set(),'baseline':{'Groovy.sv','rtl/CRT/crt_vsize_fixed.sv','rtl/vga.v'},
                    'read-add':{'rtl/CRT/crt_vsize_fixed.sv'},'delta-flat':{'Groovy.sv'},
                    'ready-shared':{'rtl/CRT/crt_vsize_fixed.sv'},'vga-old':{'rtl/vga.v'},
                    'dup-off':set(),'crt-new':{'rtl/CRT/crt_vsize_fixed.sv'},
                    'transport-new':{'rtl/lz4.v','rtl/vga.v'},'hdmi-old':{'sys/sys_top.v'},
                    'analysis-on':{'Groovy.qsf'},'fitter-slow':{'Groovy.qsf'}}[variant]
                self.assertEqual(changed,expected)

    def test_io_unknown_ports_cannot_disappear(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'io.txt'
            path.write_text('; Unconstrained Paths Summary ;\n; Unconstrained Input Ports ;\n; IO_SDA ; missing ;\n; Unconstrained Output Ports ;\n; NEW_PIN ; missing ;\n; LED[2] ; partial ;\n')
            result=report(path)
            self.assertFalse(result['release_qualified'])
            self.assertEqual(len(result['ports']),3)
            self.assertTrue(all(r['reason'] for r in result['ports']))

    def test_reject_incomplete_corner_export(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'corners.tsv').write_text('directory\tmodel\ttemperature\ncorner_01\tslow\t100\n')
            with self.assertRaisesRegex(ValueError,'operating corners'):
                validate(temp)

    def test_full_export_gate_detects_timing_and_inventory_failures(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            corners=[]; summaries=[]
            for n,(model,t) in enumerate(( (m,t) for m in ('slow','fast') for t in ('-40','0','85','100')),1):
                name=f'corner_{n:02d}'; folder=root/name; folder.mkdir()
                corners.append(f'{name}\t{model}\t{t}\t1100')
                for kind in ('setup','hold','recovery','removal'):
                    summaries.append(f'{name}\t{kind}\t0\t0.0\t0.1')
                    (folder/f'negative_{kind}_endpoints.tsv').write_text('to\tfrom\tslack_ns\n')
                    (folder/f'negative_{kind}_paths.txt').write_text('no paths')
                    (folder/f'worst_{kind}.txt').write_text('positive')
                (folder/'min_pulse_width.txt').write_text('; 0.100 ; 0.2 ; 0.1 ; High Pulse Width ;\n')
            (root/'corners.tsv').write_text('directory\tmodel\ttemperature\tvoltage\n'+'\n'.join(corners)+'\n')
            (root/'endpoint_summary.tsv').write_text('corner\tcheck\tfailing_endpoints\tendpoint_TNS_ns\tworst_slack_ns\n'+'\n'.join(summaries)+'\n')
            self.assertTrue(validate(root,False)['timing_pass'])
            (root/'report_format.txt').write_text('compact-v2\n')
            for c in range(1,9):
                folder=root/f'corner_{c:02d}'
                (folder/'min_pulse_coverage.tsv').write_text('exported_checks\tnegative_checks\tworst_slack_ns\tcomplete_negative_inventory\n1\t0\t0.1\t1\n')
                (folder/'negative_min_pulse_paths.txt').write_text('No negative checks.')
            self.assertTrue(validate(root,False)['timing_pass'])
            (root/'corner_01/min_pulse_coverage.tsv').unlink()
            with self.assertRaisesRegex(ValueError,'Missing pulse coverage'): validate(root,False)
            (root/'corner_01/min_pulse_coverage.tsv').write_text('exported_checks\tnegative_checks\tworst_slack_ns\tcomplete_negative_inventory\n1\t1\t-0.1\t1\n')
            (root/'corner_01/min_pulse_width.txt').write_text('; -0.100 ; 0.1 ; 0.2 ; High Pulse Width ;\n')
            self.assertFalse(validate(root,False)['timing_pass'])
            (root/'corner_02/negative_hold_endpoints.tsv').write_text('to\tfrom\tslack_ns\nsink\tlaunch\t-1\n')
            with self.assertRaisesRegex(ValueError,'count mismatch'):
                validate(root,False)

    def test_source_manifest_hashes_actual_overridden_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'source'; build=root/'build'
            source.mkdir(); (build/'output_files').mkdir(parents=True)
            subprocess.run(['git','init','-q',str(source)],check=True)
            (source/'input.sv').write_text('original\n')
            subprocess.run(['git','add','input.sv'],cwd=source,check=True)
            subprocess.run(['git','-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture'],cwd=source,check=True)
            (build/'input.sv').write_text('variant\n')
            (build/'output_files/build_variant.txt').write_text('crt-new\n')
            subprocess.run(['python3',str(ROOT/'tests/source_manifest.py'),str(source),str(build),'test'],check=True)
            result=json.loads((build/'output_files/source_manifest_test.json').read_text())
            self.assertEqual(result['variant'],'crt-new')
            self.assertEqual(result['files'][0]['sha256'],hashlib.sha256(b'variant\n').hexdigest())
            self.assertEqual((build/'output_files/source_inputs/input.sv').read_text(),'variant\n')

    def test_resource_gate_rejects_memory_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'timing_closure').mkdir()
            (root/'Groovy.fit.summary').write_text('Fitter Status : Successful\nDevice : 5CSEBA6U23I7\nTotal RAM Blocks : 553 / 553\n')
            (root/'Groovy.fit.rpt').write_bytes(b'; Total MLAB memory bits ; 491,520 ;\n100\xb0C\n')
            (root/'timing_closure/clocks.txt').write_text('; emu|pll|counter[0].output_counter|divclk ; Generated ; 12.081 ; 82.77 MHz ;\n')
            rows=['kind\tnode_id\tname\tport']
            for bank in range(3):
                for parity in ('even','odd'):
                    impl='altsyncram:block_ram' if bank==2 else 'altdpram:distributed'
                    rows.append(f'RAM_ADDRESS\t1\tpacked_ram[{bank}].{parity}_ram|{impl}\tPORTBADDR')
            (root/'crt_local_drivers_cmp.tsv').write_text('\n'.join(rows)+'\n')
            self.assertTrue(inspect(root)['resource_clock_pass'])
            (root/'Groovy.fit.rpt').write_text('; Total MLAB memory bits ; 491,521 ;\n')
            self.assertFalse(inspect(root)['resource_clock_pass'])


if __name__=='__main__': unittest.main()
