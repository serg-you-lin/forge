"""
tests/integration/test_pipeline.py
----------------------------------

Test semantic pipeline integrity.

Usa solo file generati in:
tests/data/
"""

import sys
from pathlib import Path
import unittest

TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_DIR))

from test_helpers import (
    run_pipeline,
    count_entities_on_layer,
)

EXAMPLES_DIR = TEST_DIR.parent / "data"



def ex(name: str) -> str:
    """
    Resolve path to example DXF.
    """
    path = EXAMPLES_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing example file: {path}. "
            f"Run generate_examples.py first."
        )
    return str(path)


class TestSpecialLayersWithoutDetect(unittest.TestCase):
    """
    Senza detect_flat(), le entità su layer non-strutturale vanno in Trash.
    """

    def setUp(self):
        self.pipeline = run_pipeline(
            ex("la_104.dxf"),
            do_write=True,
        )

    def test_001_mark_goes_to_trash_without_detect(self):
        # Il layer sorgente "MARK" non compare mai nel documento materializzato.
        msp = self.pipeline["msp"]
        mark_count = count_entities_on_layer(msp, "MARK")
        self.assertEqual(mark_count, 0)

    def test_002_trash_has_entities(self):
        # Senza detect_flat(), la geometria non strutturale resta nel modello
        # come trash_entities (non più spostata su un layer "Trash" del msp).
        result = self.pipeline["result"]
        self.assertGreater(len(result.trash_entities), 0)

if __name__ == "__main__":
    unittest.main(verbosity=2)