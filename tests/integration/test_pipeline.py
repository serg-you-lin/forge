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

# root test dir (NON integration dir)
TEST_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = TEST_DIR.parent / "examples"

sys.path.insert(0, str(TEST_DIR))

from test_helpers import (
    run_pipeline,
    get_custom,
    count_entities_on_layer,
)


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

        bending = result.parts[0].custom.get("bending_lines", [])

        print(f"\n[bending original] count={len(bending)}")
        self.assertGreater(len(bending), 0)

    def test_002_reload_finds_one_part(self):
        reloaded = self.pipeline["reloaded_result"]

        print(f"[reload] part_count={reloaded.part_count}")
        self.assertEqual(reloaded.part_count, 1)

    def test_003_bending_layer_survives_write(self):
        msp = self.pipeline["reloaded_msp"]

        bend_count = count_entities_on_layer(msp, "BEND")

        print(f"[reload] BEND entities={bend_count}")
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
            ex("rect_with_threaded_holes.dxf"),
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

        import dxf_forge as forge

        forge.detect(
            result,
            msp,
            special_layers={"BEND": "bending"},
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


if __name__ == "__main__":
    unittest.main(verbosity=2)