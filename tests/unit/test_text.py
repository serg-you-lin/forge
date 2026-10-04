"""
tests/unit/test_text.py
-----------------------
`to_text()`: il modello come testo per un lettore che è un modello linguistico
(MAP.md D84, sperimentale). Geometria costruita con `load_geometry`.
"""

import unittest

import forge
from forge.model.annotation import Dimension, Leader, Note


def _plate():
    """Piastra 100 x 50 con un cerchio Ø10, uno stadio, un contorno a L, una linea aperta e una spline."""
    entities = [
        {"type": "polyline", "points": [(0, 0), (100, 0), (100, 50), (0, 50)], "closed": True},
        {"type": "circle", "center": (20, 25), "radius": 5},
        # stadio 20 x 8: due semicerchi R4 e due lati paralleli
        {"type": "line", "start": (44, 21), "end": (56, 21)},
        {"type": "arc", "center": (56, 25), "radius": 4, "start_angle": 270, "end_angle": 90},
        {"type": "line", "start": (56, 29), "end": (44, 29)},
        {"type": "arc", "center": (44, 25), "radius": 4, "start_angle": 90, "end_angle": 270},
        # contorno a L: nessun nome breve, si scrive lato per lato
        {"type": "polyline", "points": [(70, 10), (90, 10), (90, 20), (80, 20), (80, 40), (70, 40)],
         "closed": True},
        # una linea aperta dentro la piastra, e una spline aperta
        {"type": "line", "start": (20, 15), "end": (20, 35)},
        {"type": "spline", "degree": 3, "control_points": [(5, 5), (10, 15), (15, 5), (20, 15)],
         "knots": [0, 0, 0, 0, 1, 1, 1, 1]},
    ]
    doc = forge.load_geometry(entities, tolerance=0.01)
    result = forge.heal(doc)
    # l'ordine degli inners non è garantito: la freccia punta al cerchio, cercato per forma
    circle = next(j for j, c in enumerate(result.clusters[0].inners)
                  if forge.geometry.contour_shape(c).kind == "circle")
    result.annotations = [
        Dimension(position=(50, 60), measured_value=100.0, text_override="100",
                  references=["clusters[0].outer"]),
        Dimension(position=(20, 40), measured_value=10.0, text_override="Ø10", dim_type="diameter"),
        Leader(position=(25, 30), vertices=[(25, 30)], target=f"clusters[0].inners[{circle}]"),
        Note(position=(50, -10), text="PIASTRA", cluster_ref=None),
    ]
    return result


def _line_of(text, prefix):
    return next(line for line in text.splitlines() if line.startswith(prefix))


class TestToText(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.result = _plate()
        cls.text = forge.to_text(cls.result, "plate.dxf")
        print(cls.text)

    def test_001_header_and_sections(self):
        # la prima riga dice cos'è il file: il lettore lo riconosce dal contenuto
        self.assertTrue(self.text.startswith("# forge reading of plate.dxf\nformat: forge-text 0"))
        for section in ("## contours", "## open edges", "## dimensions and leaders",
                        "## texts", "## detected", "## not understood"):
            self.assertIn(section, self.text)

    def test_002_named_shapes_on_one_line(self):
        self.assertEqual(_line_of(self.text, "C1:"), "C1: outer rectangle 100 x 50 centre (50,25)")
        inner = [l for l in self.text.splitlines() if l.startswith("C1.")]
        self.assertIn("circle D10 centre (20,25)", " ".join(inner))
        self.assertIn("stadium 20 x 8 centre (50,25)", " ".join(inner))

    def test_003_unnamed_contour_side_by_side(self):
        # la L non ha un nome breve: senza i lati si perderebbe posizione e forma
        head = next(l for l in self.text.splitlines() if l.startswith("C1.") and "segments:" in l)
        self.assertIn("6 segments", head)
        self.assertIn("  line (90,10) (90,20)", self.text)

    def test_004_annotations_reuse_the_ids(self):
        self.assertIn("dim linear '100' measured 100 -> C1", self.text)
        circle_id = next(l.split(":")[0] for l in self.text.splitlines() if "circle D10" in l)
        self.assertIn(f"leader at (25,30) -> {circle_id}", self.text)

    def test_005_unanchored_goes_to_not_understood(self):
        # niente si perde in silenzio: la quota senza elemento sta in fondo
        tail = self.text.split("## not understood")[1]
        self.assertIn("dim diameter 'Ø10' measured 10 at (20,40): no element found", tail)

    def test_006_open_edges_listed_with_geometry(self):
        self.assertIn("continuous: line (20,15) (20,35)", self.text)

    def test_007_spline_described_not_discretized(self):
        # estremi, ingombro e lunghezza; i punti di controllo solo se chiesti
        spline = _line_of(self.text.split("## open edges")[1].split("\n", 1)[1], "continuous: spline")
        self.assertIn("from (5,5) to (20,15)", spline)
        self.assertIn("length", spline)
        self.assertNotIn("ctrl", self.text)
        exact = forge.to_text(self.result, spline_data=True)
        self.assertIn("ctrl (5,5) (10,15) (15,5) (20,15)", exact)
        self.assertNotIn("knots", exact, "nodi bloccati e uniformi: non si scrivono")

    def test_008_decimals(self):
        text = forge.to_text(self.result, decimals=1)
        self.assertIn("circle D10 centre (20,25)", text)
        self.assertNotIn(".000", self.text)

    def test_009_detected_written_generically(self):
        # forge non sa cosa sia un elemento di `detected`: lo riporta e basta (come D70)
        from dataclasses import dataclass

        @dataclass
        class Countersink:
            source: str
            confidence: float
            top_diameter: float

        result = _plate()
        cluster = result.clusters[0]
        if cluster.detected is None:
            from forge.model import DetectedFeatures
            cluster.detected = DetectedFeatures()
        cluster.detected.add("countersinks", Countersink("test", 0.9, 7.8))
        text = forge.to_text(result)
        self.assertIn("C1.countersinks[1]: Countersink source=test confidence=0.9 top_diameter=7.8", text)

    def test_010_save_text(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plate.forge.md"
            forge.save_text(self.result, path, "plate.dxf")
            self.assertEqual(path.read_text(encoding="utf-8"), self.text)


if __name__ == "__main__":
    unittest.main()
