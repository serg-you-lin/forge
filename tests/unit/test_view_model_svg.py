"""
test_view_model_svg.py — to_view_model() + to_svg()

Fixture tracciati nel repo:
    golden/example_4_polylines.dxf  — 4 parti, un foro ciascuna
    rect_with_special_layers.dxf    — 1 parte, pieghe + incisione
"""

import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import forge

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
MULTI_PART   = EXAMPLES / "golden" / "example_4_polylines.dxf"
SPECIAL      = EXAMPLES / "rect_with_special_layers.dxf"
MULTIFEATURE = EXAMPLES / "Multifeature.dxf"   # non tracciato — test extra se presente

SPECIAL_LM = {"Piega": "bending", "bend": "bending", "MARK": "engrave",
              "special": "engrave", "Filettati": "threaded_hole", "Svasati": "countersink"}


def _result(path, label_map=None):
    doc = forge.load_dxf(str(path), tolerance=0.5, label_map=label_map)
    return forge.heal_and_detect(doc, features="all")


class TestViewModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = _result(MULTI_PART)
        cls.vm = forge.to_view_model(cls.result)

    def test_json_serializable(self):
        json.dumps(self.vm)

    def test_top_level_shape(self):
        for key in ("source_file", "is_valid", "part_count", "bbox",
                    "parts", "palette", "trash", "annotations"):
            self.assertIn(key, self.vm)
        self.assertEqual(self.vm["part_count"], len(self.vm["parts"]))
        self.assertEqual(self.vm["part_count"], 4)
        self.assertEqual(len(self.vm["bbox"]), 4)

    def test_part_outer_geometry(self):
        part = self.vm["parts"][0]
        self.assertGreaterEqual(len(part["outer"]["points"]), 3)
        self.assertTrue(part["outer"]["closed"])
        self.assertEqual(part["outer"]["color"], "#00ff00")  # verde = outer

    def test_hole_carries_circle_metadata(self):
        holes = [h for p in self.vm["parts"] for h in p["holes"]]
        self.assertTrue(holes)
        h = holes[0]
        self.assertIn(h["hole_type"], ("plain", "countersink", "threaded"))
        self.assertGreater(h["diameter"], 0)
        self.assertEqual(len(h["center"]), 2)

    def test_every_point_is_xy_pair(self):
        for part in self.vm["parts"]:
            for pt in part["outer"]["points"]:
                self.assertEqual(len(pt), 2)
                self.assertIsInstance(pt[0], (int, float))

    def test_toggles_drop_sections(self):
        vm = forge.to_view_model(self.result, include_trash=False,
                                 include_annotations=False)
        self.assertNotIn("trash", vm)
        self.assertNotIn("annotations", vm)

    def test_bending_and_engrave_geometry(self):
        vm = forge.to_view_model(_result(SPECIAL, SPECIAL_LM))
        part = vm["parts"][0]
        self.assertTrue(part["bending_lines"])
        self.assertTrue(part["engrave_lines"])
        for bl in part["bending_lines"]:
            self.assertFalse(bl["closed"])
            self.assertGreaterEqual(len(bl["points"]), 2)

    def test_invalid_result_does_not_raise(self):
        empty = forge.ForgeResult(parts=[], is_valid=False, errors=["boom"])
        vm = forge.to_view_model(empty)
        self.assertFalse(vm["is_valid"])
        self.assertEqual(vm["parts"], [])
        self.assertIsNone(vm["bbox"])


class TestToSvg(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = _result(MULTI_PART)
        cls.svg = forge.to_svg(cls.result)

    def test_is_well_formed_xml(self):
        root = ET.fromstring(self.svg)
        self.assertTrue(root.tag.endswith("svg"))

    def test_has_viewbox_and_geometry(self):
        self.assertIn("viewBox=", self.svg)
        self.assertRegex(self.svg, r"<(polygon|polyline|circle)\b")

    def test_holes_render_as_circles_by_default(self):
        self.assertIn("<circle", self.svg)

    def test_holes_as_polygons_when_disabled(self):
        svg = forge.to_svg(self.result, holes_as_circles=False)
        self.assertEqual(svg.count("<circle"), 0)

    def test_one_group_per_part(self):
        self.assertEqual(len(re.findall(r'data-part="', self.svg)), 4)

    def test_transparent_background(self):
        svg = forge.to_svg(self.result, background=None)
        self.assertNotIn("<rect", svg.split("<g")[0])

    def test_empty_result_returns_valid_svg(self):
        empty = forge.ForgeResult(parts=[], is_valid=False)
        ET.fromstring(forge.to_svg(empty))


@unittest.skipUnless(MULTIFEATURE.exists(), "Multifeature.dxf non tracciato")
class TestRichExample(unittest.TestCase):
    """Copertura extra sul file con tutte le feature (solo in locale)."""

    def test_all_feature_types_render(self):
        lm = {"Filettati": "threaded_hole", "Svasati": "countersink",
              "Piega": "bending", "MARK": "engrave"}
        result = _result(MULTIFEATURE, lm)
        svg = forge.to_svg(result)
        ET.fromstring(svg)
        self.assertIn("#00ff00", svg)                       # outer
        self.assertTrue("#0000ff" in svg or "#00ffff" in svg)  # foro tipato
        vm = forge.to_view_model(result)
        p = vm["parts"][0]
        self.assertTrue(p["holes"] and p["bending_lines"] and p["engrave_lines"])


if __name__ == "__main__":
    unittest.main()
