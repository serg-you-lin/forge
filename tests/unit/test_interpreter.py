"""
Test Suite per BendingLine

Test puri sul modello — non richiedono file DXF né ezdxf.
Usiamo un fake entity per isolare la logica da ezdxf.

Lancia:
    python -m unittest tests/test_bending_line.py -v
"""

import unittest
import math
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from shapely.geometry import LineString
from dxf_forge.models import BendingLine
from dxf_forge.rules.interpreter import bending_line_from_entity


# ---------------------------------------------------------------------------
# Fake entity — isola i test da ezdxf
# ---------------------------------------------------------------------------

class _FakeDxf:
    def __init__(self, start, end, layer="PIEGA"):
        self.start = type("V", (), {"x": start[0], "y": start[1]})()
        self.end   = type("V", (), {"x": end[0],   "y": end[1]})()
        self.layer = layer

    def hasattr(self, name):
        return hasattr(self, name)


class _FakeEntity:
    def __init__(self, start, end, layer="PIEGA"):
        self.dxf = _FakeDxf(start, end, layer)


# ---------------------------------------------------------------------------
# Test BendingLine costruzione
# ---------------------------------------------------------------------------

class TestBendingLineConstruction(unittest.TestCase):

    def test_001_length_horizontal(self):
        """Lunghezza corretta per BL orizzontale."""
        entity = _FakeEntity((0, 0), (100, 0))
        bl = bending_line_from_entity(entity)
        print(f"\n[BendingLine] length={bl.length}")
        self.assertAlmostEqual(bl.length, 100.0, places=4)

    def test_002_length_diagonal(self):
        """Lunghezza corretta per BL diagonale (3-4-5)."""
        entity = _FakeEntity((0, 0), (30, 40))
        bl = bending_line_from_entity(entity)
        print(f"[BendingLine] length diagonal={bl.length}")
        self.assertAlmostEqual(bl.length, 50.0, places=4)

    def test_003_angle_horizontal(self):
        """Angolo 0° per BL orizzontale."""
        entity = _FakeEntity((0, 0), (100, 0))
        bl = bending_line_from_entity(entity)
        print(f"[BendingLine] angle_deg={bl.angle_deg}")
        self.assertAlmostEqual(bl.angle_deg, 0.0, places=4)

    def test_004_angle_vertical(self):
        """Angolo 90° per BL verticale."""
        entity = _FakeEntity((0, 0), (0, 100))
        bl = bending_line_from_entity(entity)
        print(f"[BendingLine] angle_deg={bl.angle_deg}")
        self.assertAlmostEqual(bl.angle_deg, 90.0, places=4)

    def test_005_angle_45(self):
        """Angolo 45° per BL diagonale."""
        entity = _FakeEntity((0, 0), (100, 100))
        bl = bending_line_from_entity(entity)
        print(f"[BendingLine] angle_deg={bl.angle_deg}")
        self.assertAlmostEqual(bl.angle_deg, 45.0, places=4)

    def test_006_layer_preserved(self):
        """Layer originale preservato."""
        entity = _FakeEntity((0, 0), (100, 0), layer="PIEGA")
        bl = bending_line_from_entity(entity)
        print(f"[BendingLine] layer={bl.layer}")
        self.assertEqual(bl.layer, "PIEGA")

    def test_007_part_label_default(self):
        """part_label default è stringa vuota."""
        entity = _FakeEntity((0, 0), (100, 0))
        bl = bending_line_from_entity(entity)
        self.assertEqual(bl.part_label, "")

    def test_008_part_label_custom(self):
        """part_label custom passato correttamente."""
        entity = _FakeEntity((0, 0), (100, 0))
        bl = bending_line_from_entity(entity, part_label="pezzo_1")
        print(f"[BendingLine] part_label={bl.part_label}")
        self.assertEqual(bl.part_label, "pezzo_1")

    def test_009_geometry_is_linestring(self):
        """geometry è un LineString shapely."""
        entity = _FakeEntity((0, 0), (100, 0))
        bl = bending_line_from_entity(entity)
        self.assertIsInstance(bl.geometry, LineString)

    def test_010_angle_direction_invariant(self):
        """Angolo invariante per direzione opposta (% 180)."""
        e1 = _FakeEntity((0, 0), (100, 0))
        e2 = _FakeEntity((100, 0), (0, 0))
        bl1 = bending_line_from_entity(e1)
        bl2 = bending_line_from_entity(e2)
        print(f"[BendingLine] angle forward={bl1.angle_deg} reverse={bl2.angle_deg}")
        self.assertAlmostEqual(bl1.angle_deg, bl2.angle_deg, places=4)


# ---------------------------------------------------------------------------
# Test BendingLine.trim()
# ---------------------------------------------------------------------------

class TestBendingLineTrim(unittest.TestCase):

    def _make_bl(self, length=100.0):
        """BL orizzontale da 0 a length."""
        entity = _FakeEntity((0, 0), (length, 0))
        return bending_line_from_entity(entity)

    def test_001_trim_returns_two_segments(self):
        """trim(25) su BL da 100mm → 2 segmenti."""
        bl = self._make_bl(100)
        segs = bl.trim(25)
        print(f"\n[trim] n_segments={len(segs)}")
        self.assertEqual(len(segs), 2)

    def test_002_trim_start_length(self):
        """Primo segmento lungo esattamente margin."""
        bl = self._make_bl(100)
        segs = bl.trim(25)
        print(f"[trim] start_seg length={segs[0].length:.4f}")
        self.assertAlmostEqual(segs[0].length, 25.0, places=4)

    def test_003_trim_end_length(self):
        """Secondo segmento lungo esattamente margin."""
        bl = self._make_bl(100)
        segs = bl.trim(25)
        print(f"[trim] end_seg length={segs[1].length:.4f}")
        self.assertAlmostEqual(segs[1].length, 25.0, places=4)

    def test_004_trim_start_coords(self):
        """Primo segmento parte dall'origine della BL."""
        bl = self._make_bl(100)
        segs = bl.trim(25)
        start_x = list(segs[0].coords)[0][0]
        print(f"[trim] start_x={start_x}")
        self.assertAlmostEqual(start_x, 0.0, places=4)

    def test_005_trim_end_coords(self):
        """Secondo segmento arriva alla fine della BL."""
        bl = self._make_bl(100)
        segs = bl.trim(25)
        end_x = list(segs[1].coords)[-1][0]
        print(f"[trim] end_x={end_x}")
        self.assertAlmostEqual(end_x, 100.0, places=4)

    def test_006_trim_margin_too_large_returns_whole(self):
        """margin >= length/2 → restituisce geometria intera (1 segmento)."""
        bl = self._make_bl(100)
        segs = bl.trim(50)
        print(f"[trim] margin=50 on 100mm → n_segments={len(segs)}")
        self.assertEqual(len(segs), 1)
        self.assertAlmostEqual(segs[0].length, 100.0, places=4)

    def test_007_trim_margin_exactly_half(self):
        """margin == length/2 esatto → restituisce geometria intera."""
        bl = self._make_bl(100)
        segs = bl.trim(50)
        self.assertEqual(len(segs), 1)

    def test_008_trim_invalid_margin_raises(self):
        """margin <= 0 → ValueError."""
        bl = self._make_bl(100)
        with self.assertRaises(ValueError):
            bl.trim(0)
        with self.assertRaises(ValueError):
            bl.trim(-5)

    def test_009_trim_gap_between_segments(self):
        """C'è un gap tra i due segmenti (il centro è stato rimosso)."""
        bl = self._make_bl(100)
        segs = bl.trim(25)
        # Fine del primo segmento
        end_first  = list(segs[0].coords)[-1][0]
        # Inizio del secondo segmento
        start_last = list(segs[1].coords)[0][0]
        gap = start_last - end_first
        print(f"[trim] gap={gap:.4f}mm")
        self.assertGreater(gap, 0)
        self.assertAlmostEqual(gap, 50.0, places=4)

    def test_010_trim_asymmetric_margin(self):
        """trim con margin piccolo (10mm) su BL da 100mm."""
        bl = self._make_bl(100)
        segs = bl.trim(10)
        print(f"[trim] margin=10 → seg0={segs[0].length:.1f} seg1={segs[1].length:.1f}")
        self.assertAlmostEqual(segs[0].length, 10.0, places=4)
        self.assertAlmostEqual(segs[1].length, 10.0, places=4)


# ---------------------------------------------------------------------------
# Test BendingLine.to_dict()
# ---------------------------------------------------------------------------

class TestBendingLineToDict(unittest.TestCase):

    def test_001_to_dict_keys(self):
        """to_dict ha tutte le chiavi attese."""
        entity = _FakeEntity((0, 0), (100, 0))
        bl = bending_line_from_entity(entity, part_label="p1")
        d = bl.to_dict()
        print(f"\n[to_dict] keys={list(d.keys())}")
        for key in ["start", "end", "length", "angle_deg", "layer", "part_label"]:
            self.assertIn(key, d)

    def test_002_to_dict_values(self):
        """to_dict valori corretti per BL orizzontale da 100mm."""
        entity = _FakeEntity((0, 0), (100, 0))
        bl = bending_line_from_entity(entity, part_label="p1")
        d = bl.to_dict()
        print(f"[to_dict] {d}")
        self.assertAlmostEqual(d["length"], 100.0, places=2)
        self.assertAlmostEqual(d["angle_deg"], 0.0, places=2)
        self.assertEqual(d["part_label"], "p1")

    def test_003_to_dict_start_end_are_tuples(self):
        """start e end sono tuple (x, y)."""
        entity = _FakeEntity((5, 10), (105, 10))
        bl = bending_line_from_entity(entity)
        d = bl.to_dict()
        print(f"[to_dict] start={d['start']} end={d['end']}")
        self.assertEqual(len(d["start"]), 2)
        self.assertEqual(len(d["end"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)