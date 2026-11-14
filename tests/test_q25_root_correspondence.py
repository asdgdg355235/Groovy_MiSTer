"""Source-backed R0 native excerpts, with negative evidence mutations."""
import copy,json
from pathlib import Path
import unittest
from physical.review_r0_phys import root_witness
FIXTURE=Path(__file__).parent/'physical/fixtures/root_operand_r0.json'
class RootCorrespondence(unittest.TestCase):
    def setUp(self):self.data=json.loads(FIXTURE.read_text())
    def review(self):
        d=self.data;return root_witness(d['mapped'],d['fitted'],d['source'])
    def test_native_d_clock_q_consumers(self):
        self.assertEqual(len(self.review()['fitted_root_captures']),2)
    def test_a_name_is_not_source_correspondence(self):
        self.data['source'][0]['source_file']='unrelated.sv(1078)'
        with self.assertRaisesRegex(ValueError,'source correspondence'):self.review()
    def test_missing_counter_input_or_capture_edges_are_rejected(self):
        self.data['mapped'].pop()
        with self.assertRaisesRegex(ValueError,'counter inputs'):self.review()
    def test_missing_q_or_clock_is_not_accepted(self):
        original=copy.deepcopy(self.data)
        for port in ['Q','CLK']:
            self.data=copy.deepcopy(original)
            self.data['fitted']=[r for r in self.data['fitted'] if r['port']!=port]
            with self.assertRaises(ValueError):self.review()
    def test_consumer_identity_is_not_inferred_from_oterm_name(self):
        for r in self.data['fitted']:
            if r['port']=='Q':r['peer']='unrelated_consumer'
        with self.assertRaisesRegex(ValueError,'consumers'):self.review()
if __name__=='__main__':unittest.main()
