"""
tests/unit/test_metadata_xdata.py
---------------------------------
Copre write_metadata_to_dxf / read_metadata_from_dxf.

Regressione: entrambe importavano `from ..rules.layers import LAYER_OUTER`
(modulo inesistente) dentro un try/except → fallivano in silenzio e non
scrivevano mai lo XDATA. Il modulo giusto è `adapters.dxf.layers`.
"""

import unittest
import ezdxf

import forge


def _square_result(side: float = 100.0):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    pts = [(0, 0), (side, 0), (side, side), (0, side), (0, 0)]
    for a, b in zip(pts, pts[1:]):
        msp.add_line(a, b)
    source_doc = forge.document_from_msp(msp, tolerance=0.5)
    result = forge.heal(source_doc, tolerance=0.5)
    assert result.is_valid and result.clusters
    return source_doc, result


class TestMetadataXdataRoundtrip(unittest.TestCase):

    def test_write_then_read_roundtrip(self):
        source_doc, result = _square_result()
        doc_out = forge.to_dxf(result, source_doc)

        forge.write_metadata_to_dxf(doc_out, result.clusters[0])
        meta = forge.read_metadata_from_dxf(doc_out)

        self.assertIsInstance(meta, dict)
        self.assertTrue(meta, "XDATA non scritto: dict vuoto (import rotto?)")
        # area del quadrato 100x100
        area_key = next((k for k in meta if "area" in k.lower()), None)
        self.assertIsNotNone(area_key)
        self.assertAlmostEqual(float(meta[area_key]), 10000.0, delta=1.0)

    def test_read_without_metadata_returns_empty(self):
        source_doc, result = _square_result()
        doc_out = forge.to_dxf(result, source_doc)
        self.assertEqual(forge.read_metadata_from_dxf(doc_out), {})


if __name__ == "__main__":
    unittest.main()
