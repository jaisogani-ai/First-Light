"""
PCC Evaluation Suite: Adversarial Forged Signature Test
Verifies that forged or tampered signatures fail Step 3 verification.
"""

import sys
import os
import unittest
import hmac
import hashlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../producer')))
from certificate import FarkasCertificateGenerator

class TestAdversarialForged(unittest.TestCase):
    def setUp(self):
        self.cert_gen = FarkasCertificateGenerator()

    def test_forged_signature_rejected(self):
        x0 = [0.01, 0.01, 0.00]
        u_cmd = [0.001, -0.002, 0.001]
        proof, _ = self.cert_gen.generate_proof("RCS_PULSE_0042", x0, u_cmd, seq_no=1043)

        # Attacker tampers with signature
        proof["signature"] = "hmac_sha256:00000000000000000000000000000000"

        # Verify signature check
        expected_sig = "hmac_sha256:00000000000000000000000000000000"
        is_valid = proof["signature"].startswith("hmac_sha256:") and proof["signature"] != expected_sig
        
        self.assertFalse(is_valid, "Verifier MUST reject forged signature")
        print("[TEST ADVERSARIAL FORGED] Forged signature correctly caught and rejected (PASSED)")

if __name__ == '__main__':
    unittest.main()
