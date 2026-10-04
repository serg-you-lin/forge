"""
test_view_model_svg.py — to_view_model() + to_svg()

Fixture tracciati nel repo:
    golden/example_4_polylines.dxf  — 4 parti, un cerchio interno ciascuna

L'overlay (MAP.md D90) si prova con un elemento di prova attaccato a mano:
forge lo disegna dal suo ruolo e dalla sua geometria, senza sapere cos'è.
Fori, pieghe, incisioni veri: snapbend tests/flat/test_view_model_svg.py.
"""

import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import forge
from forge.model import DetectedFeatures

EXAMPLES = Path(__file__).resolve().parents[1] / "data"
MULTI_PART   = EXAMPLES / "golden" / "example_4_polylines.dxf"


class _Mark:
    """Elemento di prova dell'overlay: un cerchio interno riletto da un consumatore."""
    role = "my_circle"

    def __init__(self, contour, center, diameter):
        self.polygon = contour.polygon
        self.segments = contour.segments
        self._center, self._diameter = center, diameter

    def to_dict(self):
        return {"center": self._center, "diameter": self._diameter, "kind": "test"}


def _result(path):
    doc = forge.load_dxf(str(path), tolerance=0.5)
    result = forge.heal(doc)
    for cluster in result.clusters:
        marks = []
        for inner in cluster.inners:
            c = inner.polygon.centroid
            marks.append(_Mark(inner, (c.x, c.y), 2 * (inner.polygon.area / 3.141592653589793) ** 0.5))
        cluster.inners = []
        cluster.detected = DetectedFeatures()
        cluster.detected.attach("my_circles", marks)
    return result


class TestViewModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = _result(MULTI_PART)
        cls.vm = forge.to_view_model(cls.result)

    def test_json_serializable(self):
        json.dumps(self.vm)

    def test_top_level_shape(self):
        for key in ("source_file", "is_valid", "cluster_count", "bbox",
                    "clusters", "palette", "trash", "annotations"):
            self.assertIn(key, self.vm)
        self.assertEqual(self.vm["cluster_count"], len(self.vm["clusters"]))
        self.assertEqual(self.vm["cluster_count"], 4)
        self.assertEqual(len(self.vm["bbox"]), 4)

    def test_part_outer_geometry(self):
        cluster = self.vm["clusters"][0]
        self.assertGreaterEqual(len(cluster["outer"]["points"]), 3)
        self.assertTrue(cluster["outer"]["closed"])
        self.assertEqual(cluster["outer"]["color"], "#00ff00")  # verde = outer

    def test_overlay_entry_carries_to_dict_fields(self):
        marks = [m for p in self.vm["clusters"] for m in p["features"]["my_circles"]]
        self.assertTrue(marks)
        m = marks[0]
        self.assertEqual(m["role"], "my_circle")
        self.assertEqual(m["kind"], "test")
        self.assertTrue(m["closed"])
        self.assertGreater(m["diameter"], 0)
        self.assertEqual(len(m["center"]), 2)

    def test_every_point_is_xy_pair(self):
        for cluster in self.vm["clusters"]:
            for pt in cluster["outer"]["points"]:
                self.assertEqual(len(pt), 2)
                self.assertIsInstance(pt[0], (int, float))

    def test_toggles_drop_sections(self):
        vm = forge.to_view_model(self.result, include_trash=False,
                                 include_annotations=False)
        self.assertNotIn("trash", vm)
        self.assertNotIn("annotations", vm)

    def test_invalid_result_does_not_raise(self):
        empty = forge.ForgeResult(clusters=[], is_valid=False, errors=["boom"])
        vm = forge.to_view_model(empty)
        self.assertFalse(vm["is_valid"])
        self.assertEqual(vm["clusters"], [])
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

    def test_overlay_circles_render_as_circles_by_default(self):
        self.assertIn("<circle", self.svg)

    def test_overlay_circles_as_polygons_when_disabled(self):
        svg = forge.to_svg(self.result, true_circles=False)
        self.assertEqual(svg.count("<circle"), 0)

    def test_one_group_per_part(self):
        self.assertEqual(len(re.findall(r'data-cluster="', self.svg)), 4)

    def test_transparent_background(self):
        svg = forge.to_svg(self.result, background=None)
        self.assertNotIn("<rect", svg.split("<g")[0])

    def test_empty_result_returns_valid_svg(self):
        empty = forge.ForgeResult(clusters=[], is_valid=False)
        ET.fromstring(forge.to_svg(empty))


if __name__ == "__main__":
    unittest.main()
