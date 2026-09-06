"""
test_golden_annotations.py
--------------------------
Regressione sull'estrazione delle annotazioni: confronta
`forge.load_dxf(...).annotations` (Note / Dimension / Leader) con i golden in
tests/examples/golden/annotations/.

Golden generati da tests/generate_golden_annotations.py — da rigenerare solo
dopo aver verificato a mano che l'estrazione è giusta, mai per far passare un
test.

Un test per fixture, generato dalla fabbrica in fondo al file.
"""

import json
import sys
import unittest
from collections import Counter
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge.model.annotation import Note, Dimension, Leader

EXAMPLES_DIR = project_root / "tests" / "examples"
GOLDEN_DIR = EXAMPLES_DIR / "golden" / "annotations"
_SOURCE_DIRS = [EXAMPLES_DIR, EXAMPLES_DIR / "golden"]


def _find_source(name: str):
    for d in _SOURCE_DIRS:
        p = d / name
        if p.exists():
            return p
    return None

TOL_POS = 0.05      # mm — tolleranza sulla posizione d'ancoraggio
TOL_VALUE = 0.01    # mm — tolleranza sul valore misurato


def _golden_files():
    if not GOLDEN_DIR.exists():
        return []
    return sorted(GOLDEN_DIR.glob("*.json"))


def _rendered_counts(r) -> dict:
    return {"strokes": len(r.strokes), "fills": len(r.fills), "texts": len(r.texts)}


def _actual_dict(a) -> dict:
    d = {
        "type": type(a).__name__,
        "kind": a.kind,
        "position": [round(a.position[0], 3), round(a.position[1], 3)],
        "display_text": a.display_text,
        "layer": a.layer,
    }
    if isinstance(a, Note):
        d["height"] = round(a.height, 3)
        d["rotation"] = round(a.rotation, 3)
    elif isinstance(a, Dimension):
        d["dim_type"] = a.dim_type
        d["measured_value"] = (
            None if a.measured_value is None else round(a.measured_value, 4)
        )
        d["text_override"] = a.text_override
        d["rendered"] = _rendered_counts(a.rendered)
    elif isinstance(a, Leader):
        d["vertices"] = len(a.vertices)
        d["rendered"] = _rendered_counts(a.rendered)
    return d


def _sort_key(entry: dict):
    return (entry["position"][0], entry["position"][1], entry["kind"], entry["display_text"])


def _make_test(path: Path):

    def test(self):
        golden = json.loads(path.read_text(encoding="utf-8"))
        dxf_path = _find_source(golden["source_file"])
        if dxf_path is None:
            self.skipTest(golden["source_file"])

        doc = forge.load_dxf(
            dxf_path, explode_inserts=True, flatten_z_flag=True, verbose=False
        )
        actual = sorted((_actual_dict(a) for a in doc.annotations), key=_sort_key)
        expected = golden["annotations"]

        self.assertEqual(
            len(actual), golden["annotation_count"],
            msg=f"{golden['source_file']}: numero annotazioni",
        )
        self.assertEqual(
            dict(Counter(e["kind"] for e in actual)), golden["by_kind"],
            msg=f"{golden['source_file']}: conteggio per tipo",
        )

        for i, (act, exp) in enumerate(zip(actual, expected)):
            ctx = f"{golden['source_file']} annotazione[{i}]"
            self.assertEqual(act["type"], exp["type"], msg=f"{ctx}: type")
            self.assertEqual(act["kind"], exp["kind"], msg=f"{ctx}: kind")
            self.assertEqual(act["display_text"], exp["display_text"], msg=f"{ctx}: display_text")
            self.assertEqual(act["layer"], exp["layer"], msg=f"{ctx}: layer")
            self.assertAlmostEqual(act["position"][0], exp["position"][0], delta=TOL_POS, msg=f"{ctx}: x")
            self.assertAlmostEqual(act["position"][1], exp["position"][1], delta=TOL_POS, msg=f"{ctx}: y")

            if exp["type"] == "Note":
                self.assertAlmostEqual(act["height"], exp["height"], delta=TOL_VALUE, msg=f"{ctx}: height")
                self.assertAlmostEqual(act["rotation"], exp["rotation"], delta=TOL_VALUE, msg=f"{ctx}: rotation")
            elif exp["type"] == "Dimension":
                self.assertEqual(act["dim_type"], exp["dim_type"], msg=f"{ctx}: dim_type")
                self.assertEqual(act["text_override"], exp["text_override"], msg=f"{ctx}: text_override")
                self.assertEqual(act["rendered"], exp["rendered"], msg=f"{ctx}: rendered counts")
                if exp["measured_value"] is None:
                    self.assertIsNone(act["measured_value"], msg=f"{ctx}: measured_value")
                else:
                    self.assertAlmostEqual(
                        act["measured_value"], exp["measured_value"],
                        delta=TOL_VALUE, msg=f"{ctx}: measured_value",
                    )
            elif exp["type"] == "Leader":
                self.assertEqual(act["vertices"], exp["vertices"], msg=f"{ctx}: vertices")
                self.assertEqual(act["rendered"], exp["rendered"], msg=f"{ctx}: rendered counts")

    return test


class TestGoldenAnnotations(unittest.TestCase):
    pass


for _golden in _golden_files():
    setattr(TestGoldenAnnotations, f"test_{_golden.stem}", _make_test(_golden))


class TestGoldenAnnotationsSetup(unittest.TestCase):
    def test_golden_dir_populated(self):
        self.assertGreater(len(_golden_files()), 0, "nessun golden annotazioni")


if __name__ == "__main__":
    unittest.main()
