"""
test_golden_anchoring.py
------------------------
Regressione sugli agganci delle annotazioni nei disegni di viste: per ogni
quota e freccia, l'elemento a cui `anchor_annotations` la lega
(`Dimension.references`, `Leader.target`, D66/D69), descritto con la sua
forma (`contour_shape`) e non col suo indice — un riordino degli `inners`
non è una regressione, un aggancio a un altro cerchio sì.

Disegni in `tests/data/golden_anchoring/` (`anch_NN.dxf`, fogli del campione
`islands` rinominati), golden in `json/` accanto. Senza i disegni il test si
salta.

Golden da rigenerare solo dopo aver verificato a mano che gli agganci sono
giusti, mai per far passare un test:

    python tests/real/test_golden_anchoring.py --generate
"""

import json
import sys
import unittest
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge.model.annotation import Dimension, Leader

# max_gap non ha default (D98); island_gap non esiste più (D99)
MAX_GAP = 0.5

SOURCE_DIR = project_root / "tests" / "data" / "golden_anchoring"
GOLDEN_DIR = SOURCE_DIR / "json"

FILES = [f"anch_{i:02d}.dxf" for i in range(1, 9)]


def _element(result, path):
    """L'elemento agganciato: collezione + forma, senza indice."""
    item = forge.resolve_target(result, path)
    collection = path.split(".")[1].split("[")[0]
    shape = forge.geometry.contour_shape(item) if item is not None else None
    if shape is None:
        return {"in": collection, "shape": None}
    return {"in": collection, "shape": shape.kind,
            "center": [round(shape.center[0], 2), round(shape.center[1], 2)],
            "length": round(shape.length, 3), "width": round(shape.width, 3)}


def snapshot(dxf_path: Path) -> dict:
    result = forge.anchor_annotations(forge.island(forge.load_dxf(str(dxf_path)), max_gap=MAX_GAP))
    entries = []
    for a in result.annotations:
        if isinstance(a, Dimension):
            paths, extra = a.references, {"dim_type": a.dim_type}
        elif isinstance(a, Leader):
            paths, extra = [a.target] if a.target else [], {}
        else:
            continue
        entries.append({"type": type(a).__name__, **extra, "display_text": a.display_text,
                        "position": [round(a.position[0], 2), round(a.position[1], 2)],
                        "anchored": [_element(result, p) for p in paths]})
    entries.sort(key=lambda e: (e["position"], e["type"], e["display_text"]))
    return {"source_file": dxf_path.name, "annotations": entries}


def _golden_path(name: str) -> Path:
    return GOLDEN_DIR / (Path(name).stem + ".json")


class TestGoldenAnchoring(unittest.TestCase):
    pass


def _make_test(name: str):
    def test(self):
        dxf_path, golden_path = SOURCE_DIR / name, _golden_path(name)
        if not dxf_path.exists() or not golden_path.exists():
            self.skipTest(name)
        expected = json.loads(golden_path.read_text(encoding="utf-8"))["annotations"]
        actual = snapshot(dxf_path)["annotations"]
        self.assertEqual(len(actual), len(expected), msg=f"{name}: numero annotazioni")
        for i, (act, exp) in enumerate(zip(actual, expected)):
            self.assertEqual(act, exp, msg=f"{name} annotazione[{i}] {exp['display_text']!r}")
    return test


for _name in FILES:
    setattr(TestGoldenAnchoring, f"test_{Path(_name).stem}", _make_test(_name))


def generate():
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        dxf_path = SOURCE_DIR / name
        if not dxf_path.exists():
            print(f"  manca: {name}")
            continue
        snap = snapshot(dxf_path)
        _golden_path(name).write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
        anchored = sum(bool(e["anchored"]) for e in snap["annotations"])
        print(f"  OK: {name} — {anchored}/{len(snap['annotations'])} agganciate")


if __name__ == "__main__":
    if "--generate" in sys.argv:
        generate()
    else:
        unittest.main()
