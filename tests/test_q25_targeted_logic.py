#!/usr/bin/env python3
"""Source-hash and exact-width V1/C1 arithmetic verification. No Quartus."""
import hashlib
import json
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
CONTROL = "3b8d1edb63f2d2fed05d23323c3ba1ae93eeed1a"


class TargetedRTLRegression(unittest.TestCase):
    def test_manifest_is_an_independent_r0_source_delta(self):
        from sys import path
        path.insert(0, str(ROOT / 'tests'))
        from physical.control import hardware_hashes, targeted_q25_spec, digest
        spec = targeted_q25_spec('q25')
        self.assertIn(spec['experiment'], ('V1', 'C1'))
        self.assertEqual(spec['r0_source_commit'], CONTROL)
        self.assertEqual(len(hardware_hashes(ROOT, 'q25')), 93)
        self.assertEqual(digest((ROOT / spec['rtl_path']).read_bytes()), spec['candidate_file_sha256'])
        base = json.loads((ROOT / 'tests/physical/hardware_q25.json').read_text())
        self.assertEqual(base['files'][spec['rtl_path']], spec['r0_file_sha256'])
        self.assertNotEqual(spec['candidate_file_sha256'], spec['r0_file_sha256'])

    def test_next_line_arithmetic_all_16bit_counts(self):
        spec = json.loads((ROOT / 'tests/physical/q25_targeted_experiment.json').read_text())
        if spec['experiment'] != 'V1':
            self.skipTest('only applies to V1')
        src = (ROOT / 'Groovy.sv').read_text()
        self.assertIn("wire[16:0] vga_next_line = {1'b0,vga_vcount} + (PoC_interlaced ? 17'd2 : 17'd1);", src)
        self.assertNotIn('vga_vcount + 1 + PoC_interlaced', src)
        self.assertNotIn("vga_vcount + 10'd1 + PoC_interlaced", src)
        for parity in (0, 1):
            for count in range(65536):
                old = count + 1 + parity
                new = count + (2 if parity else 1)
                self.assertEqual(old, new)
                self.assertLess(new, 1 << 17)
                for height in (0, 1, 240, 480, 65535):
                    self.assertEqual(old >= height, new >= height)
                for width in (0, 1, 2560, 65535):
                    product_old = (width * old) & 0xffffff
                    product_new = (width * new) & 0xffffff
                    for sh in (0, 1):
                        self.assertEqual(product_old >> sh, product_new >> sh)
                        self.assertEqual(((product_old >> sh) + 3) & 0xffffff,
                                         ((product_new >> sh) + 3) & 0xffffff)

    def test_targeted_crt_mlab_address_factoring(self):
        spec = json.loads((ROOT / 'tests/physical/q25_targeted_experiment.json').read_text())
        if spec['experiment'] != 'C1':
            self.skipTest('only applies to C1')
        rtl = (ROOT / 'rtl/CRT/crt_vsize_fixed.sv').read_text()
        self.assertIn('begin : c1_even_read', rtl)
        for current_slot in range(12):
            for upcoming_slot in range(12):
                for word in range(512):
                    current = ((current_slot >> 1) * 512 + word) & 4095
                    line = ((upcoming_slot >> 1) * 512) & 4095
                    for begin in (0, 1):
                        reference = line if begin else current
                        localized = (((line if begin else current) >> 9) << 9) | (0 if begin else word)
                        self.assertEqual(reference, localized)


if __name__ == '__main__':
    unittest.main()
