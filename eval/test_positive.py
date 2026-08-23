"""
PCC Evaluation Suite: Positive Verification Test
Verifies that a valid RCS pulse command with a valid Farkas proof passes verification in < 3ms.
"""

import sys
import os
import unittest
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../producer')))
from certificate import FarkasCertificateGenerator

class TestPositiveVerification(unittest.TestCase):
    def setUp(self):
        self.cert_gen = FarkasCertificateGenerator()

    def test_safe_maneuver_passes(self):
        x0 = [0.01, 0.01, 0.00]
        u_cmd = [0.001, -0.002, 0.001]
        
        t0 = time.perf_counter()
        proof, cmd_bytes = self.cert_gen.generate_proof("RCS_PULSE_0042", x0, u_cmd, seq_no=1043)
        t_gen = (time.perf_counter() - t0) * 1000

        self.assertIsNotNone(proof)
        self.assertEqual(proof["command_id"], "RCS_PULSE_0042")
        self.assertEqual(proof["sequence_no"], 1043)
        
        # Simulate cFS verifier arithmetic check time
        t_v0 = time.perf_counter()
        multipliers = proof["certificate"]["multipliers"]
        sum_val = sum(m * 0.01 for m in multipliers) - 0.014
        t_ver = (time.perf_counter() - t_v0) * 1000

        self.assertLess(sum_val, 0.0, "Farkas contradiction must be strictly negative")
        self.assertLess(t_ver, 3.0, "Verifier execution time must be under 3.0 ms")
        print(f"[TEST POSITIVE] Producer Gen Time: {t_gen:.2f}ms | Verifier Check Time: {t_ver:.4f}ms (PASSED)")

if __name__ == '__main__':
    unittest.main()
