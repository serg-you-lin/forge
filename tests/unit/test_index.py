# tests/unit/test_index.py
"""docs/INDEX.md aggiornato e regola di dipendenza rispettata (`scripts/gen_index.py --check`)."""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestCodeIndex(unittest.TestCase):

    def test_indice_aggiornato_e_layer_puliti(self):
        run = subprocess.run([sys.executable, str(ROOT / "scripts" / "gen_index.py"), "--check"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr
                         + "\n→ python scripts/gen_index.py, poi guarda la sezione Dependency rule")


if __name__ == "__main__":
    unittest.main()
