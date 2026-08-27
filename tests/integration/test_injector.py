"""
test_injector.py
----------------
Test Suite per dxf_forge.injector

Prerequisiti DXF da aggiungere a generate_examples.py:
    - rect_with_special_layers.dxf  (già esistente per test_healer)
    - rect_with_countersink.dxf     (già esistente per test_healer)
    - rect_with_threaded_holes.dxf  (NUOVO — rettangolo con N cerchi su layer "THREADED")

Fixture NUOVO da aggiungere a generate_examples.py:
─────────────────────────────────────────────────────
    def generate_rect_with_threaded_holes():
        doc = ezdxf.new()
        msp = doc.modelspace()
        # outer: rettangolo 200x100
        msp.add_lwpolyline([(0,0),(200,0),(200,100),(0,100),(0,0)], close=True)
        # 3 cerchi piccoli su layer "THREADED" (diametro 5, sotto HOLE_DIAMETER_THRESHOLD)
        for cx in [40, 100, 160]:
            msp.add_circle((cx, 50), radius=2.5, dxfattribs={"layer": "THREADED"})
        doc.saveas(EXAMPLES_DIR / "rect_with_threaded_holes.dxf")

Poi lancia:
    python -m pytest tests/test_injector.py -v
    oppure
    python -m unittest tests/test_injector.py -v
"""

import unittest
from pathlib import Path
import sys
import ezdxf

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge.adapters.dxf.layers import LAYER_BENDING, LAYER_ENGRAVE

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def load(name):
    return ezdxf.readfile(str(EXAMPLES_DIR / name))


# ---------------------------------------------------------------------------
# Helpers condivisi
# ---------------------------------------------------------------------------


def _heal_and_inject(dxf_name, label_map=None, data_injector=None, interpreter=None):
    doc = forge.document_from_msp(
        load(dxf_name).modelspace(), label_map=label_map or {}
    )
    result = forge.heal(doc)
    forge.detect(
        result
    )
    forge.inject(result, data_injector=data_injector)
    return doc, result

# ---------------------------------------------------------------------------
# Caso base: result senza parts — inject non deve crashare
# ---------------------------------------------------------------------------

class TestInjectEmptyResult(unittest.TestCase):

    def test_001_no_parts_no_crash(self):
        """inject() su un result vuoto non deve sollevare eccezioni."""
        doc = forge.document_from_msp(ezdxf.new().modelspace())
        result = forge.heal(doc)
        # non deve esplodere
        forge.inject(result)
        self.assertEqual(result.parts, [])


# ---------------------------------------------------------------------------
# Bending lines
# ---------------------------------------------------------------------------

class TestInjectBendingLines(unittest.TestCase):

    def setUp(self):
        _, self.result = _heal_and_inject(
            "rect_with_special_layers.dxf",
            label_map={"BEND": "bending", "MARK": "engrave"},
        )

    def test_001_part_exists(self):
        self.assertTrue(self.result.parts)

    def test_002_bending_metrics_are_optional(self):
        custom = self.result.parts[0].custom
        self.assertIsInstance(custom, dict)

    def test_003_data_injector_can_add_bending_metric(self):
        def add_metric(part, testi):
            return {"bending_lines": 2}

        forge.inject(self.result, data_injector=add_metric)
        self.assertEqual(self.result.parts[0].custom["bending_lines"], 2)


# ---------------------------------------------------------------------------
# Engrave length
# ---------------------------------------------------------------------------

class TestInjectEngraveLength(unittest.TestCase):

    def setUp(self):
        _, self.result = _heal_and_inject(
            "rect_with_special_layers.dxf",
            label_map={"BEND": "bending", "MARK": "engrave"},
        )

    def test_001_engrave_metric_is_optional(self):
        custom = self.result.parts[0].custom
        self.assertIsInstance(custom, dict)

    def test_002_data_injector_can_add_engrave_metric(self):
        def add_metric(part, testi):
            return {"total_engrave_length": 141.42}

        forge.inject(self.result, data_injector=add_metric)
        self.assertAlmostEqual(self.result.parts[0].custom["total_engrave_length"], 141.42, delta=0.1)

    def test_003_engrave_metric_is_float(self):
        def add_metric(part, testi):
            return {"total_engrave_length": 141.42}

        forge.inject(self.result, data_injector=add_metric)
        self.assertIsInstance(self.result.parts[0].custom["total_engrave_length"], float)


# ---------------------------------------------------------------------------
# Countersink
# ---------------------------------------------------------------------------

class TestInjectCountersink(unittest.TestCase):

    def setUp(self):
        _, self.result = _heal_and_inject("rect_with_countersink.dxf")

    def test_001_countersink_count_present(self):
        """countersink_count deve comparire in part.custom quando il foro è presente."""
        custom = self.result.parts[0].custom
        self.assertIn("countersink_count", custom)

    def test_002_countersink_count_value(self):
        """Il DXF ha 1 coppia concentrica → countersink_count == 1."""
        self.assertEqual(self.result.parts[0].custom["countersink_count"], 1)

    def test_003_countersink_count_is_int(self):
        val = self.result.parts[0].custom["countersink_count"]
        self.assertIsInstance(val, int)


# ---------------------------------------------------------------------------
# Threaded holes
# ---------------------------------------------------------------------------

class TestInjectThreadedHoles(unittest.TestCase):
    """
    Richiede fixture: rect_with_threaded_holes.dxf
    Vedi istruzioni in cima al file per generate_examples.py.
    """

    def setUp(self):
        _, self.result = _heal_and_inject(
            "rect_with_threaded_holes.dxf",
            label_map={"THREADED": "threaded_hole"},
        )

    def test_001_threaded_holes_count_present(self):
        custom = self.result.parts[0].custom
        self.assertIn("threaded_holes_count", custom)

    def test_002_threaded_holes_count_value(self):
        """Il DXF ha 3 cerchi su layer THREADED → threaded_holes_count == 3."""
        self.assertEqual(self.result.parts[0].custom["threaded_holes_count"], 3)

    def test_003_threaded_holes_count_is_int(self):
        val = self.result.parts[0].custom["threaded_holes_count"]
        self.assertIsInstance(val, int)


# ---------------------------------------------------------------------------
# Data injector esterno
# ---------------------------------------------------------------------------

class TestInjectDataInjector(unittest.TestCase):

    def setUp(self):
        self.doc = forge.document_from_msp(
            load("rect_with_special_layers.dxf").modelspace(),
            label_map={"BEND": "bending", "MARK": "engrave"},
        )
        self.result = forge.heal(self.doc)
        forge.detect(self.result)

    def test_001_data_injector_viene_chiamato(self):
        """Il data_injector deve essere chiamato e il risultato finire in custom."""
        forge.inject(
            self.result,
            data_injector=lambda part, testi: {"materiale": "acciaio"},
        )
        self.assertEqual(self.result.parts[0].custom["materiale"], "acciaio")

    def test_002_data_injector_riceve_lista_testi(self):
        """Il data_injector riceve una lista come secondo argomento."""
        received = {}
        def spy(part, testi):
            received["testi"] = testi
            return {}
        forge.inject(self.result, data_injector=spy)
        self.assertIn("testi", received)
        self.assertIsInstance(received["testi"], list)

    def test_003_data_injector_none_non_crasha(self):
        """Senza data_injector non devono esserci eccezioni."""
        forge.inject(self.result, data_injector=None)
        # nessuna eccezione = test passa

    def test_004_data_injector_eccezione_produce_warning(self):
        """Se il data_injector solleva un'eccezione, deve finire in result.warnings."""
        def bad_injector(part, testi):
            raise ValueError("errore simulato")

        forge.inject(self.result, data_injector=bad_injector)
        warnings_text = " ".join(self.result.warnings)
        self.assertIn("data_injector", warnings_text)

    def test_005_data_injector_restituisce_none_non_crasha(self):
        """Se il data_injector restituisce None, inject() non deve crashare."""
        forge.inject(
            self.result,
            data_injector=lambda part, testi: None,
        )
        # nessuna eccezione = test passa

    def test_006_data_injector_merge_con_forge_metrics(self):
        """Il data_injector può aggiungere dati custom senza interferire con il resto del custom."""
        forge.inject(
            self.result,
            data_injector=lambda part, testi: {"spessore": 3.0},
        )
        custom = self.result.parts[0].custom
        self.assertIn("spessore", custom)
        self.assertIsInstance(custom, dict)


# ---------------------------------------------------------------------------
# Isolamento tra parts (multi-part)
# ---------------------------------------------------------------------------

class TestInjectMultiPart(unittest.TestCase):
    """Verifica che il data injector applichi i valori in modo isolato per ogni part."""

    def setUp(self):
        _, self.result = _heal_and_inject(
            "two_rects_with_bend.dxf",
            label_map={"BEND": "bending"},
        )

    def test_001_two_parts_found(self):
        self.assertEqual(self.result.part_count, 2)

    def test_002_data_injector_can_target_each_part(self):
        def add_metric(part, testi):
            return {"marker": part.outer.polygon.area}

        forge.inject(self.result, data_injector=add_metric)
        areas = [part.custom["marker"] for part in self.result.parts]
        self.assertEqual(len(areas), 2)
        self.assertTrue(all(isinstance(a, float) for a in areas))

    def test_003_empty_custom_is_allowed(self):
        for part in self.result.parts:
            self.assertIsInstance(part.custom, dict)


if __name__ == "__main__":
    unittest.main(verbosity=2)