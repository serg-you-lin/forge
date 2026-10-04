# tests/unit/core/test_concentric.py
"""`concentric_groups` e `arcs_around`: fatti geometrici fra più contorni (D91)."""

import math
import unittest

import forge
from forge.core.primitives.segments import ArcSeg, CircleSeg, LineSeg
from forge.core.geometry.shape import arcs_around, concentric_groups


def _circle(c, r):
    return [CircleSeg(center=c, radius=r)]


def _square(c, half):
    x, y = c
    pts = [(x - half, y - half), (x + half, y - half), (x + half, y + half), (x - half, y + half)]
    return [LineSeg(start=pts[i], end=pts[(i + 1) % 4]) for i in range(4)]


class TestConcentricGroups(unittest.TestCase):

    def test_due_cerchi_concentrici_e_uno_isolato(self):
        small, big, alone = _circle((0, 0), 2), _circle((0.05, 0), 4), _circle((20, 0), 2)
        groups = concentric_groups([big, alone, small])
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0].items, (small, big))
        self.assertEqual(groups[0].diameters, (4, 8))
        self.assertEqual(groups[0].center, (0, 0))
        self.assertEqual(groups[1].items, (alone,))

    def test_fuori_tolleranza_non_si_uniscono(self):
        a, b = _circle((0, 0), 2), _circle((0.5, 0), 4)
        self.assertEqual(len(concentric_groups([a, b])), 2)
        self.assertEqual(len(concentric_groups([a, b], tolerance=1.0)), 1)

    def test_i_non_cerchi_non_compaiono(self):
        groups = concentric_groups([_square((0, 0), 5), _circle((0, 0), 2)])
        self.assertEqual([len(g.items) for g in groups], [1])

    def test_tre_cerchi_dal_minore_al_maggiore(self):
        rings = [_circle((0, 0), r) for r in (6, 2, 4)]
        (group,) = concentric_groups(rings)
        self.assertEqual(group.diameters, (4, 8, 12))

    def test_api_pubblica(self):
        self.assertIs(forge.geometry.concentric_groups, concentric_groups)
        self.assertIs(forge.geometry.arcs_around, arcs_around)


class TestArcsAround(unittest.TestCase):

    def _arc(self, c, r, sweep_deg):
        return ArcSeg(center=c, radius=r, start_angle=0.0, end_angle=math.radians(sweep_deg))

    def test_arco_di_tre_quarti(self):
        (found,) = arcs_around((0, 0), 2.5, [self._arc((0, 0), 3, 270)])
        self.assertAlmostEqual(found.sweep, 270)
        self.assertAlmostEqual(found.radius_ratio, 1.2)

    def test_solo_archi_piu_grandi_e_concentrici(self):
        arcs = [self._arc((0, 0), 2, 270),       # più piccolo
                self._arc((5, 0), 3, 270),       # altro centro
                self._arc((0, 0), 10, 90),
                self._arc((0, 0.05), 3, 270)]
        found = arcs_around((0, 0), 2.5, arcs)
        self.assertEqual([a.arc for a in found], [arcs[3], arcs[2]])

    def test_ignora_cio_che_non_e_arco(self):
        self.assertEqual(arcs_around((0, 0), 1, [CircleSeg(center=(0, 0), radius=2)]), [])

    def test_arco_orario(self):
        arc = ArcSeg(center=(0, 0), radius=3, start_angle=0.0, end_angle=math.radians(90), ccw=False)
        (found,) = arcs_around((0, 0), 2, [arc])
        self.assertAlmostEqual(found.sweep, 270)


if __name__ == "__main__":
    unittest.main()
