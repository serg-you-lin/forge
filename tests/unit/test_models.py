# """
# Test Suite per dxf_forge.models

# Test puri sui modelli dati — non richiedono file DXF.

# Lancia:
#     python -m unittest tests/test_models.py -v
# """

# import unittest
# from pathlib import Path
# import sys

# project_root = Path(__file__).resolve().parent.parent
# sys.path.insert(0, str(project_root))

# from shapely.geometry import Polygon
# from dxf_forge.core.models import ForgeContour, ForgePart, ForgeResult


# class TestForgeContour(unittest.TestCase):
#     """Test su ForgeContour."""

#     def test_001_area(self):
#         """Area calcolata correttamente."""
#         poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
#         contour = ForgeContour(polygon=poly, is_inner=False, layer="OuterContour")
#         print(f"\n[ForgeContour] area={contour.area}")
#         self.assertEqual(contour.area, 100.0)

#     def test_002_bbox(self):
#         """Bbox calcolato correttamente."""
#         poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
#         contour = ForgeContour(polygon=poly, is_inner=False, layer="OuterContour")
#         print(f"[ForgeContour] bbox={contour.bbox}")
#         self.assertEqual(contour.bbox, (0, 0, 10, 10))

#     def test_003_is_hole_default(self):
#         """is_hole default è False."""
#         poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
#         contour = ForgeContour(polygon=poly)
#         self.assertFalse(contour.is_inner)


# class TestForgePart(unittest.TestCase):
#     """Test su ForgePart."""

#     def test_001_no_holes_area(self):
#         """Area corretta senza fori."""
#         outer_poly = Polygon([(0,0), (100,0), (100,100), (0,100)])
#         outer = ForgeContour(polygon=outer_poly)
#         part = ForgePart(outer=outer, label="test")
#         print(f"\n[ForgePart] area={part.area}, holes={len(part.inners)}")
#         self.assertEqual(part.area, 10000.0)

#     def test_002_no_holes_count(self):
#         """Lista fori vuota di default."""
#         outer_poly = Polygon([(0,0), (100,0), (100,100), (0,100)])
#         outer = ForgeContour(polygon=outer_poly)
#         part = ForgePart(outer=outer, label="test")
#         self.assertEqual(len(part.inners), 0)

#     def test_003_with_hole_net_area(self):
#         """Area netta = outer - foro."""
#         outer_poly = Polygon([(0,0), (100,0), (100,100), (0,100)])
#         hole_poly  = Polygon([(10,10), (20,10), (20,20), (10,20)])
#         outer = ForgeContour(polygon=outer_poly)
#         hole  = ForgeContour(polygon=hole_poly, is_inner=True)
#         part  = ForgePart(outer=outer, inners=[hole])
#         print(f"\n[ForgePart with hole] area={part.area}")
#         self.assertEqual(part.area, 10000.0 - 100.0)

#     def test_004_polygon_with_holes(self):
#         """polygon_with_holes restituisce Polygon Shapely con foro."""
#         outer_poly = Polygon([(0,0), (100,0), (100,100), (0,100)])
#         hole_poly  = Polygon([(10,10), (20,10), (20,20), (10,20)])
#         outer = ForgeContour(polygon=outer_poly)
#         hole  = ForgeContour(polygon=hole_poly, is_inner=True)
#         part  = ForgePart(outer=outer, inners=[hole])
#         result_poly = part.polygon_with_holes
#         print(f"[ForgePart] interiors={len(list(result_poly.interiors))}")
#         self.assertEqual(len(list(result_poly.interiors)), 1)

#     def test_005_bbox(self):
#         """Bbox corrisponde all'outer."""
#         outer_poly = Polygon([(0,0), (100,0), (100,100), (0,100)])
#         outer = ForgeContour(polygon=outer_poly)
#         part  = ForgePart(outer=outer)
#         print(f"[ForgePart] bbox={part.bbox}")
#         self.assertEqual(part.bbox, (0, 0, 100, 100))


# class TestForgeResult(unittest.TestCase):
#     """Test su ForgeResult."""

#     def _make_result(self):
#         outer_poly = Polygon([(0,0), (50,0), (50,50), (0,50)])
#         outer = ForgeContour(polygon=outer_poly)
#         part  = ForgePart(outer=outer, label="pezzo_1", source_file="test.dxf")
#         return ForgeResult(parts=[part], source_file="test.dxf")

#     def test_001_part_count(self):
#         """part_count corretto."""
#         result = self._make_result()
#         print(f"\n[ForgeResult] part_count={result.part_count}")
#         self.assertEqual(result.part_count, 1)

#     def test_002_is_valid_default(self):
#         """is_valid è True di default."""
#         result = self._make_result()
#         self.assertTrue(result.is_valid)

#     def test_003_has_issues_false(self):
#         """has_issues è False senza warning né errori."""
#         result = self._make_result()
#         self.assertFalse(result.has_issues)

#     def test_004_has_issues_true(self):
#         """has_issues è True se ci sono warning."""
#         result = self._make_result()
#         result.warnings.append("qualcosa non va")
#         print(f"[ForgeResult] has_issues={result.has_issues}")
#         self.assertTrue(result.has_issues)

#     def test_005_to_dict_keys(self):
#         """to_dict ha le chiavi giuste."""
#         result = self._make_result()
#         d = result.to_dict()
#         print(f"[ForgeResult] keys={list(d.keys())}")
#         self.assertIn("part_count", d)
#         self.assertIn("parts", d)
#         self.assertIn("is_valid", d)
#         self.assertIn("source_file", d)

#     def test_006_to_dict_values(self):
#         """to_dict ha i valori corretti."""
#         result = self._make_result()
#         d = result.to_dict()
#         print(f"[ForgeResult] part label={d['parts'][0]['label']}")
#         self.assertEqual(d["part_count"], 1)
#         self.assertEqual(d["parts"][0]["label"], "pezzo_1")
#         self.assertTrue(d["is_valid"])


# if __name__ == "__main__":
#     unittest.main(verbosity=2)


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

from shapely.geometry import Polygon, LineString, Point
from dxf_forge.core.models import (
    ForgeContour,
    ForgePart,
    ForgeResult,
    Hole,
    Edge,
    BendingLine,
    ClassifiedEntity,
    GeometryHints,
    HOLE_TYPE_UNKNOWN,
    HOLE_TYPE_PLAIN,
    HOLE_TYPE_COUNTERSINK,
    HOLE_TYPE_THREADED,
)


# ---------------------------------------------------------------------------
# Fake entity minimale — isola i test da ezdxf
# ---------------------------------------------------------------------------

class _FakeEntity:
    """Entità ezdxf minimale per test che richiedono un riferimento entity."""
    pass


# ---------------------------------------------------------------------------
# Test ForgeContour
# ---------------------------------------------------------------------------

class TestForgeContour(unittest.TestCase):

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

    def test_004_is_hole_always_false(self):
        """is_hole è sempre False su ForgeContour — i fori usano Hole."""
        poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
        contour = ForgeContour(polygon=poly)
        self.assertFalse(contour.is_hole)

    def test_005_layer_preserved(self):
        """Layer preservato correttamente."""
        poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
        contour = ForgeContour(polygon=poly, layer="TAGLIO")
        self.assertEqual(contour.layer, "TAGLIO")


# ---------------------------------------------------------------------------
# Test Hole
# ---------------------------------------------------------------------------

class TestHole(unittest.TestCase):

    def _make_hole(self, diameter=10.0, center=(50.0, 50.0), hole_type=HOLE_TYPE_PLAIN):
        r = diameter / 2
        poly = Point(center).buffer(r, resolution=64)
        return Hole(
            polygon=poly,
            diameter=diameter,
            center=center,
            hole_type=hole_type,
            confidence=1.0,
            source="geometric",
            layer="0",
        )

    def test_001_area(self):
        """Area approssima π*r²."""
        import math
        hole = self._make_hole(diameter=10.0)
        expected = math.pi * 5.0 ** 2
        print(f"\n[Hole] area={hole.area:.4f} expected≈{expected:.4f}")
        self.assertAlmostEqual(hole.area, expected, delta=0.01)

    def test_002_bbox(self):
        """Bbox centrato sul centro del foro."""
        hole = self._make_hole(diameter=10.0, center=(50.0, 50.0))
        minx, miny, maxx, maxy = hole.bbox
        print(f"[Hole] bbox={hole.bbox}")
        self.assertAlmostEqual(minx, 45.0, delta=0.01)
        self.assertAlmostEqual(miny, 45.0, delta=0.01)
        self.assertAlmostEqual(maxx, 55.0, delta=0.01)
        self.assertAlmostEqual(maxy, 55.0, delta=0.01)

    def test_003_is_hole_always_true(self):
        """is_hole è sempre True su Hole."""
        hole = self._make_hole()
        self.assertTrue(hole.is_hole)

    def test_004_hole_type_default(self):
        """hole_type default è UNKNOWN."""
        r = 5.0
        poly = Point((0, 0)).buffer(r, resolution=64)
        hole = Hole(polygon=poly, diameter=10.0, center=(0, 0))
        self.assertEqual(hole.hole_type, HOLE_TYPE_UNKNOWN)

    def test_005_to_dict_keys(self):
        """to_dict ha tutte le chiavi attese."""
        hole = self._make_hole()
        d = hole.to_dict()
        print(f"\n[Hole.to_dict] keys={list(d.keys())}")
        for key in ["hole_type", "diameter", "center", "layer", "confidence", "source"]:
            self.assertIn(key, d)

    def test_006_to_dict_values(self):
        """to_dict valori corretti."""
        hole = self._make_hole(diameter=8.0, center=(10.0, 20.0))
        d = hole.to_dict()
        print(f"[Hole.to_dict] {d}")
        self.assertAlmostEqual(d["diameter"], 8.0, places=4)
        self.assertEqual(d["center"], (10.0, 20.0))
        self.assertEqual(d["hole_type"], HOLE_TYPE_PLAIN)

    def test_007_to_dict_countersink_has_outer_diameter(self):
        """to_dict include outer_diameter se presente."""
        hole = self._make_hole(hole_type=HOLE_TYPE_COUNTERSINK)
        hole.outer_diameter = 14.0
        d = hole.to_dict()
        print(f"[Hole.to_dict] outer_diameter={d.get('outer_diameter')}")
        self.assertIn("outer_diameter", d)
        self.assertAlmostEqual(d["outer_diameter"], 14.0, places=4)

    def test_008_to_dict_plain_no_outer_diameter(self):
        """to_dict NON include outer_diameter per foro plain."""
        hole = self._make_hole(hole_type=HOLE_TYPE_PLAIN)
        d = hole.to_dict()
        self.assertNotIn("outer_diameter", d)

    def test_009_confidence_default(self):
        """confidence default è 0.0."""
        r = 5.0
        poly = Point((0, 0)).buffer(r, resolution=64)
        hole = Hole(polygon=poly, diameter=10.0, center=(0, 0))
        self.assertEqual(hole.confidence, 0.0)

    def test_010_source_default(self):
        """source default è stringa vuota."""
        r = 5.0
        poly = Point((0, 0)).buffer(r, resolution=64)
        hole = Hole(polygon=poly, diameter=10.0, center=(0, 0))
        self.assertEqual(hole.source, "")


# ---------------------------------------------------------------------------
# Test Edge
# ---------------------------------------------------------------------------

class TestEdge(unittest.TestCase):

    def test_001_construction(self):
        """Edge costruito correttamente con campi minimi."""
        entity = _FakeEntity()
        edge = Edge(
            entity=entity,
            layer="TAGLIO",
            start=(0.0, 0.0),
            end=(100.0, 0.0),
        )
        print(f"\n[Edge] start={edge.start} end={edge.end} layer={edge.layer}")
        self.assertEqual(edge.start, (0.0, 0.0))
        self.assertEqual(edge.end, (100.0, 0.0))
        self.assertEqual(edge.layer, "TAGLIO")

    def test_002_entity_reference_preserved(self):
        """Riferimento all'entità originale non viene perso."""
        entity = _FakeEntity()
        edge = Edge(entity=entity, layer="0", start=(0, 0), end=(1, 1))
        self.assertIs(edge.entity, entity)

    def test_003_geometry_optional(self):
        """geometry è None di default."""
        edge = Edge(entity=_FakeEntity(), layer="0", start=(0, 0), end=(1, 1))
        self.assertIsNone(edge.geometry)

    def test_004_geometry_linestring(self):
        """geometry può essere un LineString shapely."""
        geom = LineString([(0, 0), (100, 0)])
        edge = Edge(
            entity=_FakeEntity(),
            layer="0",
            start=(0.0, 0.0),
            end=(100.0, 0.0),
            geometry=geom,
        )
        print(f"[Edge] geometry length={edge.geometry.length}")
        self.assertIsInstance(edge.geometry, LineString)
        self.assertAlmostEqual(edge.geometry.length, 100.0, places=4)

    def test_005_layer_preserved(self):
        """Layer cached sull'Edge — non rileggere entity.dxf.layer."""
        edge = Edge(entity=_FakeEntity(), layer="PIEGA", start=(0, 0), end=(1, 0))
        self.assertEqual(edge.layer, "PIEGA")

    def test_006_start_end_are_tuples(self):
        """start e end sono tuple (x, y)."""
        edge = Edge(entity=_FakeEntity(), layer="0", start=(5.0, 10.0), end=(15.0, 20.0))
        self.assertEqual(len(edge.start), 2)
        self.assertEqual(len(edge.end), 2)


# ---------------------------------------------------------------------------
# Test BendingLine
# ---------------------------------------------------------------------------

class TestBendingLine(unittest.TestCase):

    def _make_bl(self, start=(0, 0), end=(100, 0), layer="PIEGA", part_label=""):
        geom = LineString([start, end])
        import math
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        angle = math.degrees(math.atan2(dy, dx)) % 180.0
        return BendingLine(
            entity=_FakeEntity(),
            geometry=geom,
            length=geom.length,
            layer=layer,
            angle_deg=angle,
            part_label=part_label,
        )

    def test_001_to_dict_keys(self):
        """to_dict ha tutte le chiavi attese."""
        bl = self._make_bl(part_label="p1")
        d = bl.to_dict()
        print(f"\n[BendingLine.to_dict] keys={list(d.keys())}")
        for key in ["start", "end", "length", "angle_deg", "layer", "part_label"]:
            self.assertIn(key, d)

    def test_002_to_dict_length(self):
        """to_dict length corretta per BL orizzontale da 100mm."""
        bl = self._make_bl()
        d = bl.to_dict()
        print(f"[BendingLine.to_dict] length={d['length']}")
        self.assertAlmostEqual(d["length"], 100.0, places=4)

    def test_003_to_dict_angle(self):
        """to_dict angle_deg corretto per BL orizzontale."""
        bl = self._make_bl()
        d = bl.to_dict()
        print(f"[BendingLine.to_dict] angle_deg={d['angle_deg']}")
        self.assertAlmostEqual(d["angle_deg"], 0.0, places=4)

    def test_004_to_dict_part_label(self):
        """to_dict part_label preservato."""
        bl = self._make_bl(part_label="pezzo_3")
        d = bl.to_dict()
        self.assertEqual(d["part_label"], "pezzo_3")

    def test_005_to_dict_start_end_are_tuples(self):
        """start e end in to_dict sono tuple (x, y)."""
        bl = self._make_bl(start=(5, 10), end=(105, 10))
        d = bl.to_dict()
        print(f"[BendingLine.to_dict] start={d['start']} end={d['end']}")
        self.assertEqual(len(d["start"]), 2)
        self.assertEqual(len(d["end"]), 2)

    def test_006_layer_preserved(self):
        """Layer originale preservato in to_dict."""
        bl = self._make_bl(layer="PIEGA")
        d = bl.to_dict()
        self.assertEqual(d["layer"], "PIEGA")


# ---------------------------------------------------------------------------
# Test GeometryHints
# ---------------------------------------------------------------------------

class TestGeometryHints(unittest.TestCase):

    def test_001_default_empty(self):
        """bend_line_ids è un set vuoto di default."""
        hints = GeometryHints()
        print(f"\n[GeometryHints] bend_line_ids={hints.bend_line_ids}")
        self.assertIsInstance(hints.bend_line_ids, set)
        self.assertEqual(len(hints.bend_line_ids), 0)

    def test_002_add_id(self):
        """Si può aggiungere un id al set."""
        hints = GeometryHints()
        hints.bend_line_ids.add(12345)
        self.assertIn(12345, hints.bend_line_ids)

    def test_003_instances_are_independent(self):
        """Due istanze non condividono lo stesso set (field factory)."""
        h1 = GeometryHints()
        h2 = GeometryHints()
        h1.bend_line_ids.add(999)
        print(f"[GeometryHints] h1={h1.bend_line_ids} h2={h2.bend_line_ids}")
        self.assertNotIn(999, h2.bend_line_ids)


# ---------------------------------------------------------------------------
# Test ForgePart
# ---------------------------------------------------------------------------

class TestForgePart(unittest.TestCase):

    def _make_outer(self, coords=None):
        if coords is None:
            coords = [(0,0), (100,0), (100,100), (0,100)]
        return ForgeContour(polygon=Polygon(coords))

    def test_001_no_holes_area(self):
        """Area corretta senza fori."""
        part = ForgePart(outer=self._make_outer(), label="test")
        print(f"\n[ForgePart] area={part.area}, holes={len(part.holes)}")
        self.assertEqual(part.area, 10000.0)

    def test_002_no_holes_count(self):
        """Lista fori vuota di default."""
        part = ForgePart(outer=self._make_outer(), label="test")
        self.assertEqual(len(part.holes), 0)

    def test_003_with_hole_net_area(self):
        """Area netta = outer - foro."""
        import math
        outer = self._make_outer()
        hole_poly = Point((50, 50)).buffer(5.0, resolution=64)
        hole = Hole(polygon=hole_poly, diameter=10.0, center=(50, 50))
        part = ForgePart(outer=outer, holes=[hole])
        expected = 10000.0 - math.pi * 25.0
        print(f"\n[ForgePart with hole] area={part.area:.4f} expected≈{expected:.4f}")
        self.assertAlmostEqual(part.area, expected, delta=0.01)

    def test_004_polygon_with_holes(self):
        """polygon_with_holes restituisce Polygon Shapely con foro."""
        outer = self._make_outer()
        hole_poly = Point((50, 50)).buffer(5.0, resolution=64)
        hole = Hole(polygon=hole_poly, diameter=10.0, center=(50, 50))
        part = ForgePart(outer=outer, holes=[hole])
        result_poly = part.polygon_with_holes
        print(f"[ForgePart] interiors={len(list(result_poly.interiors))}")
        self.assertEqual(len(list(result_poly.interiors)), 1)

    def test_005_bbox(self):
        """Bbox corrisponde all'outer."""
        part = ForgePart(outer=self._make_outer())
        print(f"[ForgePart] bbox={part.bbox}")
        self.assertEqual(part.bbox, (0, 0, 100, 100))

    def test_006_geometry_hints_default(self):
        """geometry_hints è GeometryHints vuoto di default."""
        part = ForgePart(outer=self._make_outer())
        self.assertIsInstance(part.geometry_hints, GeometryHints)
        self.assertEqual(len(part.geometry_hints.bend_line_ids), 0)

    def test_007_entity_ids_default_empty(self):
        """entity_ids è set vuoto di default."""
        part = ForgePart(outer=self._make_outer())
        self.assertIsInstance(part.entity_ids, set)
        self.assertEqual(len(part.entity_ids), 0)

    def test_008_custom_default_empty(self):
        """custom è dict vuoto di default."""
        part = ForgePart(outer=self._make_outer())
        self.assertIsInstance(part.custom, dict)
        self.assertEqual(len(part.custom), 0)

    def test_009_inners_independent(self):
        """Due ForgePart non condividono la stessa lista inners."""
        p1 = ForgePart(outer=self._make_outer())
        p2 = ForgePart(outer=self._make_outer())
        inner_poly = Polygon([(10,10), (20,10), (20,20), (10,20)])
        p1.inners.append(ForgeContour(polygon=inner_poly))
        print(f"[ForgePart] p1.inners={len(p1.inners)} p2.inners={len(p2.inners)}")
        self.assertEqual(len(p2.inners), 0)


# ---------------------------------------------------------------------------
# Test ForgeResult
# ---------------------------------------------------------------------------

class TestForgeResult(unittest.TestCase):

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