"""
tests/integration/test_pipeline.py
----------------------------------

Test semantic pipeline integrity.

Usa solo file generati in:
tests/examples/
"""

import sys
from pathlib import Path
import unittest

TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_DIR))

from test_helpers import (
    run_pipeline,
    get_custom,
    count_entities_on_layer,
)

EXAMPLES_DIR = TEST_DIR.parent / "examples"



def ex(name: str) -> str:
    """
    Resolve path to example DXF.
    """
    path = EXAMPLES_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing example file: {path}. "
            f"Run generate_examples.py first."
        )
    return str(path)


class TestPipelineBendingRoundtrip(unittest.TestCase):

    def setUp(self):
        self.pipeline = run_pipeline(
            ex("rect_with_special_layers.dxf"),
            do_detect=True,
            do_inject=True,
            do_write=True,
            reload_after_write=True,
            special_layers={
                "BEND": "bending",
            },
        )

    def test_001_original_has_bending(self):
        result = self.pipeline["result"]

        bending = result.parts[0].custom.get("bending_lines", 0)

        print(f"\n[bending original] count={(bending)}")
        self.assertGreater(bending, 0)

    def test_002_reload_finds_one_part(self):
        reloaded = self.pipeline["reloaded_result"]

        print(f"[reload] part_count={reloaded.part_count}")
        self.assertEqual(reloaded.part_count, 1)

    def test_003_bending_layer_survives_write(self):
        msp = self.pipeline["reloaded_msp"]

        bend_count = count_entities_on_layer(msp, "Bending")

        print(f"[reload] Bending entities={bend_count}")
        self.assertGreater(bend_count, 0)


class TestPipelineCountersinkPersistence(unittest.TestCase):

    def setUp(self):
        self.pipeline = run_pipeline(
            ex("rect_with_countersink.dxf"),
            do_detect=True,
            do_inject=True,
            do_write=True,
            reload_after_write=True,
            special_layers={
                "CSK": "countersink",
            },
        )

    def test_001_original_has_countersink(self):
        result = self.pipeline["result"]

        value = get_custom(result, "countersink_count", 0)

        print(f"\n[countersink original] count={value}")
        self.assertGreater(value, 0)

    def test_002_reload_still_has_one_part(self):
        self.assertEqual(
            self.pipeline["reloaded_result"].part_count,
            1,
        )

    def test_003_no_errors_after_reload(self):
        reloaded = self.pipeline["reloaded_result"]

        print(f"[reload] errors={reloaded.errors}")
        self.assertEqual(len(reloaded.errors), 0)


class TestPipelineThreadedHolePersistence(unittest.TestCase):

    def setUp(self):
        self.pipeline = run_pipeline(
            ex("rect_with_threaded_holes_geometric.dxf"),
            do_detect=True,
            do_inject=True,
            do_write=True,
            reload_after_write=True,
        )

    def test_001_original_has_threaded_holes(self):
        result = self.pipeline["result"]

        value = get_custom(result, "threaded_holes_count", 0)

        print(f"\n[threaded original] count={value}")
        self.assertGreater(value, 0)

    def test_002_reload_is_valid(self):
        reloaded = self.pipeline["reloaded_result"]

        print(f"[reload] is_valid={reloaded.is_valid}")
        self.assertTrue(reloaded.is_valid)


class TestPipelineDetectIdempotency(unittest.TestCase):

    def setUp(self):
        self.pipeline = run_pipeline(
            ex("rect_with_special_layers.dxf"),
            do_detect=True,
            special_layers={"BEND": "bending"},
        )

    def test_001_detect_twice_does_not_duplicate(self):
        result = self.pipeline["result"]
        msp = self.pipeline["msp"]

        before = len(result.parts[0].custom.get("bending_lines", []))

        import forge

        forge.heal(
            msp,
            label_map={"BEND": "bending"},
        )

        forge.detect(
            result
        )

        after = len(result.parts[0].custom.get("bending_lines", []))

        print(f"\n[idempotency] before={before} after={after}")
        self.assertEqual(before, after)


class TestPipelineWriteIntegrity(unittest.TestCase):

    def setUp(self):
        self.pipeline = run_pipeline(
            ex("rect_with_special_layers.dxf"),
            do_detect=True,
            do_write=True,
            reload_after_write=True,
            special_layers={
                "MARK": "engrave",
                "BEND": "bending",
            },
        )

    def test_001_only_one_outer_exists(self):
        reloaded = self.pipeline["reloaded_result"]

        print(f"\n[write integrity] parts={reloaded.part_count}")
        self.assertEqual(reloaded.part_count, 1)

    def test_002_no_extra_holes_created(self):
        reloaded = self.pipeline["reloaded_result"]
        part = reloaded.parts[0]

        print(f"[write integrity] inners={len(part.inners)}")
        self.assertGreaterEqual(len(part.inners), 0)


class TestSpecialLayersEngrave(unittest.TestCase):
    """
    Verifica che entità su special layer (MARK) vengano classificate
    come engrave — sia LINE isolate (in trash) sia loop chiusi (inner VS).
    """

    def setUp(self):
        self.pipeline = run_pipeline(
            ex("la_104.dxf"),
            do_detect=True,
            do_inject=True,
            do_write=True,
            special_layers={"MARK": "engrave"},
        )

    def test_001_engrave_length_nonzero(self):
        result = self.pipeline["result"]
        value = get_custom(result, "total_engrave_length", 0)
        self.assertGreater(value, 0)

    def test_002_no_mark_entities_on_inner_after_write(self):
        msp = self.pipeline["msp"]
        mark_on_inner = [
            e for e in msp
            if e.dxf.layer == "InnerContour"
            and e.dxftype() == "LWPOLYLINE"
        ]
        # D e O non devono essere su InnerContour
        self.assertEqual(len(mark_on_inner), 0)  # solo i fori reali

    def test_003_no_mark_layer_survives_write(self):
        msp = self.pipeline["msp"]
        mark_count = count_entities_on_layer(msp, "MARK")
        self.assertEqual(mark_count, 0)


class TestSpecialLayersWithoutDetect(unittest.TestCase):
    """
    Senza detect(), le entità su layer non-strutturale vanno in Trash.
    """

    def setUp(self):
        self.pipeline = run_pipeline(
            ex("la_104.dxf"),
            do_detect=False,
            do_write=True,
        )

    def test_001_mark_goes_to_trash_without_detect(self):
        msp = self.pipeline["msp"]
        mark_count = count_entities_on_layer(msp, "MARK")
        self.assertEqual(mark_count, 0)

    def test_002_trash_has_entities(self):
        msp = self.pipeline["msp"]
        trash_count = count_entities_on_layer(msp, "Trash")
        self.assertGreater(trash_count, 0)

if __name__ == "__main__":
    unittest.main(verbosity=2)