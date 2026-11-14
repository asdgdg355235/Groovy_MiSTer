"""V2 has no speculative RTL or physical control. No vendor execution."""
import json
from pathlib import Path
import tempfile
import unittest
from physical.control import create,hardware_hashes,load_registry
ROOT=Path(__file__).resolve().parents[1]
class V2Gate(unittest.TestCase):
    def test_v2_cannot_prepare_even_with_nominal_recipe(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'candidate'
            with self.assertRaisesRegex(ValueError,'V2 blocked'):
                create(ROOT,out,'V2',overlay='fabricated.json',evidence='fabricated',profile='q25')
            self.assertFalse(out.exists())
    def test_v2_keeps_baseline_hardware_and_empty_recipe(self):
        hardware_hashes(ROOT,'q25')
        recipe=json.loads((ROOT/'tests/physical/candidates/V2.pending.json').read_text())
        self.assertEqual(recipe['assignments'],[]);self.assertIsNone(recipe['rtl_patch'])
        self.assertEqual(load_registry()['experiments']['V2']['status'],'blocked-evidence')
        self.assertFalse((ROOT/'tests/physical/variants/V1.patch').exists())
if __name__=='__main__':unittest.main()
