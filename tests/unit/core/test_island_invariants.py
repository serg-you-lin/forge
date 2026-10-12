# tests/unit/core/test_island_invariants.py

"""
Invarianti di `island()` che devono valere sempre, per qualunque disegno —
non confrontano contro un valore congelato (un golden): o sono vere o il
motore ha un difetto. Non vanno mai rigenerate né guardate a occhio (a
differenza di `tests/real/test_golden_islands.py`). Fixture: gli stessi
disegni reali, `tests/data/golden_islands/`.
"""

import tempfile
import unittest
from pathlib import Path

import forge
from forge.core.island import GRAPH_EPSILON
from forge.core.primitives.segments import DEFAULT_TOLERANCE

MAX_GAP = 0.5
SOURCE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "golden_islands"
# lo stesso contorno può dare un `.polygon` diverso di tanto così: la freccia
# della discretizzazione più la griglia dei nodi dell'unione di facce (D106)
BOUNDS_TOLERANCE = DEFAULT_TOLERANCE + GRAPH_EPSILON


def _snapshot(result) -> list:
    return sorted([float(v) for v in c.outer.polygon.bounds] + [len(c.inners)]
                  for c in result.clusters)


def _unmatched(before: list, after: list) -> list:
    """Le isole di `before` senza una gemella in `after`: stesso numero di
    inner, riquadro entro BOUNDS_TOLERANCE (accoppiamento uno a uno)."""
    free = list(after)
    missing = []
    for item in before:
        twin = next((other for other in free if other[4] == item[4]
                     and all(abs(x - y) <= BOUNDS_TOLERANCE for x, y in zip(item[:4], other[:4]))),
                    None)
        if twin is None:
            missing.append([round(v, 3) for v in item])
        else:
            free.remove(twin)
    return missing


class TestPolygonValidity(unittest.TestCase):
    """Ogni poligono letto da `island()` — outer e inner — è una forma
    semplice (non autointersecante): un poligono autointersecante dà
    un'area calcolata per cancellazione di segno, non la forma vera."""

    def _assert_valid(self, contour, where):
        self.assertTrue(contour.polygon.is_valid, f"{where}: .polygon non è una forma semplice")
        self.assertGreater(contour.polygon.area, 0, f"{where}: .polygon ha area nulla")


def _make_validity_test(dxf: Path):
    def test(self):
        result = forge.island(forge.load_dxf(str(dxf)), max_gap=MAX_GAP)
        for ci, cluster in enumerate(result.clusters):
            self._assert_valid(cluster.outer, f"{dxf.stem}.cluster[{ci}].outer")
            for ii, inner in enumerate(cluster.inners):
                self._assert_valid(inner, f"{dxf.stem}.cluster[{ci}].inner[{ii}]")
    return test


for _dxf in sorted(SOURCE_DIR.glob("*.dxf")):
    setattr(TestPolygonValidity, f"test_{_dxf.stem}", _make_validity_test(_dxf))


class TestRoundtripStable(unittest.TestCase):
    """Esportare in DXF e rileggere con `island()` deve dare le stesse isole
    (stesso riquadro esterno entro BOUNDS_TOLERANCE, stesso numero di inner
    per isola) — se cambia,
    il motore ha scritto o letto qualcosa di diverso da quello che aveva
    trovato la prima volta. Trovato così il 12 ottobre su `regr_04` (bordo
    doppio in un solo giro): quel caso resta rosso qui finché non è risolto,
    apposta."""


def _make_roundtrip_test(dxf: Path):
    def test(self):
        doc = forge.load_dxf(str(dxf))
        before = forge.island(doc, max_gap=MAX_GAP)
        exported = forge.to_dxf(before, source_doc=doc, allow_invalid=True)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp) / f"{dxf.stem}.dxf"
            exported.saveas(str(tmp_path))
            after = forge.island(forge.load_dxf(str(tmp_path)), max_gap=MAX_GAP)
        snap_before, snap_after = _snapshot(before), _snapshot(after)
        self.assertEqual(len(snap_before), len(snap_after),
                         f"{dxf.stem}: il numero di isole cambia dopo export+reload")
        self.assertEqual(_unmatched(snap_before, snap_after), [],
                         f"{dxf.stem}: le isole cambiano dopo export+reload "
                         f"(dopo: {[[round(v, 3) for v in s] for s in snap_after]})")
    return test


for _dxf in sorted(SOURCE_DIR.glob("*.dxf")):
    setattr(TestRoundtripStable, f"test_{_dxf.stem}", _make_roundtrip_test(_dxf))


if __name__ == "__main__":
    unittest.main()
