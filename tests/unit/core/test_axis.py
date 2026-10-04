# tests/unit/core/test_axis.py
"""`forge.core.axis`: intervalli, rettangoli coperti, linee che attraversano un rettangolo (D94)."""

import unittest

import forge
from forge.core.axis import (axis_aligned_share, axis_lines, cluster_values, covered_rectangles,
                             interval_coverage, items_inside, merge_intervals, spanning_lines)
from forge.core.primitives.segments import ArcSeg, LineSeg


def _rect(x0, y0, x1, y1):
    return [LineSeg(start=(x0, y0), end=(x1, y0)), LineSeg(start=(x1, y0), end=(x1, y1)),
            LineSeg(start=(x1, y1), end=(x0, y1)), LineSeg(start=(x0, y1), end=(x0, y0))]


class TestIntervals(unittest.TestCase):

    def test_unione(self):
        self.assertEqual(merge_intervals([(5, 8), (0, 2), (1, 3)]), [(0, 3), (5, 8)])
        self.assertEqual(merge_intervals([(0, 2), (2.5, 4)], tolerance=0.5), [(0, 4)])

    def test_copertura(self):
        self.assertAlmostEqual(interval_coverage([(0, 4), (6, 10)], 0, 10), 0.8)
        self.assertAlmostEqual(interval_coverage([(-5, 20)], 0, 10), 1.0)
        self.assertEqual(interval_coverage([(0, 1)], 3, 3), 0.0)

    def test_raggruppa_valori(self):
        self.assertEqual(cluster_values([10.0, 0.0, 1.0, 10.5], tolerance=1.5), [0.0, 10.0])


class TestCoveredRectangles(unittest.TestCase):

    def test_doppio_bordo_due_rettangoli(self):
        items = _rect(0, 0, 420, 297) + _rect(10, 10, 410, 287)
        rects = covered_rectangles(items, min_side=100)
        bboxes = sorted(r.bbox for r in rects)
        self.assertIn((0.0, 0.0, 420.0, 297.0), bboxes)
        self.assertIn((10.0, 10.0, 410.0, 287.0), bboxes)

    def test_lato_spezzato_da_tacche_resta_coperto(self):
        top = [LineSeg(start=(x, 100), end=(x + 19, 100)) for x in range(0, 200, 20)]
        items = [LineSeg(start=(0, 0), end=(200, 0)), LineSeg(start=(200, 0), end=(200, 100)),
                 LineSeg(start=(0, 100), end=(0, 0))] + top + [LineSeg(start=(50, 100), end=(150, 100))]
        (rect,) = covered_rectangles(items, min_side=50)
        self.assertEqual(rect.bbox, (0.0, 0.0, 200.0, 100.0))
        self.assertAlmostEqual(rect.ratio, 2.0)

    def test_lato_mancante(self):
        self.assertEqual(covered_rectangles(_rect(0, 0, 100, 50)[:3], min_side=10), [])

    def test_api_pubblica(self):
        self.assertIs(forge.covered_rectangles, covered_rectangles)


class TestSpanningLines(unittest.TestCase):

    def test_righe_e_colonne(self):
        items = _rect(0, 0, 100, 40) + [LineSeg(start=(0, 20), end=(100, 20)),
                                        LineSeg(start=(60, 0), end=(60, 40)),
                                        LineSeg(start=(0, 30), end=(30, 30))]   # troppo corta
        self.assertEqual(spanning_lines((0, 0, 100, 40), items), ([20.0], [60.0]))


class TestMeasures(unittest.TestCase):

    def test_tratti_dentro(self):
        items = [LineSeg(start=(1, 1), end=(9, 9)), LineSeg(start=(1, 1), end=(11, 1))]
        self.assertEqual(items_inside((0, 0, 10, 10), items), items[:1])
        self.assertEqual(len(items_inside((0, 0, 10, 10), items, margin=1.5)), 2)

    def test_quota_allineata_agli_assi(self):
        segs = [LineSeg(start=(0, 0), end=(30, 0)), LineSeg(start=(0, 0), end=(10, 10 * 3 ** 0.5))]
        self.assertAlmostEqual(axis_aligned_share(segs, angle_tolerance=2.0), 30 / 50)
        self.assertIsNone(axis_aligned_share([ArcSeg(center=(0, 0), radius=1, start_angle=0, end_angle=1)], 2.0))

    def test_orizzontali_e_verticali(self):
        horiz, vert = axis_lines(_rect(0, 0, 10, 5))
        self.assertEqual(sorted(h.at for h in horiz), [0.0, 5.0])
        self.assertEqual(sorted(v.at for v in vert), [0.0, 10.0])


if __name__ == "__main__":
    unittest.main()
