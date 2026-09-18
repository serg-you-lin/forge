"""
tests/integration/test_ellipse_roundtrip.py
---------------------------------------------
Test end-to-end (ezdxf reale, non mock) per l'ELLIPSE: load -> heal -> to_dxf
-> reload, per un'ellisse piena (standalone) e un arco ellittico misto a
linee. Verifica che l'ELLIPSE esca nativa in output (mai discretizzata a
spline) e che il roundtrip riproduca la stessa geometria.

Lancia:
    python -m pytest tests/integration/test_ellipse_roundtrip.py -v
"""

import math
import unittest

import ezdxf

import forge


class TestFullEllipseOuter(unittest.TestCase):
    """Un'ELLIPSE piena, sola geometria del file: un cluster, outer ellittico."""

    def setUp(self):
        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_ellipse(center=(5, 5), major_axis=(10, 0), ratio=0.5)
        self.fdoc = forge.document_from_msp(msp)
        self.result = forge.heal(self.fdoc)

    def test_001_one_valid_cluster(self):
        self.assertTrue(self.result.is_valid)
        self.assertEqual(self.result.cluster_count, 1)

    def test_002_area_matches_ellipse_formula(self):
        # area = pi * a * b, a=10 (semiasse maggiore), b=5 (ratio 0.5)
        expected = math.pi * 10 * 5
        area = self.result.clusters[0].outer.area
        self.assertAlmostEqual(area, expected, delta=1.0)

    def test_003_writes_native_ellipse(self):
        doc_out = forge.to_dxf(self.result, self.fdoc)
        ellipses = list(doc_out.modelspace().query("ELLIPSE"))
        self.assertEqual(len(ellipses), 1)
        e = ellipses[0]
        self.assertAlmostEqual(e.dxf.center.x, 5.0, places=6)
        self.assertAlmostEqual(e.dxf.center.y, 5.0, places=6)
        self.assertAlmostEqual(e.dxf.major_axis.x, 10.0, places=6)
        self.assertAlmostEqual(e.dxf.major_axis.y, 0.0, places=6)
        self.assertAlmostEqual(e.dxf.ratio, 0.5, places=6)

    def test_004_no_spline_written(self):
        """Un'ellisse non deve mai uscire come SPLINE — è una conica esatta,
        non un'approssimazione (stesso principio delle spline mai discretizzate)."""
        doc_out = forge.to_dxf(self.result, self.fdoc)
        self.assertEqual(len(list(doc_out.modelspace().query("SPLINE"))), 0)

    def test_005_roundtrip_area_stable(self):
        """Ricaricando l'output con forge stesso si ritrova la stessa area."""
        doc_out = forge.to_dxf(self.result, self.fdoc)
        reloaded = forge.heal(forge.document_from_msp(doc_out.modelspace()))
        self.assertEqual(reloaded.cluster_count, 1)
        self.assertAlmostEqual(
            reloaded.clusters[0].outer.area,
            self.result.clusters[0].outer.area,
            delta=0.5,
        )


class TestEllipticalArcMixedWithLines(unittest.TestCase):
    """Un quarto di ellisse (arco aperto) + 2 LINE chiudono un contorno."""

    def setUp(self):
        doc = ezdxf.new()
        msp = doc.modelspace()
        # quarto di ellisse da (20,0) a (0,10) — CCW, param 0 -> pi/2
        msp.add_ellipse(center=(0, 0), major_axis=(20, 0), ratio=0.5,
                         start_param=0.0, end_param=math.pi / 2)
        msp.add_line((0, 10), (0, 0))
        msp.add_line((0, 0), (20, 0))
        self.fdoc = forge.document_from_msp(msp)
        self.result = forge.heal(self.fdoc)

    def test_001_closes_into_one_valid_cluster(self):
        self.assertTrue(self.result.is_valid, self.result.errors)
        self.assertEqual(self.result.cluster_count, 1)

    def test_002_area_matches_quarter_ellipse(self):
        # settore delimitato dai due semiassi e dall'arco = un quarto
        # dell'area totale dell'ellisse (a=20, b=10)
        expected = 0.25 * math.pi * 20 * 10
        area = self.result.clusters[0].outer.area
        self.assertAlmostEqual(area, expected, delta=1.0)

    def test_003_writes_native_ellipse_not_spline(self):
        doc_out = forge.to_dxf(self.result, self.fdoc)
        msp_out = doc_out.modelspace()
        self.assertEqual(len(list(msp_out.query("ELLIPSE"))), 1)
        self.assertEqual(len(list(msp_out.query("SPLINE"))), 0)

    def test_004_roundtrip_area_stable(self):
        doc_out = forge.to_dxf(self.result, self.fdoc)
        reloaded = forge.heal(forge.document_from_msp(doc_out.modelspace()))
        self.assertEqual(reloaded.cluster_count, 1)
        self.assertAlmostEqual(
            reloaded.clusters[0].outer.area,
            self.result.clusters[0].outer.area,
            delta=0.5,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
