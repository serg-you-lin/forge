# tests/unit/core/test_lines.py
"""`splits_polygon`, `bridged_runs`, `point_line_distance`: fatti fra rette e poligoni (D93)."""

import unittest

from shapely.geometry import Polygon, box

import forge
from forge.core.geometry.lines import CollinearRun, are_collinear, bridged_runs, point_line_distance, splits_polygon

PART = box(0, 0, 100, 50)


class TestSplitsPolygon(unittest.TestCase):

    def test_corda_da_bordo_a_bordo(self):
        self.assertTrue(splits_polygon(PART, (40, 0), (40, 50)))

    def test_corda_che_non_arriva_al_bordo_lo_divide_col_prolungamento(self):
        self.assertFalse(splits_polygon(PART, (40, 0.5), (40, 49.5)))
        self.assertTrue(splits_polygon(PART, (40, 0.5), (40, 49.5), reach=1.0))

    def test_tratto_interno_non_divide(self):
        self.assertFalse(splits_polygon(PART, (40, 10), (40, 20), reach=1.0))

    def test_tratto_degenere(self):
        self.assertFalse(splits_polygon(PART, (40, 10), (40, 10), reach=1.0))


class TestBridgedRuns(unittest.TestCase):

    HOLE = box(38, 20, 42, 30)

    def test_due_tratti_uniti_attraverso_un_foro(self):
        segments = [((40, 30), (40, 50)), ((40, 0), (40, 20))]
        (run,) = bridged_runs(segments, [self.HOLE])
        self.assertEqual(run, CollinearRun((40, 0), (40, 50), (1, 0)))

    def test_spazio_fuori_dal_foro_non_unisce(self):
        segments = [((40, 0), (40, 15)), ((40, 30), (40, 50))]
        self.assertEqual(bridged_runs(segments, [self.HOLE]), [])

    def test_tratti_su_rette_diverse(self):
        segments = [((40, 0), (40, 20)), ((41, 30), (41, 50))]
        self.assertEqual(bridged_runs(segments, [self.HOLE]), [])

    def test_lineastring_come_tratto(self):
        from shapely.geometry import LineString
        segments = [LineString([(40, 0), (40, 20)]), LineString([(40, 30), (40, 50)])]
        self.assertEqual(len(bridged_runs(segments, [self.HOLE])), 1)

    def test_api_pubblica(self):
        self.assertIs(forge.geometry.bridged_runs, bridged_runs)
        self.assertIs(forge.geometry.splits_polygon, splits_polygon)


class TestLineFacts(unittest.TestCase):

    def test_distanza_dalla_retta(self):
        self.assertAlmostEqual(point_line_distance((0, 3), (-5, 0), (5, 0)), 3)
        self.assertAlmostEqual(point_line_distance((3, 4), (0, 0), (0, 0)), 5)

    def test_collineari_con_tolleranza_angolare(self):
        a, b = ((0, 0), (100, 0)), ((0, 0.01), (100, 0.06))
        self.assertFalse(are_collinear(a, b))
        self.assertTrue(are_collinear(a, b, angle_tolerance=1e-3))


if __name__ == "__main__":
    unittest.main()
