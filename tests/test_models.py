"""
Test Suite per dxf_forge.models

Test puri sui modelli dati — non richiedono file DXF.

Lancia:
    python -m unittest tests/test_models.py -v
"""

import unittest
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from shapely.geometry import Polygon
from dxf_forge.models import ForgeContour, ForgePart, ForgeResult


class TestForgeContour(unittest.TestCase):
    """Test su ForgeContour."""

    def test_001_area(self):
        """Area calcolata correttamente."""
        poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
        contour = ForgeContour(polygon=poly, is_inner=False, layer="OuterContour")
        print(f"\n[ForgeContour] area={contour.area}")
        self.assertEqual(contour.area, 100.0)

    def test_002_bbox(self):
        """Bbox calcolato correttamente."""
        poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
        contour = ForgeContour(polygon=poly, is_inner=False, layer="OuterContour")
        print(f"[ForgeContour] bbox={contour.bbox}")
        self.assertEqual(contour.bbox, (0, 0, 10, 10))

    def test_003_is_hole_default(self):
        """is_hole default è False."""
        poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
        contour = ForgeContour(polygon=poly)
        self.assertFalse(contour.is_inner)


class TestForgePart(unittest.TestCase):
    """Test su ForgePart."""

    def test_001_no_holes_area(self):
        """Area corretta senza fori."""
        outer_poly = Polygon([(0,0), (100,0), (100,100), (0,100)])
        outer = ForgeContour(polygon=outer_poly)
        part = ForgePart(outer=outer, label="test")
        print(f"\n[ForgePart] area={part.area}, holes={len(part.inners)}")
        self.assertEqual(part.area, 10000.0)

    def test_002_no_holes_count(self):
        """Lista fori vuota di default."""
        outer_poly = Polygon([(0,0), (100,0), (100,100), (0,100)])
        outer = ForgeContour(polygon=outer_poly)
        part = ForgePart(outer=outer, label="test")
        self.assertEqual(len(part.inners), 0)

    def test_003_with_hole_net_area(self):
        """Area netta = outer - foro."""
        outer_poly = Polygon([(0,0), (100,0), (100,100), (0,100)])
        hole_poly  = Polygon([(10,10), (20,10), (20,20), (10,20)])
        outer = ForgeContour(polygon=outer_poly)
        hole  = ForgeContour(polygon=hole_poly, is_inner=True)
        part  = ForgePart(outer=outer, inners=[hole])
        print(f"\n[ForgePart with hole] area={part.area}")
        self.assertEqual(part.area, 10000.0 - 100.0)

    def test_004_polygon_with_holes(self):
        """polygon_with_holes restituisce Polygon Shapely con foro."""
        outer_poly = Polygon([(0,0), (100,0), (100,100), (0,100)])
        hole_poly  = Polygon([(10,10), (20,10), (20,20), (10,20)])
        outer = ForgeContour(polygon=outer_poly)
        hole  = ForgeContour(polygon=hole_poly, is_inner=True)
        part  = ForgePart(outer=outer, inners=[hole])
        result_poly = part.polygon_with_holes
        print(f"[ForgePart] interiors={len(list(result_poly.interiors))}")
        self.assertEqual(len(list(result_poly.interiors)), 1)

    def test_005_bbox(self):
        """Bbox corrisponde all'outer."""
        outer_poly = Polygon([(0,0), (100,0), (100,100), (0,100)])
        outer = ForgeContour(polygon=outer_poly)
        part  = ForgePart(outer=outer)
        print(f"[ForgePart] bbox={part.bbox}")
        self.assertEqual(part.bbox, (0, 0, 100, 100))


class TestForgeResult(unittest.TestCase):
    """Test su ForgeResult."""

    def _make_result(self):
        outer_poly = Polygon([(0,0), (50,0), (50,50), (0,50)])
        outer = ForgeContour(polygon=outer_poly)
        part  = ForgePart(outer=outer, label="pezzo_1", source_file="test.dxf")
        return ForgeResult(parts=[part], source_file="test.dxf")

    def test_001_part_count(self):
        """part_count corretto."""
        result = self._make_result()
        print(f"\n[ForgeResult] part_count={result.part_count}")
        self.assertEqual(result.part_count, 1)

    def test_002_is_valid_default(self):
        """is_valid è True di default."""
        result = self._make_result()
        self.assertTrue(result.is_valid)

    def test_003_has_issues_false(self):
        """has_issues è False senza warning né errori."""
        result = self._make_result()
        self.assertFalse(result.has_issues)

    def test_004_has_issues_true(self):
        """has_issues è True se ci sono warning."""
        result = self._make_result()
        result.warnings.append("qualcosa non va")
        print(f"[ForgeResult] has_issues={result.has_issues}")
        self.assertTrue(result.has_issues)

    def test_005_to_dict_keys(self):
        """to_dict ha le chiavi giuste."""
        result = self._make_result()
        d = result.to_dict()
        print(f"[ForgeResult] keys={list(d.keys())}")
        self.assertIn("part_count", d)
        self.assertIn("parts", d)
        self.assertIn("is_valid", d)
        self.assertIn("source_file", d)

    def test_006_to_dict_values(self):
        """to_dict ha i valori corretti."""
        result = self._make_result()
        d = result.to_dict()
        print(f"[ForgeResult] part label={d['parts'][0]['label']}")
        self.assertEqual(d["part_count"], 1)
        self.assertEqual(d["parts"][0]["label"], "pezzo_1")
        self.assertTrue(d["is_valid"])


if __name__ == "__main__":
    unittest.main(verbosity=2)