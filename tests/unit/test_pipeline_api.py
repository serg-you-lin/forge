"""
tests/unit/test_pipeline_api.py
-------------------------------
Copre la superficie API introdotta in Fase 3 (MAP.md D2, D3):
  - forge.heal_and_detect(doc) -> ForgeResult
  - forge.detect(result) e forge.inject(result) ritornano il ForgeResult
"""

import unittest
import ezdxf

import forge


def _square_doc(side: float = 100.0):
    d = ezdxf.new("R2010")
    msp = d.modelspace()
    pts = [(0, 0), (side, 0), (side, side), (0, side), (0, 0)]
    for a, b in zip(pts, pts[1:]):
        msp.add_line(a, b)
    return forge.document_from_msp(msp, tolerance=0.5)


class TestPipelineApi(unittest.TestCase):

    def test_heal_and_detect_returns_result(self):
        r = forge.heal_and_detect(_square_doc(), label="X")
        self.assertIsInstance(r, forge.ForgeResult)
        self.assertTrue(r.is_valid)
        self.assertEqual(r.cluster_count, 1)

    def test_heal_and_detect_equivalent_to_separate_calls(self):
        doc_a, doc_b = _square_doc(), _square_doc()
        combined = forge.heal_and_detect(doc_a)
        step = forge.detect(forge.heal(doc_b), features="all")
        self.assertEqual(combined.cluster_count, step.cluster_count)
        self.assertEqual(
            [h.hole_type for p in combined.clusters for h in p.holes],
            [h.hole_type for p in step.clusters for h in p.holes],
        )

    def test_detect_returns_same_result_object(self):
        result = forge.heal(_square_doc())
        self.assertIs(forge.detect(result), result)

    def test_inject_returns_same_result_object(self):
        result = forge.detect(forge.heal(_square_doc()))
        self.assertIs(forge.inject(result), result)

    def test_heal_and_detect_invalid_still_returns_result(self):
        # 3 lati di un quadrato: nessun contorno chiuso -> non valido
        d = ezdxf.new("R2010")
        msp = d.modelspace()
        for a, b in [((0, 0), (100, 0)), ((100, 0), (100, 100)), ((100, 100), (0, 100))]:
            msp.add_line(a, b)
        doc = forge.document_from_msp(msp, tolerance=0.5)
        r = forge.heal_and_detect(doc)
        self.assertIsInstance(r, forge.ForgeResult)
        self.assertFalse(r.is_valid)
        self.assertTrue(r.errors)

    def test_heal_and_detect_exported(self):
        self.assertIn("heal_and_detect", forge.__all__)


if __name__ == "__main__":
    unittest.main()
