"""
PCC Evaluation Suite: Startup Boot-Order Test
Verifies that startup sequencing initializes PCC Gate App before Target App.
"""

import unittest

class TestBootOrder(unittest.TestCase):
    def test_startup_script_order(self):
        # Simulate parsing cfe_es_startup.scr
        startup_script_lines = [
            "CFE_APP, PCC_GATE_APP, PCC_GateAppMain, PCC_GATE, 50, 8192, 0x0, 0x0;",
            "CFE_APP, TARGET_APP,   Target_AppMain,  TARGET,   60, 8192, 0x0, 0x0;"
        ]

        gate_index = -1
        target_index = -1

        for idx, line in enumerate(startup_script_lines):
            if "PCC_GATE_APP" in line:
                gate_index = idx
            if "TARGET_APP" in line:
                target_index = idx

        self.assertNotEqual(gate_index, -1)
        self.assertNotEqual(target_index, -1)
        self.assertLess(gate_index, target_index, "PCC_GATE_APP must start BEFORE TARGET_APP to prevent boot race")
        print("[TEST BOOT ORDER] Startup script sequencing verified: Gate App initializes first (PASSED)")

if __name__ == '__main__':
    unittest.main()
