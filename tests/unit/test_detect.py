import unittest
import ezdxf
from pathlib import Path
import sys

import forge
from forge.adapters.dxf.layers import LAYER_HOLE, LAYER_INNER
from forge.rules.thresholds import HOLE_DIAMETER_THRESHOLD
from forge.model import (
    HOLE_TYPE_PLAIN,
    HOLE_TYPE_COUNTERSINK,
    HOLE_TYPE_THREADED,
)


project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

EXAMPLES_DIR = project_root / "tests" / "examples"


def load(name):
    return ezdxf.readfile(EXAMPLES_DIR / name)


print("\n=== EXAMPLES DIR ===")
for f in sorted(EXAMPLES_DIR.iterdir()):
    print(f.name)


# -------------------------------------------------------------------
# BASE DETECT BEHAVIOR
# -------------------------------------------------------------------

class TestDetectBase(unittest.TestCase):

    def setUp(self):
        doc = load("rect_with_circle_hole.dxf")
        self.msp = doc.modelspace()

        self.result = forge.heal(self.msp)
        forge.detect(self.result, self.msp)

    # ---------------------------------------------------------------
    # detect NON deve rompere heal
    # ---------------------------------------------------------------
    def test_001_structure_intact(self):
        self.assertEqual(self.result.part_count, 1)
        self.assertEqual(len(self.result.parts[0].holes), 1)

    # ---------------------------------------------------------------
    # hole deve essere classificato (NON UNKNOWN)
    # ---------------------------------------------------------------
    def test_002_hole_classified(self):
        hole = self.result.parts[0].holes[0]
        self.assertNotEqual(hole.hole_type, "unknown")

    # ---------------------------------------------------------------
    # consistenza diametro vs decisione detect
    # ---------------------------------------------------------------
    def test_003_diameter_rule(self):
        hole = self.result.parts[0].holes[0]

        if hole.diameter < HOLE_DIAMETER_THRESHOLD:
            self.assertEqual(hole.hole_type, HOLE_TYPE_PLAIN)

    # ---------------------------------------------------------------
    # detect è idempotente
    # ---------------------------------------------------------------
    def test_004_idempotent(self):
        hole = self.result.parts[0].holes[0]
        first = hole.hole_type

        forge.detect(self.result, self.msp)
        second = hole.hole_type

        self.assertEqual(first, second)


# -------------------------------------------------------------------
# COUNTERSINK
# -------------------------------------------------------------------

class TestDetectCountersink(unittest.TestCase):

    def setUp(self):
        doc = load("rect_with_countersink.dxf")
        self.msp = doc.modelspace()

        self.result = forge.heal(self.msp)
        forge.detect(self.result, self.msp)
        
    def test_001_countersink_detected(self):
        holes = self.result.parts[0].holes

        self.assertTrue(
            any(h.hole_type == HOLE_TYPE_COUNTERSINK for h in holes)
        )


# -------------------------------------------------------------------
# LABEL MAP (override assoluto)
# -------------------------------------------------------------------

class TestDetectLabelMap(unittest.TestCase):

    def setUp(self):
        doc = load("rect_special_countersink.dxf")
        self.msp = doc.modelspace()

        label_map = {
            "Svasati": "countersink"
        }

        self.result = forge.heal(self.msp, label_map=label_map)
        forge.detect(self.result, self.msp)

    def test_001_label_map_override(self):
        hole = self.result.parts[0].holes[0]

        self.assertEqual(hole.source, "labeled")
        self.assertEqual(hole.hole_type, HOLE_TYPE_COUNTERSINK)


# -------------------------------------------------------------------
# THREAD DETECTION (ARC logic)
# -------------------------------------------------------------------

class TestDetectThreaded(unittest.TestCase):

    def setUp(self):
        doc = load("rect_with_threaded_holes_geometric.dxf")
        self.msp = doc.modelspace()

        self.result = forge.heal(self.msp)
        forge.detect(self.result, self.msp)

    def test_001_thread_detected(self):
        holes = self.result.parts[0].holes

        self.assertTrue(
            any(h.hole_type == HOLE_TYPE_THREADED for h in holes)
        )


# -------------------------------------------------------------------
# FLANGE
# -------------------------------------------------------------------

class TestFlangeCountersink(unittest.TestCase):

    def setUp(self):
        doc = load("flangia semplice.DXF")
        self.result = forge.heal(doc.modelspace())
        forge.detect(self.result, doc.modelspace())

    def test_concentric_large_hole_is_not_countersink(self):
        part = self.result.parts[0]

        big_holes = [
            h for h in part.holes
            if h.diameter > HOLE_DIAMETER_THRESHOLD
        ]

        for h in big_holes:
            self.assertNotEqual(h.hole_type, HOLE_TYPE_COUNTERSINK)
            self.assertEqual(h.role, "inner")

    def test_flangia_struttura(self):
        self.assertEqual(len(self.result.parts), 1)

        part = self.result.parts[0]

        self.assertEqual(len(part.holes), 1)

        hole = part.holes[0]

        self.assertEqual(hole.role, "inner")
        self.assertEqual(hole.hole_type, HOLE_TYPE_PLAIN)
        self.assertNotEqual(hole.hole_type, HOLE_TYPE_COUNTERSINK)


if __name__ == "__main__":
    unittest.main(verbosity=2)