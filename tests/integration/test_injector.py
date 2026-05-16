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

import dxf_forge as forge
from dxf_forge.rules.layers import LAYER_BENDING, LAYER_ENGRAVE

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def load(name):
    return ezdxf.readfile(str(EXAMPLES_DIR / name))


# ---------------------------------------------------------------------------
# Helpers condivisi
# ---------------------------------------------------------------------------


def _heal_and_inject(dxf_name, special_layers=None, data_injector=None, interpreter=None):
    """Carica il DXF, esegue heal + inject, restituisce (msp, result)."""
    doc = load(dxf_name)
    msp = doc.modelspace()
    result = forge.heal(
        msp,
        write_to_msp=True,
        special_layers=special_layers or {},
    )
    if interpreter is not None or special_layers:
        forge.classify(result, msp, interpreter=interpreter)
    forge.inject(msp, result, data_injector=data_injector)
    return msp, result

# ---------------------------------------------------------------------------
# Caso base: result senza parts — inject non deve crashare
# ---------------------------------------------------------------------------

class TestInjectEmptyResult(unittest.TestCase):

    def test_001_no_parts_no_crash(self):
        """inject() su un result vuoto non deve sollevare eccezioni."""
        doc = ezdxf.new()
        msp = doc.modelspace()
        result = forge.heal(msp, write_to_msp=False)
        # non deve esplodere
        forge.inject(msp, result)
        self.assertEqual(result.parts, [])


# ---------------------------------------------------------------------------
# Bending lines
# ---------------------------------------------------------------------------

class TestInjectBendingLines(unittest.TestCase):

    def setUp(self):
        _, self.result = _heal_and_inject(
            "rect_with_special_layers.dxf",
            special_layers={"BEND": "bending", "MARK": "engrave"},
        )

    def test_001_bending_lines_present_in_custom(self):
        """bending_lines deve essere presente in part.custom."""
        custom = self.result.parts[0].custom
        self.assertIn("bending_lines", custom)

    def test_002_bending_lines_count(self):
        """Il DXF ha 2 linee di piega collineari → bending_lines == 2."""
        custom = self.result.parts[0].custom
        self.assertEqual(custom["bending_lines"], 2)

    def test_003_bending_lines_is_int(self):
        """bending_lines deve essere un intero (conteggio gruppi)."""
        val = self.result.parts[0].custom["bending_lines"]
        self.assertIsInstance(val, int)


# ---------------------------------------------------------------------------
# Engrave length
# ---------------------------------------------------------------------------

class TestInjectEngraveLength(unittest.TestCase):

    def setUp(self):
        _, self.result = _heal_and_inject(
            "rect_with_special_layers.dxf",
            special_layers={"BEND": "bending", "MARK": "engrave"},
        )

    def test_001_total_engrave_length_present(self):
        custom = self.result.parts[0].custom
        self.assertIn("total_engrave_length", custom)

    def test_002_total_engrave_length_value(self):
        """LINE diagonale (50,0)→(150,100): √(100²+100²) ≈ 141.42 mm."""
        length = self.result.parts[0].custom["total_engrave_length"]
        self.assertAlmostEqual(length, 141.42, delta=0.1)

    def test_003_total_engrave_length_is_float(self):
        val = self.result.parts[0].custom["total_engrave_length"]
        self.assertIsInstance(val, float)

    def test_004_engrave_length_non_negative(self):
        val = self.result.parts[0].custom["total_engrave_length"]
        self.assertGreaterEqual(val, 0.0)


# ---------------------------------------------------------------------------
# Countersink
# ---------------------------------------------------------------------------

class TestInjectCountersink(unittest.TestCase):

    def setUp(self):
        from dxf_forge.rules.interpreter import GeometricInterpreter
        _, self.result = _heal_and_inject(
            "rect_with_countersink.dxf",
            interpreter=GeometricInterpreter(),
        )

    def test_001_countersink_count_present(self):
        """countersink_count deve comparire in part.custom."""
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
            special_layers={"THREADED": "threaded_hole"},
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
        self.doc = load("rect_with_special_layers.dxf")
        self.msp = self.doc.modelspace()
        self.result = forge.heal(
            self.msp,
            write_to_msp=True,
            special_layers={"BEND": "bending", "MARK": "engrave"},
        )

    def test_001_data_injector_viene_chiamato(self):
        """Il data_injector deve essere chiamato e il risultato finire in custom."""
        forge.inject(
            self.msp, self.result,
            data_injector=lambda part, testi: {"materiale": "acciaio"},
        )
        self.assertEqual(self.result.parts[0].custom["materiale"], "acciaio")

    def test_002_data_injector_riceve_lista_testi(self):
        """Il data_injector riceve una lista come secondo argomento."""
        received = {}
        def spy(part, testi):
            received["testi"] = testi
            return {}
        forge.inject(self.msp, self.result, data_injector=spy)
        self.assertIn("testi", received)
        self.assertIsInstance(received["testi"], list)

    def test_003_data_injector_none_non_crasha(self):
        """Senza data_injector non devono esserci eccezioni."""
        forge.inject(self.msp, self.result, data_injector=None)
        # nessuna eccezione = test passa

    def test_004_data_injector_eccezione_produce_warning(self):
        """Se il data_injector solleva un'eccezione, deve finire in result.warnings."""
        def bad_injector(part, testi):
            raise ValueError("errore simulato")

        forge.inject(self.msp, self.result, data_injector=bad_injector)
        warnings_text = " ".join(self.result.warnings)
        self.assertIn("data_injector", warnings_text)

    def test_005_data_injector_restituisce_none_non_crasha(self):
        """Se il data_injector restituisce None, inject() non deve crashare."""
        forge.inject(
            self.msp, self.result,
            data_injector=lambda part, testi: None,
        )
        # nessuna eccezione = test passa

    def test_006_data_injector_merge_con_forge_metrics(self):
        """I dati del data_injector si sommano alle metriche forge in custom."""
        forge.inject(
            self.msp, self.result,
            data_injector=lambda part, testi: {"spessore": 3.0},
        )
        custom = self.result.parts[0].custom
        # metriche forge presenti
        self.assertIn("bending_lines", custom)
        # dati injector presenti
        self.assertIn("spessore", custom)


# ---------------------------------------------------------------------------
# Isolamento tra parts (multi-part)
# ---------------------------------------------------------------------------

class TestInjectMultiPart(unittest.TestCase):
    """
    Verifica che le metriche di un part non contaminino quelle di un altro.
    Usa due rettangoli separati nello stesso DXF — se non hai questo fixture,
    aggiungilo a generate_examples.py come 'two_rects_with_bend.dxf'.

    Fixture da aggiungere:
        def generate_two_rects_with_bend():
            doc = ezdxf.new()
            msp = doc.modelspace()
            # rect A: 200x100 in (0,0)
            msp.add_lwpolyline([(0,0),(200,0),(200,100),(0,100),(0,0)], close=True)
            # rect B: 200x100 in (300,0) — ben separato
            msp.add_lwpolyline([(300,0),(500,0),(500,100),(300,100),(300,0)], close=True)
            # 1 linea BEND dentro A
            msp.add_line((10,50),(190,50), dxfattribs={"layer": "BEND"})
            # nessuna linea BEND dentro B
            doc.saveas(EXAMPLES_DIR / "two_rects_with_bend.dxf")
    """

    def setUp(self):
        _, self.result = _heal_and_inject(
            "two_rects_with_bend.dxf",
            special_layers={"BEND": "bending"},
        )

    def test_001_two_parts_found(self):
        self.assertEqual(self.result.part_count, 2)

    def test_002_only_one_part_has_bending(self):
        """Solo il part che contiene la linea BEND deve avere bending_lines > 0."""
        bending_counts = [
            p.custom.get("bending_lines", 0)
            for p in self.result.parts
        ]
        self.assertEqual(sorted(bending_counts), [0, 1])

    def test_003_other_part_has_no_bending_key_or_zero(self):
        """Il part senza BEND non deve avere bending_lines contaminato dall'altro."""
        for part in self.result.parts:
            count = part.custom.get("bending_lines", 0)
            self.assertGreaterEqual(count, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)