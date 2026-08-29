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

        self.result = forge.heal(forge.document_from_msp(self.msp))
        forge.detect(self.result, features="all")

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

        forge.detect(self.result, features="all")
        second = hole.hole_type

        self.assertEqual(first, second)


# -------------------------------------------------------------------
# COUNTERSINK
# -------------------------------------------------------------------

class TestDetectCountersink(unittest.TestCase):

    def setUp(self):
        doc = load("rect_with_countersink.dxf")
        self.msp = doc.modelspace()

        self.result = forge.heal(forge.document_from_msp(self.msp))
        forge.detect(self.result, features="all")
        
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

        self.result = forge.heal(forge.document_from_msp(self.msp, label_map=label_map))
        forge.detect(self.result, features="all")

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

        self.result = forge.heal(forge.document_from_msp(self.msp))
        forge.detect(self.result, features="all")

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
        self.result = forge.heal(forge.document_from_msp(doc.modelspace()))
        forge.detect(self.result, features="all")

    def test_concentric_large_hole_is_not_countersink(self):
        part = self.result.parts[0]

        # D15: un cerchio Ø > max_drill_diameter non è più un Hole — resta un
        # contorno interno. Nessun foro deve risultare countersink qui.
        for h in part.holes:
            self.assertNotEqual(h.hole_type, HOLE_TYPE_COUNTERSINK)

    def test_flangia_struttura(self):
        self.assertEqual(len(self.result.parts), 1)

        part = self.result.parts[0]

        # Il cerchio centrale della flangia ha Ø > 32.1 → resta ForgeContour
        # inner, non viene promosso a foro (regola di processo, D15).
        self.assertEqual(len(part.holes), 0)
        self.assertEqual(len(part.inners), 1)
        self.assertEqual(part.inners[0].role, "inner")


# -------------------------------------------------------------------
# D15 — contratto parametrico di detect()
# -------------------------------------------------------------------

class TestDetectParametric(unittest.TestCase):

    def _healed(self, name="rect_with_circle_hole.dxf"):
        doc = load(name)
        return forge.heal(forge.document_from_msp(doc.modelspace()))

    def test_bare_detect_promotes_no_holes(self):
        # detect(result) nudo = solo topologia pulita + lane label_map.
        result = self._healed()
        forge.detect(result)
        self.assertEqual(sum(len(p.holes) for p in result.parts), 0)
        self.assertEqual(sum(len(p.inners) for p in result.parts), 1)

    def test_features_holes_promotes(self):
        result = self._healed()
        forge.detect(result, features="holes")
        self.assertEqual(sum(len(p.holes) for p in result.parts), 1)
        self.assertEqual(sum(len(p.inners) for p in result.parts), 0)

    def test_features_all_equivalent_to_holes_here(self):
        result = self._healed()
        forge.detect(result, features="all")
        self.assertEqual(sum(len(p.holes) for p in result.parts), 1)

    def test_max_drill_diameter_gates_promotion(self):
        # Con soglia sotto il Ø del foro, il cerchio resta contorno interno.
        result = self._healed()
        hole_d = None
        forge.detect(result, features="holes")
        hole_d = result.parts[0].holes[0].diameter

        result2 = self._healed()
        forge.detect(result2, features="holes", max_drill_diameter=hole_d - 1.0)
        self.assertEqual(len(result2.parts[0].holes), 0)
        self.assertEqual(len(result2.parts[0].inners), 1)

    def test_heal_and_detect_defaults_to_all(self):
        doc = load("rect_with_circle_hole.dxf")
        result = forge.heal_and_detect(forge.document_from_msp(doc.modelspace()))
        self.assertEqual(sum(len(p.holes) for p in result.parts), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)