"""
test_geometry_loader.py
------------------------
Test unitari per adapters/geometry/loader.py (forge.load_geometry).

Verifica il contratto: dict puri Python → ForgeDocument → heal_and_detect() →
to_dxf(), esattamente come load_dxf, ma senza file sorgente. Copre i due casi
d'uso reali: un rettangolo con foro (polyline + circle) e un settore anulare
tipo sviluppo di cono (arc + line, con conversione gradi→radianti).
"""

import math
import unittest

import ezdxf

import forge
from forge.adapters.geometry.loader import GeometryAdapter, load_geometry
from forge.model.role import ContourRole


class TestGeometryAdapter(unittest.TestCase):

    def test_line_edge_roundtrips_coordinates(self):
        edge = GeometryAdapter([], tolerance=0.05)._line_edge(
            {"start": (0, 0), "end": (10, 0), "role": "outer"}, ContourRole.OUTER
        )
        self.assertEqual(edge.start, (0.0, 0.0))
        self.assertEqual(edge.end, (10.0, 0.0))
        self.assertEqual(edge.role, ContourRole.OUTER)

    def test_arc_angles_are_degrees_not_radians(self):
        edge = GeometryAdapter([], tolerance=0.05)._arc_edge(
            {"center": (0, 0), "radius": 10, "start_angle": 0, "end_angle": 90},
            ContourRole.OUTER,
        )
        # end point a 90 gradi da un cerchio di raggio 10 -> (0, 10)
        self.assertAlmostEqual(edge.end[0], 0.0, places=3)
        self.assertAlmostEqual(edge.end[1], 10.0, places=3)

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            GeometryAdapter([{"type": "hexagon"}]).to_edges()


class TestLoadGeometryRectangleWithHole(unittest.TestCase):
    """Rettangolo (polyline chiusa) con un foro circolare — caso semplice."""

    def setUp(self):
        self.doc = load_geometry([
            {
                "type": "polyline",
                "points": [(0, 0), (100, 0), (100, 50), (0, 50)],
                "closed": True,
                "role": "outer",
            },
            {"type": "circle", "center": (20, 25), "radius": 5, "role": "hole"},
        ])

    def test_returns_forge_document(self):
        self.assertIsInstance(self.doc, forge.ForgeDocument)
        self.assertTrue(self.doc.edges)

    def test_heal_and_detect_finds_one_part_with_one_hole(self):
        result = forge.heal_and_detect(self.doc, label="rect_test")
        self.assertTrue(result.is_valid, result.errors)
        self.assertEqual(result.part_count, 1)
        part = result.parts[0]
        self.assertAlmostEqual(part.outer.area, 100 * 50, delta=1e-6)
        self.assertEqual(len(part.holes), 1)

    def test_to_dxf_writes_a_valid_document(self):
        result = forge.heal_and_detect(self.doc, label="rect_test")
        doc_out = forge.to_dxf(result)
        self.assertGreater(len(doc_out.modelspace()), 0)


class TestLoadGeometryConeSector(unittest.TestCase):
    """Settore anulare (2 arc + 2 line) — stessa forma di uno sviluppo di cono."""

    def setUp(self):
        r_int, r_est = 10.0, 20.0
        a0, a1 = -45.0, 45.0

        def polar(r, deg):
            rad = math.radians(deg)
            return (r * math.cos(rad), r * math.sin(rad))

        p_int_1, p_est_1 = polar(r_int, a0), polar(r_est, a0)
        p_int_2, p_est_2 = polar(r_int, a1), polar(r_est, a1)

        self.expected_area = (a1 - a0) / 360.0 * math.pi * (r_est**2 - r_int**2)

        self.doc = load_geometry([
            {"type": "arc", "center": (0, 0), "radius": r_est,
             "start_angle": a0, "end_angle": a1, "ccw": True, "role": "outer"},
            {"type": "line", "start": p_est_2, "end": p_int_2, "role": "outer"},
            {"type": "arc", "center": (0, 0), "radius": r_int,
             "start_angle": a1, "end_angle": a0, "ccw": False, "role": "outer"},
            {"type": "line", "start": p_int_1, "end": p_est_1, "role": "outer"},
        ])

    def test_forms_a_single_closed_part_with_correct_area(self):
        result = forge.heal_and_detect(self.doc, label="cono_sector_test")
        self.assertTrue(result.is_valid, result.errors)
        self.assertEqual(result.part_count, 1)
        self.assertAlmostEqual(
            result.parts[0].outer.area, self.expected_area, delta=self.expected_area * 0.01
        )

    def test_to_dxf_keeps_arcs_native_not_discretized(self):
        result = forge.heal_and_detect(self.doc, label="cono_sector_test")
        doc_out = forge.to_dxf(result)
        msp = doc_out.modelspace()
        # write_segments emette LWPOLYLINE con bulge per un contorno misto
        # linea/arco (rappresentazione esatta, non una discretizzazione) —
        # verifichiamo solo che il giro d'uscita non esploda e produca
        # geometria, la fedeltà del bulge è già coperta altrove.
        polylines = list(msp.query("LWPOLYLINE"))
        self.assertEqual(len(polylines), 1)
        self.assertTrue(any(abs(b) > 1e-9 for _, _, _, _, b in polylines[0].get_points()))


if __name__ == "__main__":
    unittest.main()
