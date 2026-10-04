"""
tests/unit/test_attached_export.py
----------------------------------
D70: `to_dxf` scrive ogni collezione attaccata a `cluster.detected` da un
consumatore (D90: tutte, forge non ne conosce nessuna per nome). Un elemento
con `role` va sul layer del suo ruolo: i suoi `contours` se ne ha, altrimenti
i suoi `segments`. Senza ruolo o senza geometria si salta.
"""

import unittest
from dataclasses import dataclass, field

import forge
from forge.model import DetectedFeatures


@dataclass
class _Mark:
    """Un elemento di un consumatore: solo quello che l'exporter legge."""
    role: str
    segments: list = field(default_factory=list)
    styles: list = field(default_factory=list)
    source: str = "test"
    confidence: float = 1.0


@dataclass
class _Composite:
    """Un elemento fatto di più contorni chiusi (un foro con la sua sede)."""
    role: str
    contours: list = field(default_factory=list)
    source: str = "test"
    confidence: float = 1.0


def _plate():
    # piastra 100x50 con due fori concentrici e uno singolo
    doc = forge.load_geometry([
        {"type": "polygon", "points": [(0, 0), (100, 0), (100, 50), (0, 50)]},
        {"type": "circle", "center": (20, 25), "radius": 3},
        {"type": "circle", "center": (20, 25), "radius": 6},
        {"type": "circle", "center": (70, 25), "radius": 4},
    ])
    return doc, forge.heal(doc)


def _layers(out):
    return [e.dxf.layer for e in out.modelspace()]


class TestAttachedExport(unittest.TestCase):

    def test_elemento_con_segments_sul_layer_del_suo_ruolo(self):
        doc, result = _plate()
        cluster = result.clusters[0]
        single = next(i for i in cluster.inners if abs(i.polygon.area - 3.1416 * 16) < 1)
        cluster.detected = DetectedFeatures()
        cluster.detected.attach("my_marks", [_Mark(role="my_role", segments=single.segments)])
        layers = _layers(forge.to_dxf(result, doc))
        self.assertEqual(layers.count("my_role"), 1)

    def test_elemento_con_contours_scrive_ogni_contorno(self):
        doc, result = _plate()
        cluster = result.clusters[0]
        pair = [i for i in cluster.inners if abs(i.polygon.centroid.x - 20) < 1e-6]
        self.assertEqual(len(pair), 2)
        cluster.detected = DetectedFeatures()
        cluster.detected.attach("my_marks", [_Composite(role="my_seat", contours=pair)])
        self.assertEqual(_layers(forge.to_dxf(result, doc)).count("my_seat"), 2)

    def test_senza_ruolo_o_senza_geometria_si_salta(self):
        doc, result = _plate()
        cluster = result.clusters[0]
        before = len(_layers(forge.to_dxf(result, doc)))
        cluster.detected = DetectedFeatures()
        cluster.detected.attach("my_marks", [_Mark(role="", segments=cluster.inners[0].segments),
                                             _Mark(role="my_role"), object()])
        self.assertEqual(len(_layers(forge.to_dxf(result, doc))), before)


if __name__ == "__main__":
    unittest.main()
