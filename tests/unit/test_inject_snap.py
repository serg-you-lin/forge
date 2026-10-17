"""
tests/unit/test_inject_snap.py
------------------------------
`inject(snap_distance=...)`: un testo appena fuori dal contorno esterno arriva
lo stesso al `data_injector` della parte più vicina, stessa regola di
`anchor_annotations`.
"""

import unittest

from shapely.geometry import Polygon

import topo
from topo.model.annotation import Note
from topo.model.cluster import Cluster
from topo.model.contour import Contour
from topo.model.result import Result
from topo.model.role import ContourRole


def _part(x0, y0, x1, y1):
    poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return Cluster(outer=Contour(polygon=poly, role=ContourRole.OUTER))


def _result(*clusters, annotations=()):
    return Result(clusters=list(clusters), annotations=list(annotations))


def _collect(cluster, testi):
    return {"testi": list(testi)}


class TestInjectSnapDistance(unittest.TestCase):

    def test_default_keeps_strict_containment(self):
        res = _result(_part(0, 0, 100, 100),
                      annotations=[Note(position=(105, 50), text="materiale sp.3")])
        topo.inject(res, data_injector=_collect)
        self.assertEqual(res.clusters[0].custom["testi"], [])

    def test_text_just_outside_goes_to_part(self):
        res = _result(_part(0, 0, 100, 100),
                      annotations=[Note(position=(105, 50), text="materiale sp.3")])
        topo.inject(res, data_injector=_collect, snap_distance=10.0)
        self.assertEqual(res.clusters[0].custom["testi"], ["materiale sp.3"])

    def test_beyond_snap_distance_goes_nowhere(self):
        res = _result(_part(0, 0, 100, 100),
                      annotations=[Note(position=(150, 50), text="cartiglio")])
        topo.inject(res, data_injector=_collect, snap_distance=10.0)
        self.assertEqual(res.clusters[0].custom["testi"], [])

    def test_snapped_text_goes_only_to_nearest_part(self):
        res = _result(_part(0, 0, 100, 100), _part(120, 0, 220, 100),
                      annotations=[Note(position=(104, 50), text="Q.tà 2")])
        topo.inject(res, data_injector=_collect, snap_distance=10.0)
        self.assertEqual(res.clusters[0].custom["testi"], ["Q.tà 2"])
        self.assertEqual(res.clusters[1].custom["testi"], [])

    def test_contained_text_ignores_snap(self):
        # dentro la parte 0 ma a 2 dal bordo della parte 1: resta solo alla 0
        res = _result(_part(0, 0, 100, 100), _part(102, 0, 200, 100),
                      annotations=[Note(position=(99, 50), text="dentro")])
        topo.inject(res, data_injector=_collect, snap_distance=10.0)
        self.assertEqual(res.clusters[0].custom["testi"], ["dentro"])
        self.assertEqual(res.clusters[1].custom["testi"], [])


if __name__ == "__main__":
    unittest.main()
