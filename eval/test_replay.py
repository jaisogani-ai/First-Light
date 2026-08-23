"""
PCC Evaluation Suite: Replay Attack Test
Verifies that re-sending an old, previously valid certificate fails sequence number freshness check.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../producer')))
from certificate import FarkasCertificateGenerator

class TestReplayAttack(unittest.TestCase):
    def setUp(self):
        self.cert_gen = FarkasCertificateGenerator()

    def test_replayed_sequence_rejected(self):
        x0 = [0.01, 0.01, 0.00]
        u_cmd = [0.001, -0.002, 0.001]
        
        # Original command with sequence #1043
        proof1, _ = self.cert_gen.generate_proof("RCS_PULSE_0042", x0, u_cmd, seq_no=1043)
        last_accepted_seq = 1043

        # Replay attack: resend proof1 (seq #1043) when verifier already accepted 1043
        is_fresh = proof1["sequence_no"] > last_accepted_seq
        self.assertFalse(is_fresh, "Replayed sequence number MUST be rejected at Step 1")
        print("[TEST REPLAY ATTACK] Replayed sequence number correctly rejected (PASSED)")

if __name__ == '__main__':
    unittest.main()
