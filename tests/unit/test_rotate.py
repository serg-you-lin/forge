"""
test_rotate.py
---------------
Test unitari per forge.tools.rotate (sperimentale, non ancora in __all__):
    structural_segments      ForgeResult -> list[segment], filtrato per ruolo
    longest_structural_segment  idem, ma solo il più lungo + il suo angolo
    rotate_cluster / rotate_result   ruotano un ForgeCluster/ForgeResult GIÀ
                                      sano — nessun heal() richiamato
    rotate_document           ruota un ForgeDocument grezzo (pre-heal)
    rotate_to_longest         orchestratore: allinea il più lungo, un solo
                               heal() (quello che il chiamante ha già fatto)

Usa forge.load_geometry (dict puri Python -> ForgeDocument) invece di un
file DXF: stesso pattern di test_geometry_loader.py, nessun I/O.
"""

import math
import unittest

import forge
from forge.tools.rotate import (
    structural_segments, longest_structural_segment,
    rotate_cluster, rotate_result, rotate_document, rotate_to_longest,
)
from forge.model.annotation import Note


def _tall_rect_with_diagonal():
    """
    Rettangolo 100x400 (outer verticale, lati lunghi = 400) più una linea
    interna diagonale (più corta e non outer) — stessa forma di
    tests/examples/try_for_rotation.dxf, costruita in memoria.
    """
    return forge.load_geometry([
        {"type": "polyline", "points": [(0, 0), (100, 0), (100, 400), (0, 400)], "closed": True},
        {"type": "line", "start": (0.3, 50), "end": (99.7, 350)},
    ])


def _rect_with_hole():
    """
    Rettangolo 100x50 con un foro (cerchio) — outer + un inner. Nessun
    `role` esplicito sul rettangolo di proposito: heal() assegna comunque
    `ContourRole.OUTER` al vero outer, e lasciare l'input senza ruolo evita
    che il foro interno erediti "outer" dal padre (vedi il commento in
    forge/tools/rotate.py su `hierarchy._make_inner`).
    """
    return forge.load_geometry([
        {"type": "polyline", "points": [(0, 0), (100, 0), (100, 50), (0, 50)], "closed": True},
        {"type": "circle", "center": (50, 25), "radius": 5},
    ])


class TestStructuralSegments(unittest.TestCase):

    def test_001_longest_defaults_to_outer_only_ignores_diagonal(self):
        result = forge.heal(_tall_rect_with_diagonal())
        seg, length, angle_deg = longest_structural_segment(result)
        self.assertIsNotNone(seg)
        self.assertAlmostEqual(length, 400.0, places=6)
        self.assertAlmostEqual(angle_deg, 90.0, places=6)

    def test_002_include_inners_adds_the_hole(self):
        result = forge.heal(_rect_with_hole())
        with_inners = structural_segments(result, include_inners=True)
        outer_only = structural_segments(result, include_inners=False)
        self.assertGreater(len(with_inners), len(outer_only))

    def test_003_no_clusters_returns_none(self):
        doc = forge.load_geometry([{"type": "line", "start": (0, 0), "end": (10, 0)}])
        result = forge.heal(doc)
        seg, length, angle_deg = longest_structural_segment(result)
        self.assertIsNone(seg)
        self.assertEqual(length, 0.0)
        self.assertIsNone(angle_deg)


class TestRotateCluster(unittest.TestCase):

    def test_001_rotates_outer_and_inner_keeps_parent_link(self):
        result = forge.heal(_rect_with_hole())
        cluster = result.clusters[0]
        rotated = rotate_cluster(cluster, math.pi / 2, origin=(0, 0))

        self.assertAlmostEqual(rotated.outer.polygon.bounds[0], -50.0, places=3)
        # l'inner ruotato deve ancora avere come parent il NUOVO outer, non il vecchio
        self.assertIs(rotated.inners[0].parent, rotated.outer)
        self.assertIsNot(rotated.inners[0].parent, cluster.outer)

    def test_002_does_not_mutate_original(self):
        result = forge.heal(_rect_with_hole())
        cluster = result.clusters[0]
        original_bounds = cluster.outer.polygon.bounds
        rotate_cluster(cluster, math.pi / 2, origin=(0, 0))
        self.assertEqual(cluster.outer.polygon.bounds, original_bounds)


class TestRotateResult(unittest.TestCase):

    def test_001_single_heal_matches_longest_outer_after_rotation(self):
        result = forge.heal(_tall_rect_with_diagonal())
        rotated = rotate_result(result, math.radians(-90), origin=(50, 200))
        _, length, angle_deg = longest_structural_segment(rotated)
        self.assertAlmostEqual(length, 400.0, places=6)
        self.assertAlmostEqual(angle_deg, 0.0, places=6)

    def test_002_trash_entities_rotate_too(self):
        result = forge.heal(_tall_rect_with_diagonal())
        trash_before = result.trash_entities[0].segments[0]
        rotated = rotate_result(result, math.radians(-90), origin=(50, 200))
        trash_after = rotated.trash_entities[0].segments[0]
        self.assertNotEqual(trash_before.start, trash_after.start)

    def test_003_warns_instead_of_silently_dropping_annotations(self):
        result = forge.heal(_tall_rect_with_diagonal())
        result.annotations.append(Note(position=(0, 0), text="X"))
        rotated = rotate_result(result, 0.1)
        self.assertTrue(any("annotazioni non ruotate" in w for w in rotated.warnings))

    def test_004_warns_when_detected_overlay_present(self):
        result = forge.heal(_tall_rect_with_diagonal())
        result.clusters[0].detected = {"bending_lines": []}
        rotated = rotate_result(result, 0.1)
        self.assertTrue(any("detect()" in w for w in rotated.warnings))


class TestRotateDocument(unittest.TestCase):

    def test_001_rotates_every_edge_around_origin(self):
        doc = forge.load_geometry([{"type": "line", "start": (1, 0), "end": (2, 0)}])
        rotated = rotate_document(doc, math.pi / 2, origin=(0, 0))
        seg = rotated.edges[0].segment
        self.assertAlmostEqual(seg.start[0], 0.0, places=6)
        self.assertAlmostEqual(seg.start[1], 1.0, places=6)


class TestRotateToLongest(unittest.TestCase):

    def test_001_aligns_longest_outer_to_horizontal_one_heal_only(self):
        result = forge.heal(_tall_rect_with_diagonal())
        rotated_result, applied_deg = rotate_to_longest(result)
        self.assertAlmostEqual(applied_deg, -90.0, places=6)

        _, length, angle_deg = longest_structural_segment(rotated_result)
        self.assertAlmostEqual(length, 400.0, places=6)
        self.assertAlmostEqual(angle_deg, 0.0, places=6)

    def test_002_no_outer_returns_result_unchanged(self):
        doc = forge.load_geometry([{"type": "line", "start": (0, 0), "end": (10, 0)}])
        result = forge.heal(doc)
        rotated_result, applied_deg = rotate_to_longest(result)
        self.assertIs(rotated_result, result)
        self.assertEqual(applied_deg, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
