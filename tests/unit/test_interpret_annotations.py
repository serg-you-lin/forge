"""
tests/unit/test_interpret_annotations.py
----------------------------------------
`interpret_annotations()`: assegna `part_ref` (indice della parte contenitrice)
alle annotazioni del modello. Fase separata e opzionale della pipeline.
"""

import unittest

from shapely.geometry import Polygon

from forge.model.part import ForgePart, ForgeContour
from forge.model.result import ForgeResult
from forge.model.role import ContourRole
from forge.model.annotation import Note
from forge.pipeline.interpret import interpret_annotations


def _part(x0, y0, x1, y1):
    poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return ForgePart(outer=ForgeContour(polygon=poly, role=ContourRole.OUTER))


def _result(*parts, annotations=()):
    return ForgeResult(parts=list(parts), annotations=list(annotations))


class TestInterpretAnnotations(unittest.TestCase):

    def test_containment_assigns_part_index(self):
        res = _result(
            _part(0, 0, 100, 100),
            _part(200, 0, 300, 100),
            annotations=[
                Note(position=(50, 50), text="dentro parte 0"),
                Note(position=(250, 50), text="dentro parte 1"),
            ],
        )
        interpret_annotations(res)
        self.assertEqual(res.annotations[0].part_ref, 0)
        self.assertEqual(res.annotations[1].part_ref, 1)

    def test_outside_all_parts_stays_none(self):
        res = _result(
            _part(0, 0, 100, 100),
            annotations=[Note(position=(500, 500), text="cartiglio")],
        )
        interpret_annotations(res)
        self.assertIsNone(res.annotations[0].part_ref)

    def test_snap_distance_assigns_near_part(self):
        res = _result(
            _part(0, 0, 100, 100),
            annotations=[Note(position=(105, 50), text="callout appena fuori")],
        )
        interpret_annotations(res, snap_distance=0.0)
        self.assertIsNone(res.annotations[0].part_ref)

        interpret_annotations(res, snap_distance=10.0)
        self.assertEqual(res.annotations[0].part_ref, 0)

    def test_first_covering_part_wins_on_overlap(self):
        res = _result(
            _part(0, 0, 100, 100),
            _part(50, 50, 150, 150),   # sovrapposta alla prima
            annotations=[Note(position=(75, 75), text="nella zona comune")],
        )
        interpret_annotations(res)
        self.assertEqual(res.annotations[0].part_ref, 0)

    def test_no_parts_is_noop(self):
        res = _result(annotations=[Note(position=(1, 1), text="x")])
        interpret_annotations(res)
        self.assertIsNone(res.annotations[0].part_ref)


if __name__ == "__main__":
    unittest.main()
