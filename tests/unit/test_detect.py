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
        self.assertEqual(self.result.cluster_count, 1)
        self.assertEqual(len(self.result.clusters[0].holes), 1)

    # ---------------------------------------------------------------
    # hole deve essere classificato (NON UNKNOWN)
    # ---------------------------------------------------------------
    def test_002_hole_classified(self):
        hole = self.result.clusters[0].holes[0]
        self.assertNotEqual(hole.hole_type, "unknown")

    # ---------------------------------------------------------------
    # consistenza diametro vs decisione detect
    # ---------------------------------------------------------------
    def test_003_diameter_rule(self):
        hole = self.result.clusters[0].holes[0]

        if hole.diameter < HOLE_DIAMETER_THRESHOLD:
            self.assertEqual(hole.hole_type, HOLE_TYPE_PLAIN)

    # ---------------------------------------------------------------
    # detect è idempotente
    # ---------------------------------------------------------------
    def test_004_idempotent(self):
        hole = self.result.clusters[0].holes[0]
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
        holes = self.result.clusters[0].holes

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
        hole = self.result.clusters[0].holes[0]

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
        holes = self.result.clusters[0].holes

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
        cluster = self.result.clusters[0]

        # D15: un cerchio Ø > max_drill_diameter non è più un Hole — resta un
        # contorno interno. Nessun foro deve risultare countersink qui.
        for h in cluster.holes:
            self.assertNotEqual(h.hole_type, HOLE_TYPE_COUNTERSINK)

    def test_flangia_struttura(self):
        self.assertEqual(len(self.result.clusters), 1)

        cluster = self.result.clusters[0]

        # Il cerchio centrale della flangia ha Ø > 32.1 → resta ForgeContour
        # inner, non viene promosso a foro (regola di processo, D15).
        self.assertEqual(len(cluster.holes), 0)
        self.assertEqual(len(cluster.inners), 1)
        self.assertEqual(cluster.inners[0].role, "inner")


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
        self.assertEqual(sum(len(p.holes) for p in result.clusters), 0)
        self.assertEqual(sum(len(p.inners) for p in result.clusters), 1)

    def test_features_holes_promotes(self):
        result = self._healed()
        forge.detect(result, features="holes")
        self.assertEqual(sum(len(p.holes) for p in result.clusters), 1)
        self.assertEqual(sum(len(p.inners) for p in result.clusters), 0)

    def test_features_all_equivalent_to_holes_here(self):
        result = self._healed()
        forge.detect(result, features="all")
        self.assertEqual(sum(len(p.holes) for p in result.clusters), 1)

    def test_max_drill_diameter_gates_promotion(self):
        # Con soglia sotto il Ø del foro, il cerchio resta contorno interno.
        result = self._healed()
        hole_d = None
        forge.detect(result, features="holes")
        hole_d = result.clusters[0].holes[0].diameter

        result2 = self._healed()
        forge.detect(result2, features="holes", max_drill_diameter=hole_d - 1.0)
        self.assertEqual(len(result2.clusters[0].holes), 0)
        self.assertEqual(len(result2.clusters[0].inners), 1)

    def test_heal_and_detect_defaults_to_all(self):
        doc = load("rect_with_circle_hole.dxf")
        result = forge.heal_and_detect(forge.document_from_msp(doc.modelspace()))
        self.assertEqual(sum(len(p.holes) for p in result.clusters), 1)


# -------------------------------------------------------------------
# LINETYPE_MAP / COLOR_MAP — seconda lane di classificazione, sull'aspetto
# grezzo invece che sul nome layer (usata solo dove label_map non decide).
# -------------------------------------------------------------------

class TestDetectStyleMap(unittest.TestCase):

    def _rect_with_internal_lines(self, extra_dxfattribs_line1, extra_dxfattribs_line2):
        doc = ezdxf.new("R2010")
        doc.linetypes.add("DASHED", pattern=[0.5, 0.25, -0.25], description="dashed")
        msp = doc.modelspace()
        msp.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True)
        # linea interna, ep entrambi lontani dal bordo — solo il ruolo conta
        msp.add_line((20, 20), (80, 80), dxfattribs=extra_dxfattribs_line1)
        msp.add_line((20, 80), (80, 20), dxfattribs=extra_dxfattribs_line2)
        return msp

    def test_001_dashed_linetype_becomes_bending(self):
        msp = self._rect_with_internal_lines(
            {"linetype": "DASHED"}, {},
        )
        doc = forge.document_from_msp(msp, linetype_map={"DASHED": "bending"})
        result = forge.heal(doc)
        forge.detect(result)

        cluster = result.clusters[0]
        self.assertEqual(len(cluster.bending_lines), 1)
        self.assertEqual(cluster.bending_lines[0].role.value, "bending")

    def test_002_cyan_color_becomes_engrave(self):
        msp = self._rect_with_internal_lines(
            {}, {"color": 4},  # 4 = cyan ACI
        )
        doc = forge.document_from_msp(msp, color_map={"cyan": "engrave"})
        result = forge.heal(doc)
        forge.detect(result)

        cluster = result.clusters[0]
        self.assertEqual(len(cluster.engrave_lines), 1)
        self.assertEqual(cluster.engrave_lines[0].role.value, "engrave")

    def test_003_color_map_accepts_aci_int_and_numeric_string(self):
        for key in (4, "4"):
            msp = self._rect_with_internal_lines({}, {"color": 4})
            doc = forge.document_from_msp(msp, color_map={key: "engrave"})
            result = forge.heal(doc)
            forge.detect(result)
            self.assertEqual(len(result.clusters[0].engrave_lines), 1, msg=f"key={key!r}")

    def test_004_label_map_wins_over_color_map(self):
        # label_map resta la lane autoritativa (D5): se il layer già assegna
        # un ruolo, linetype_map/color_map non intervengono più.
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        msp.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True)
        msp.add_line((20, 20), (80, 80), dxfattribs={"layer": "Piega", "color": 4})

        forge_doc = forge.document_from_msp(
            msp,
            label_map={"Piega": "bending"},
            color_map={"cyan": "engrave"},
        )
        result = forge.heal(forge_doc)
        forge.detect(result)

        cluster = result.clusters[0]
        self.assertEqual(len(cluster.bending_lines), 1)
        self.assertEqual(len(cluster.engrave_lines), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)