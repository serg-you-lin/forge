"""
test_golden_islands.py
----------------------
Regressione su `island()` (D99-D100): per ogni foglio di viste, le isole —
riquadro del contorno esterno e numero di contorni interni — e le linee
aperte fuori da ogni isola.

Disegni in `tests/data/golden_islands/` (`anch_NN`, `regr_NN`): copie
anonimizzate dei fogli di snapdraw con la sola geometria che `island()` legge
nel framer — cornice, cartiglio e linee di costruzione tolti da snapdraw, il
file scritto da forge (layer `geometry`). forge non sa cos'è una cornice:
riceve il foglio già ripulito. Isole giudicate giuste da Federico sulla
pagina "Scala delle isole" (5 ottobre). Golden in `json/` accanto; senza i
disegni il test si salta.

Golden da rigenerare solo dopo aver verificato a occhio che le isole sono
giuste, mai per far passare un test:

    python tests/real/test_golden_islands.py --generate
"""

import json
import sys
import unittest
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import forge

MAX_GAP = 0.5    # quello di snapdraw (SHEET_MAX_GAP)
TOL = 0.01       # mm

SOURCE_DIR = project_root / "tests" / "data" / "golden_islands"
GOLDEN_DIR = SOURCE_DIR / "json"


def snapshot(dxf_path: Path) -> dict:
    """Le isole in ordine di riquadro (due isole di area uguale non scambiano il golden)."""
    result = forge.island(forge.load_dxf(str(dxf_path)), max_gap=MAX_GAP)
    islands = sorted([round(float(v), 3) for v in c.outer.polygon.bounds] + [len(c.inners)]
                     for c in result.clusters)
    return {"source_file": dxf_path.name,
            "islands": [{"bbox": i[:4], "inners": i[4]} for i in islands],
            "open_outside": sum(1 for t in result.trash_entities if getattr(t, "cluster_ref", None) is None)}


class TestGoldenIslands(unittest.TestCase):

    def _compare(self, expected, actual, where):
        if isinstance(expected, dict):
            self.assertEqual(sorted(expected), sorted(actual), where)
            for k in expected:
                self._compare(expected[k], actual[k], f"{where}.{k}")
        elif isinstance(expected, list):
            self.assertEqual(len(expected), len(actual), f"{where}: lunghezze diverse")
            for i, (e, a) in enumerate(zip(expected, actual)):
                self._compare(e, a, f"{where}[{i}]")
        elif isinstance(expected, float):
            self.assertAlmostEqual(expected, actual, delta=TOL, msg=where)
        else:
            self.assertEqual(expected, actual, where)


def _make_test(dxf: Path, golden: Path):
    def test(self):
        self._compare(json.loads(golden.read_text(encoding="utf-8")), snapshot(dxf), dxf.stem)
    return test


for _dxf in sorted(SOURCE_DIR.glob("*.dxf")):
    _golden = GOLDEN_DIR / f"{_dxf.stem}.json"
    if _golden.exists():
        setattr(TestGoldenIslands, f"test_{_dxf.stem}", _make_test(_dxf, _golden))


def generate():
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for dxf in sorted(SOURCE_DIR.glob("*.dxf")):
        snap = snapshot(dxf)
        (GOLDEN_DIR / f"{dxf.stem}.json").write_text(json.dumps(snap, indent=2), encoding="utf-8")
        print(f"  OK: {dxf.name} — {len(snap['islands'])} isole, {snap['open_outside']} linee aperte fuori")


if __name__ == "__main__":
    if "--generate" in sys.argv:
        generate()
    else:
        unittest.main()
