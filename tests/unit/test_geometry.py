"""
test_geometry.py
----------------
Test unitari per le funzioni pure di dxf_forge.core.geometry.

Copre:
  - is_threaded_arc      : riconosce archi a 270° (filettatura)
  - is_threaded_hole     : riconosce fori filettati (cerchio + arco concentrico)
  - is_countersink_outer : riconosce il cerchio esterno di un countersink

Lancia con:
    python -m pytest tests/unit/test_geometry.py -v
    oppure
    python -m unittest tests/unit/test_geometry.py -v
"""

import unittest
import math
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import ezdxf
from dxf_forge.core.geometry import is_threaded_arc, is_threaded_hole, is_countersink_outer


# ---------------------------------------------------------------------------
# Helpers — costruiscono entità ezdxf sintetiche senza file su disco
# ---------------------------------------------------------------------------

def _make_arc(cx, cy, radius, start_angle, end_angle):
    doc = ezdxf.new()
    msp = doc.modelspace()
    return msp.add_arc(
        center=(cx, cy),
        radius=radius,
        start_angle=start_angle,
        end_angle=end_angle,
    )


def _make_circle(cx, cy, radius):
    doc = ezdxf.new()
    msp = doc.modelspace()
    return msp.add_circle(center=(cx, cy), radius=radius)


# ---------------------------------------------------------------------------
# is_threaded_arc
# ---------------------------------------------------------------------------

class TestIsThreadedArc(unittest.TestCase):
    """
    Un arco filettato spazza ~270° e lascia un gap di ~90°.
    Tolleranza default: ±20°.
    """

    def test_001_arco_270_gradi_e_filettato(self):
        """Arco che spazza esattamente 270° → True."""
        # start=0°, end=270° → swept=270°
        arc = _make_arc(0, 0, 5, start_angle=0, end_angle=270)
        self.assertTrue(is_threaded_arc(arc))

    def test_002_arco_260_gradi_entro_tolleranza(self):
        """Arco a 260° — entro i ±20° di tolleranza → True."""
        arc = _make_arc(0, 0, 5, start_angle=0, end_angle=260)
        self.assertTrue(is_threaded_arc(arc))

    def test_003_arco_180_gradi_non_filettato(self):
        """Semicerchio a 180° → False."""
        arc = _make_arc(0, 0, 5, start_angle=0, end_angle=180)
        self.assertFalse(is_threaded_arc(arc))

    def test_004_arco_360_non_filettato(self):
        """Cerchio completo → False."""
        arc = _make_arc(0, 0, 5, start_angle=0, end_angle=360)
        self.assertFalse(is_threaded_arc(arc))

    def test_005_entita_non_arc_restituisce_false(self):
        """Se si passa un CIRCLE invece di un ARC → False senza crash."""
        circle = _make_circle(0, 0, 5)
        self.assertFalse(is_threaded_arc(circle))

    def test_006_tolleranza_custom_stretta(self):
        """Con tolleranza 1° un arco a 260° non passa."""
        arc = _make_arc(0, 0, 5, start_angle=0, end_angle=260)
        self.assertFalse(is_threaded_arc(arc, angle_tolerance=1.0))

    def test_007_arco_ruotato_stesso_risultato(self):
        """Un arco a 270° partendo da 45° è comunque filettato."""
        arc = _make_arc(0, 0, 5, start_angle=45, end_angle=315)
        self.assertTrue(is_threaded_arc(arc))


# ---------------------------------------------------------------------------
# is_threaded_hole
# ---------------------------------------------------------------------------

class TestIsThreadedHole(unittest.TestCase):
    """
    Un foro filettato = CIRCLE piccolo + ARC concentrico più grande a ~270°.
    """

    def _make_threaded_pair(self, cx=0, cy=0, r_circle=3, r_arc=4):
        """Crea un cerchio piccolo e un arco filettato concentrico."""
        circle = _make_circle(cx, cy, r_circle)
        arc = _make_arc(cx, cy, r_arc, start_angle=0, end_angle=270)
        return circle, arc

    def test_001_coppia_concentrica_filettata(self):
        """Cerchio + arco a 270° concentrico → True."""
        circle, arc = self._make_threaded_pair()
        self.assertTrue(is_threaded_hole(circle, [arc]))

    def test_002_nessun_arco(self):
        """Cerchio senza archi → False."""
        circle = _make_circle(0, 0, 3)
        self.assertFalse(is_threaded_hole(circle, []))

    def test_003_arco_non_filettato(self):
        """Cerchio + arco a 180° (non filettato) → False."""
        circle = _make_circle(0, 0, 3)
        arc = _make_arc(0, 0, 4, start_angle=0, end_angle=180)
        self.assertFalse(is_threaded_hole(circle, [arc]))

    def test_004_arco_non_concentrico(self):
        """Cerchio + arco filettato ma lontano → False."""
        circle = _make_circle(0, 0, 3)
        arc = _make_arc(100, 100, 4, start_angle=0, end_angle=270)
        self.assertFalse(is_threaded_hole(circle, [arc]))

    def test_005_arco_piu_piccolo_del_cerchio(self):
        """Arco con raggio minore del cerchio → non conta come filettatura."""
        circle = _make_circle(0, 0, 5)
        arc = _make_arc(0, 0, 3, start_angle=0, end_angle=270)
        self.assertFalse(is_threaded_hole(circle, [arc]))

    def test_006_piu_archi_uno_solo_valido(self):
        """Lista con un arco non filettato e uno filettato → True."""
        circle = _make_circle(0, 0, 3)
        arc_bad = _make_arc(0, 0, 4, start_angle=0, end_angle=180)
        arc_ok  = _make_arc(0, 0, 4, start_angle=0, end_angle=270)
        self.assertTrue(is_threaded_hole(circle, [arc_bad, arc_ok]))


# ---------------------------------------------------------------------------
# is_countersink_outer
# ---------------------------------------------------------------------------

class TestIsCountersinkOuter(unittest.TestCase):
    """
    Il cerchio esterno di un countersink ha un cerchio più piccolo concentrico
    tra i suoi children.
    """

    def _children(self, *circles):
        """Costruisce la lista children nel formato (obj, poly, tipo)."""
        return [(c, None, 'CIRCLE') for c in circles]

    def test_001_cerchio_grande_con_piccolo_concentrico(self):
        """Cerchio grande + cerchio piccolo concentrico → True."""
        big   = _make_circle(0, 0, 10)
        small = _make_circle(0, 0, 5)
        self.assertTrue(is_countersink_outer(big, self._children(big, small)))

    def test_002_cerchio_senza_figli(self):
        """Nessun figlio → False."""
        big = _make_circle(0, 0, 10)
        self.assertFalse(is_countersink_outer(big, []))

    def test_003_cerchio_con_figlio_non_concentrico(self):
        """Figlio piccolo ma lontano → False."""
        big   = _make_circle(0, 0, 10)
        small = _make_circle(50, 50, 5)
        self.assertFalse(is_countersink_outer(big, self._children(big, small)))

    def test_004_cerchio_con_figlio_stesso_raggio(self):
        """Figlio con raggio uguale → non è il cerchio interno → False."""
        big  = _make_circle(0, 0, 10)
        same = _make_circle(0, 0, 10)
        self.assertFalse(is_countersink_outer(big, self._children(big, same)))

    def test_005_figlio_non_circle_ignorato(self):
        """Children non CIRCLE vengono ignorati → False."""
        big = _make_circle(0, 0, 10)
        children = [(big, None, 'LWPOLYLINE')]
        self.assertFalse(is_countersink_outer(big, children))

    def test_006_piu_figli_uno_solo_concentrico(self):
        """Più figli, solo uno concentrico e più piccolo → True."""
        big    = _make_circle(0, 0, 10)
        lontano = _make_circle(50, 50, 3)
        vicino  = _make_circle(0, 0, 4)
        self.assertTrue(is_countersink_outer(big, self._children(big, lontano, vicino)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
