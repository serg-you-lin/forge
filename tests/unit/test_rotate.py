"""
test_rotate.py
---------------
Test unitari per forge.tools.rotate (sperimentale, non ancora in __all__):
    longest_outer_segment   ForgeResult -> (segment, length, angle_deg) del
                             lato OUTER più lungo, filtrato per ruolo
    rotate_document         ForgeDocument -> ForgeDocument con ogni edge
                             ruotato
    rotate_to_longest_outer orchestratore: due passate di heal(), allinea
                             l'outer più lungo all'orizzontale

Usa forge.load_geometry (dict puri Python -> ForgeDocument) invece di un
file DXF: stesso pattern di test_geometry_loader.py, nessun I/O.
"""

import math
import unittest

import forge
from forge.tools.rotate import longest_outer_segment, rotate_document, rotate_to_longest_outer
from forge.model.annotation import Note


def _tall_rect_with_diagonal():
    """
    Rettangolo 100x400 (outer verticale, lati lunghi = 400) più una linea
    interna diagonale (più corta e non outer) — stessa forma di
    tests/examples/try_for_rotation.dxf, costruita in memoria.
    """
    return forge.load_geometry([
        {"type": "polyline", "points": [(0, 0), (100, 0), (100, 400), (0, 400)], "closed": True, "role": "outer"},
        {"type": "line", "start": (0.3, 50), "end": (99.7, 350)},
    ])


class TestLongestOuterSegment(unittest.TestCase):

    def test_001_picks_the_longer_outer_side_not_the_diagonal(self):
        doc = _tall_rect_with_diagonal()
        result = forge.heal(doc)
        seg, length, angle_deg = longest_outer_segment(result)
        self.assertIsNotNone(seg)
        self.assertAlmostEqual(length, 400.0, places=6)
        self.assertAlmostEqual(angle_deg, 90.0, places=6)

    def test_002_no_clusters_returns_none(self):
        doc = forge.load_geometry([{"type": "line", "start": (0, 0), "end": (10, 0)}])
        result = forge.heal(doc)
        seg, length, angle_deg = longest_outer_segment(result)
        self.assertIsNone(seg)
        self.assertEqual(length, 0.0)
        self.assertIsNone(angle_deg)


class TestRotateDocument(unittest.TestCase):

    def test_001_rotates_every_edge_around_origin(self):
        doc = forge.load_geometry([
            {"type": "line", "start": (1, 0), "end": (2, 0)},
        ])
        rotated = rotate_document(doc, math.pi / 2, origin=(0, 0))
        seg = rotated.edges[0].segment
        self.assertAlmostEqual(seg.start[0], 0.0, places=6)
        self.assertAlmostEqual(seg.start[1], 1.0, places=6)
        self.assertAlmostEqual(seg.end[0], 0.0, places=6)
        self.assertAlmostEqual(seg.end[1], 2.0, places=6)
        # edge.start/end (arrotondati) devono seguire lo stesso segmento
        self.assertAlmostEqual(rotated.edges[0].start[0], 0.0, places=2)
        self.assertAlmostEqual(rotated.edges[0].start[1], 1.0, places=2)

    def test_002_warns_instead_of_silently_dropping_annotations(self):
        doc = forge.load_geometry([{"type": "line", "start": (0, 0), "end": (1, 0)}])
        note = Note(position=(0, 0), text="X")
        doc.annotations.append(note)
        rotated = rotate_document(doc, 0.1)
        self.assertTrue(any("annotazioni non ruotate" in w for w in rotated.warnings))


class TestRotateToLongestOuter(unittest.TestCase):

    def test_001_aligns_longest_outer_to_horizontal(self):
        doc = _tall_rect_with_diagonal()
        rotated_doc, applied_deg = rotate_to_longest_outer(doc)
        self.assertAlmostEqual(applied_deg, -90.0, places=6)

        result = forge.heal(rotated_doc)
        _, length, angle_deg = longest_outer_segment(result)
        self.assertAlmostEqual(length, 400.0, places=6)
        self.assertAlmostEqual(angle_deg, 0.0, places=6)

    def test_002_no_outer_returns_document_unchanged(self):
        doc = forge.load_geometry([{"type": "line", "start": (0, 0), "end": (10, 0)}])
        rotated_doc, applied_deg = rotate_to_longest_outer(doc)
        self.assertIs(rotated_doc, doc)
        self.assertEqual(applied_deg, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
