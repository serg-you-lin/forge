
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

from forge.model import (
    ForgeContour,
    ForgeCluster,
    ForgeResult,
    Edge,
)
from forge.model import DetectedFeatures

from forge.model.role import ContourRole
from forge.core.primitives.segments import LineSeg

# ---------------------------------------------------------------------------
# Fake entity minimale — isola i test da ezdxf
# ---------------------------------------------------------------------------

class _Void:
    """Un elemento dell'overlay che un consumatore dichiara vuoto del pezzo (D90)."""
    is_void = True
    role = "my_void"

    def __init__(self, polygon):
        self.polygon = polygon


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
        contour = ForgeContour(polygon=poly, role="outer")
        print(f"\n[ForgeContour] area={contour.area}")
        self.assertEqual(contour.area, 100.0)

    def test_002_bbox(self):
        """Bbox calcolato correttamente."""
        poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
        contour = ForgeContour(polygon=poly, role="outer")
        print(f"[ForgeContour] bbox={contour.bbox}")
        self.assertEqual(contour.bbox, (0, 0, 10, 10))

    def test_003_role_unknown_preserved(self):
        """role UNKNOWN è un valore valido e viene preservato."""
        poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
        contour = ForgeContour(role=ContourRole.UNKNOWN, polygon=poly)
        self.assertEqual(contour.role, ContourRole.UNKNOWN)

    def test_004_role_inner(self):
        """role inner assegnato correttamente."""
        poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
        contour = ForgeContour(polygon=poly, role="inner")
        self.assertEqual(contour.role, "inner")

    def test_005_role_preserved(self):
        """Role preservato correttamente."""
        poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
        contour = ForgeContour(polygon=poly, role="outer")
        self.assertEqual(contour.role, "outer")


# ---------------------------------------------------------------------------
# Test Edge
# ---------------------------------------------------------------------------

class TestEdge(unittest.TestCase):
    """
    Dopo il refactoring Edge è dati puri: role + start/end + segment
    (primitiva nativa) + style. Nessun source_ref, layer o geometry.
    """

    def _seg(self, start=(0.0, 0.0), end=(100.0, 0.0)):
        return LineSeg(start=start, end=end)

    def test_001_construction(self):
        """Edge costruito correttamente con campi minimi."""
        seg = self._seg()
        edge = Edge(
            role=ContourRole.OUTER,
            start=(0.0, 0.0),
            end=(100.0, 0.0),
            segment=seg,
        )
        print(f"\n[Edge] start={edge.start} end={edge.end} role={edge.role}")
        self.assertEqual(edge.start, (0.0, 0.0))
        self.assertEqual(edge.end, (100.0, 0.0))
        self.assertEqual(edge.role, ContourRole.OUTER)

    def test_002_segment_reference_preserved(self):
        """La primitiva geometrica passata non viene sostituita."""
        seg = self._seg()
        edge = Edge(role=ContourRole.UNKNOWN, start=(0, 0), end=(1, 1), segment=seg)
        self.assertIs(edge.segment, seg)

    def test_005_role_preserved(self):
        """role cached sull'Edge — assegnato dall'adapter, mai dal layer DXF."""
        edge = Edge(role="bending", start=(0, 0), end=(1, 0),
                    segment=self._seg((0, 0), (1, 0)))
        self.assertEqual(edge.role, "bending")

    def test_006_start_end_are_tuples(self):
        """start e end sono tuple (x, y)."""
        edge = Edge(role=ContourRole.UNKNOWN, start=(5.0, 10.0), end=(15.0, 20.0),
                    segment=self._seg((5.0, 10.0), (15.0, 20.0)))
        self.assertEqual(len(edge.start), 2)
        self.assertEqual(len(edge.end), 2)


# ---------------------------------------------------------------------------
# Test ForgeCluster
# ---------------------------------------------------------------------------

class TestForgeCluster(unittest.TestCase):

    def _make_outer(self, coords=None):
        if coords is None:
            coords = [(0,0), (100,0), (100,100), (0,100)]
        return ForgeContour(role=ContourRole.OUTER, polygon=Polygon(coords))

    def test_001_no_holes_area(self):
        """Area corretta senza fori."""
        cluster = ForgeCluster(outer=self._make_outer(), label="test")
        print(f"\n[ForgeCluster] area={cluster.area}, holes={len(cluster.features('holes'))}")
        self.assertEqual(cluster.area, 10000.0)

    def test_002_no_holes_count(self):
        """Lista fori vuota di default."""
        cluster = ForgeCluster(outer=self._make_outer(), label="test")
        self.assertEqual(len(cluster.features("holes")), 0)

    def test_003_with_hole_net_area(self):
        """Area netta = outer - un vuoto dell'overlay (is_void, D90)."""
        import math
        outer = self._make_outer()
        hole_poly = Point((50, 50)).buffer(5.0, resolution=64)
        cluster = ForgeCluster(outer=outer, detected=DetectedFeatures())
        cluster.detected.attach("holes", [_Void(polygon=hole_poly)])
        expected = 10000.0 - math.pi * 25.0
        print(f"\n[ForgeCluster with hole] area={cluster.area:.4f} expected≈{expected:.4f}")
        self.assertAlmostEqual(cluster.area, expected, delta=0.01)

    def test_004_polygon_with_holes(self):
        """polygon_with_holes restituisce Polygon Shapely con foro."""
        outer = self._make_outer()
        hole_poly = Point((50, 50)).buffer(5.0, resolution=64)
        cluster = ForgeCluster(outer=outer, detected=DetectedFeatures())
        cluster.detected.attach("holes", [_Void(polygon=hole_poly)])
        result_poly = cluster.polygon_with_holes
        print(f"[ForgeCluster] interiors={len(list(result_poly.interiors))}")
        self.assertEqual(len(list(result_poly.interiors)), 1)

    def test_005_bbox(self):
        """Bbox corrisponde all'outer."""
        cluster = ForgeCluster(outer=self._make_outer())
        print(f"[ForgeCluster] bbox={cluster.bbox}")
        self.assertEqual(cluster.bbox, (0, 0, 100, 100))

    def test_006_bending_lines_default_empty(self):
        """bending_lines è lista vuota di default."""
        cluster = ForgeCluster(outer=self._make_outer())
        self.assertIsInstance(cluster.features("bending_lines"), list)
        self.assertEqual(len(cluster.features("bending_lines")), 0)

    def test_007_engrave_lines_default_empty(self):
        """engrave_lines è lista vuota di default."""
        cluster = ForgeCluster(outer=self._make_outer())
        self.assertIsInstance(cluster.features("engrave_lines"), list)
        self.assertEqual(len(cluster.features("engrave_lines")), 0)

    def test_008_custom_default_empty(self):
        """custom è dict vuoto di default."""
        cluster = ForgeCluster(outer=self._make_outer())
        self.assertIsInstance(cluster.custom, dict)
        self.assertEqual(len(cluster.custom), 0)

    def test_009_inners_independent(self):
        """Due ForgeCluster non condividono la stessa lista inners."""
        p1 = ForgeCluster(outer=self._make_outer())
        p2 = ForgeCluster(outer=self._make_outer())
        inner_poly = Polygon([(10,10), (20,10), (20,20), (10,20)])
        p1.inners.append(ForgeContour(role=ContourRole.INNER, polygon=inner_poly))
        print(f"[ForgeCluster] p1.inners={len(p1.inners)} p2.inners={len(p2.inners)}")
        self.assertEqual(len(p2.inners), 0)


# ---------------------------------------------------------------------------
# Test ForgeResult
# ---------------------------------------------------------------------------

class TestForgeResult(unittest.TestCase):

    def _make_result(self):
        outer_poly = Polygon([(0,0), (50,0), (50,50), (0,50)])
        outer = ForgeContour(role=ContourRole.OUTER, polygon=outer_poly)
        cluster  = ForgeCluster(outer=outer, label="pezzo_1", source_file="test.dxf")
        return ForgeResult(clusters=[cluster], source_file="test.dxf")

    def test_001_part_count(self):
        """cluster_count corretto."""
        result = self._make_result()
        print(f"\n[ForgeResult] cluster_count={result.cluster_count}")
        self.assertEqual(result.cluster_count, 1)

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
        self.assertIn("cluster_count", d)
        self.assertIn("clusters", d)
        self.assertIn("is_valid", d)
        self.assertIn("source_file", d)

    def test_006_to_dict_values(self):
        """to_dict ha i valori corretti."""
        result = self._make_result()
        d = result.to_dict()
        print(f"[ForgeResult] cluster label={d['clusters'][0]['label']}")
        self.assertEqual(d["cluster_count"], 1)
        self.assertEqual(d["clusters"][0]["label"], "pezzo_1")
        self.assertTrue(d["is_valid"])


if __name__ == "__main__":
    unittest.main(verbosity=2)