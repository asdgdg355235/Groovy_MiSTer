"""Exact V2 fresh-snapshot source controls. Native compiler never runs here."""
import json,shutil,tempfile,unittest
from pathlib import Path
from physical.control import create,hardware_hashes,digest,freeze_generated,stage_inputs
from physical.variants import variant,apply_variant
ROOT=Path(__file__).resolve().parents[1]

class V2SourceVariant(unittest.TestCase):
    def test_only_root_operand_changes_and_r0_validation_stays_strict(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for rel in hardware_hashes(ROOT):
                p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,p)
            before=hardware_hashes(root);spec=apply_variant(root)
            after=hardware_hashes(root,'q25','V2')
            self.assertEqual({k for k in before if before[k]!=after[k]},{'Groovy.sv'})
            self.assertEqual(after['Groovy.sv'],spec['result_sha256'])
            self.assertEqual(before['rtl/vga.v'],after['rtl/vga.v'])
            with self.assertRaisesRegex(ValueError,'approved manifest'):hardware_hashes(root)
            with self.assertRaisesRegex(ValueError,'untouched R0'):apply_variant(root)
            (root/'rtl/vga.v').write_text('unexpected')
            with self.assertRaisesRegex(ValueError,'approved manifest'):hardware_hashes(root,'q25','V2')

    def test_v1_and_physical_overlays_are_not_source_variants(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'build'
            with self.assertRaisesRegex(ValueError,'Unknown physical'):create(ROOT,out,'V1')
            self.assertFalse(out.exists())
            with self.assertRaisesRegex(ValueError,'only the reviewed'):create(ROOT,out,'V2',overlay='nominal.json')
            self.assertFalse(out.exists())
        self.assertFalse((ROOT/'tests/physical/variants/V1.patch').exists())

    def test_fresh_candidate_elaboration_and_both_assignment_stages(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'build';p=create(ROOT,out,'V2')
            self.assertEqual(p['experiment']['name'],'V2');self.assertEqual(p['source_variant'],variant())
            self.assertEqual(p['control_hardware_hashes'],hardware_hashes(ROOT))
            freeze_generated(out);stage_inputs(out,'before_map')
            from physical.q25_ram_evidence import preflight
            self.assertEqual(preflight(out,'q25')['hardware_files'],93)
            from restart.language_gate import run
            self.assertEqual(run(out)['project_modes']['Groovy.sv'],'SYSTEMVERILOG_FILE')
            from test_physical_q25 import PostMapQ25SerializationGate
            PostMapQ25SerializationGate.setUpClass()
            qsf=out/'Groovy.qsf'
            qsf.write_text(qsf.read_text().replace('17.0.2 Lite Edition','25.1std.0 Lite Edition'))
            with qsf.open('a') as stream:
                for row in PostMapQ25SerializationGate.block:
                    stream.write('\nset_'+row[0]+'_assignment '+' '.join('{'+str(v)+'}' for v in row[1:]))
            stage_inputs(out,'before_fit')
            self.assertTrue(json.loads((out/'output_files/input_gate_before_fit.json').read_text())['pass'])
            with qsf.open('a') as stream:stream.write('\nset_global_assignment -name SEED 2\n')
            with self.assertRaisesRegex(ValueError,'Unapproved effective'):stage_inputs(out,'before_fit')

    def test_review_is_bound_to_exact_native_export(self):
        spec=variant();path=ROOT/'tests/physical/evidence/R0-PHYS-reviewed.json'
        self.assertEqual(spec['r0_phys_review_sha256'],digest(path.read_bytes()))
        review=json.loads(path.read_text())
        self.assertEqual(review['archive_sha256'],'ec067377ace04da1e7ce444b91f6dcd4639a4e8e11f9c6331f8b41f63cb29011')
        self.assertFalse(review['physical_assignment_approved'])
        self.assertEqual(review['C1'],'BLOCKED_LEGAL_SITE_AND_ASSIGNMENT_SCOPE')
if __name__=='__main__':unittest.main()
