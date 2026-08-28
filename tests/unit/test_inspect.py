"""
tests/unit/test_inspect.py
--------------------------
Smoke test dei tre livelli di forge.inspect: non devono sollevare e devono
stampare qualcosa di sensato.
"""

import io
import unittest
from contextlib import redirect_stdout

import ezdxf

import forge


def _square_msp(side: float = 100.0):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    pts = [(0, 0), (side, 0), (side, side), (0, side), (0, 0)]
    for a, b in zip(pts, pts[1:]):
        msp.add_line(a, b)
    return doc, msp


class TestInspectLevels(unittest.TestCase):

    def test_level2_document(self):
        _, msp = _square_msp()
        doc = forge.document_from_msp(msp, tolerance=0.5)
        buf = io.StringIO()
        with redirect_stdout(buf):
            forge.inspect_document(doc)
        out = buf.getvalue()
        self.assertIn("LIVELLO 2", out)
        self.assertIn("edge: 4", out)
        self.assertIn("grafo nodi", out)

    def test_level3_result(self):
        _, msp = _square_msp()
        doc = forge.document_from_msp(msp, tolerance=0.5)
        result = forge.heal(doc, tolerance=0.5)
        buf = io.StringIO()
        with redirect_stdout(buf):
            forge.inspect_result(result)
        out = buf.getvalue()
        self.assertIn("LIVELLO 3", out)
        self.assertIn("PARTE 0", out)
        self.assertIn("role=outer", out)

    def test_inspect_functions_exported(self):
        for name in ("inspect_dxf", "inspect_document", "inspect_result", "inspect_file"):
            self.assertIn(name, forge.__all__)
            self.assertTrue(callable(getattr(forge, name)))


if __name__ == "__main__":
    unittest.main()
