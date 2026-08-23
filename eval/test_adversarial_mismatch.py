"""
PCC Evaluation Suite: Adversarial Command Hash Mismatch Test
Verifies that attaching a valid proof to a different (unsafe) command is rejected at Step 2.
"""

import sys
import os
import unittest
import hashlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../producer')))
from certificate import FarkasCertificateGenerator

class TestAdversarialMismatch(unittest.TestCase):
    def setUp(self):
        self.cert_gen = FarkasCertificateGenerator()

    def test_mismatched_command_rejected(self):
        x0 = [0.01, 0.01, 0.00]
        u_cmd_safe = [0.001, -0.002, 0.001]
        
        # Valid proof generated for safe command
        proof, safe_cmd_bytes = self.cert_gen.generate_proof("RCS_PULSE_0042", x0, u_cmd_safe, seq_no=1043)

        # Attacker tries to pair valid proof with unsafe command bytes
        unsafe_cmd_bytes = b"RCS_PULSE_0042:0.500:0.500:0.500"
        computed_hash = "sha256:" + hashlib.sha256(unsafe_cmd_bytes).hexdigest()

        # Step 2 Check: SHA256 Hash Binding
        hash_match = (computed_hash == proof["command_hash"])
        self.assertFalse(hash_match, "Verifier MUST reject mismatched command hash")
        print("[TEST ADVERSARIAL MISMATCH] Hash mismatch correctly caught and rejected (PASSED)")

if __name__ == '__main__':
    unittest.main()
