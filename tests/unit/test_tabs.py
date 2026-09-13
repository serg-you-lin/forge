"""
test_tabs.py
------------
Test unitari per forge.tools.tabs.cut_tabs (MAP.md D39).

Nota: la rappresentazione della posizione di una linguetta (oggi un indice in
`points`) non è ancora una decisione definitiva — questi test coprono il
comportamento della prima implementazione, non blindano la forma dell'API.
"""

import math
import unittest
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from forge.tools.tabs import cut_tabs


class TestCutTabsOpenSequence(unittest.TestCase):

    def test_001_no_tabs_returns_unchanged(self):
        pts = [(0, 0), (1, 0), (2, 0), (3, 0)]
        self.assertEqual(cut_tabs(pts, closed=False, tab_positions=[], tab_width=1.0), [pts])

    def test_002_single_tab_splits_into_two_stretches(self):
        pts = [(i, 0) for i in range(11)]  # 0..10, spaziatura 1
        stretches = cut_tabs(pts, closed=False, tab_positions=[5], tab_width=2.0)
        self.assertEqual(len(stretches), 2)
        # gap = [center-1, center+1] = [4, 6] inclusi -> restano 0..3 e 7..10
        self.assertEqual(stretches[0][-1], (3, 0))
        self.assertEqual(stretches[1][0], (7, 0))

    def test_003_tab_at_start_only_trims_one_side(self):
        pts = [(i, 0) for i in range(11)]
        stretches = cut_tabs(pts, closed=False, tab_positions=[0], tab_width=2.0)
        self.assertEqual(len(stretches), 1)
        self.assertEqual(stretches[0][0], (2, 0))


class TestCutTabsClosedSequence(unittest.TestCase):

    def _circle(self, n=24, r=10.0):
        return [
            (r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n))
            for i in range(n)
        ]

    def test_001_no_tabs_returns_reclosed_loop(self):
        pts = self._circle()
        result = cut_tabs(pts, closed=True, tab_positions=[], tab_width=1.0)
        self.assertEqual(result, [pts])

    def test_002_one_tab_on_circle_gives_one_open_stretch(self):
        pts = self._circle(n=36, r=10.0)
        # spaziatura fra punti ~ 2*pi*10/36 ~ 1.75; una linguetta larga 3 copre ~2 punti
        stretches = cut_tabs(pts, closed=True, tab_positions=[0], tab_width=3.0)
        self.assertEqual(len(stretches), 1)
        # il tratto tenuto è tutto tranne l'intorno dell'indice 0
        self.assertNotIn(pts[0], stretches[0])

    def test_003_four_tabs_give_four_stretches(self):
        n = 40
        pts = self._circle(n=n, r=10.0)
        positions = [0, n // 4, n // 2, 3 * n // 4]
        stretches = cut_tabs(pts, closed=True, tab_positions=positions, tab_width=2.0)
        self.assertEqual(len(stretches), 4)

    def test_004_tabs_covering_everything_returns_empty(self):
        pts = self._circle(n=8, r=10.0)
        stretches = cut_tabs(pts, closed=True, tab_positions=list(range(8)), tab_width=100.0)
        self.assertEqual(stretches, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
