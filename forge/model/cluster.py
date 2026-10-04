"""
model/cluster.py
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from shapely.geometry import Polygon

from forge.model.contour import ForgeContour


@dataclass
class ForgeCluster:
    outer:         ForgeContour
    inners:        List[ForgeContour]                      = field(default_factory=list)
    label:         str                                     = ""
    source_file:   str                                     = ""
    custom:        dict                                    = field(default_factory=dict)
    # Overlay di un consumatore (snapbend, snapdraw, un tool custom), di
    # norma un `model.detected.DetectedFeatures` (D44, D90). `None` finché
    # nessuno ci ha scritto: distingue "non
    # ho ancora fatto detect" da "ho fatto detect e non c'è nessuna
    # feature", cosa che i vecchi campi fissi (sempre liste vuote) non
    # permettevano di distinguere. Il solo contratto richiesto, mai imposto
    # a runtime, è duck-typed: `.get(name, default)` e `.items()`.
    detected:      Optional[Any]                           = None

    def features(self, name: str) -> list:
        """
        Collezione `name` attaccata a `self.detected`, o `[]` se `detected` è
        `None` o quel nome non è stato scritto — accesso sicuro per un
        consumatore che non vuole gestire `None` a mano. Generico: non ha
        bisogno di sapere quali nomi esistono (`"holes"`, `"flange_view_hint"`,
        qualunque altro).
        """
        if self.detected is None:
            return []
        return self.detected.get(name, [])

    @property
    def overlay_voids(self) -> list:
        """
        Gli elementi dell'overlay che sono vuoti del pezzo: chi li ha letti
        dichiara `is_void = True` e porta un `polygon` (MAP.md D90). Un
        consumatore che toglie un contorno da `inners` per farne un suo
        elemento (un foro di snapbend) non cambia l'area del pezzo.
        """
        if self.detected is None:
            return []
        return [
            item for _name, items in self.detected.items() for item in items
            if getattr(item, "is_void", False) and getattr(item, "polygon", None) is not None
        ]

    @property
    def polygon_with_holes(self) -> Polygon:
        all_inners = (
            [v.polygon for v in self.overlay_voids]
            + [i.polygon for i in self.inners]
        )
        if not all_inners:
            return self.outer.polygon
        return Polygon(
            self.outer.polygon.exterior.coords,
            [p.exterior.coords for p in all_inners],
        )

    @property
    def bbox(self):
        return self.outer.bbox

    @property
    def area(self) -> float:
        """
        Area netta: depth dispari è vuoto, depth pari è materiale (isola nel
        vuoto del padre) — i segni alternano col livello (MAP.md D89).
        """
        return (
            self.outer.area
            - sum(v.polygon.area for v in self.overlay_voids)
            - sum(i.area if i.depth % 2 else -i.area for i in self.inners)
        )

    @property
    def summary(self) -> dict:
        """
        Conteggio grezzo per nome — `{nome}_count: len(items)` per ogni
        collezione attaccata a `self.detected` (`{}` se `detected is None`).

        Generico e sempre disponibile, zero import a runtime: funziona
        identico per chi ha fatto solo `heal()` (oggi: sempre `{}`, come
        prima di questo refactor) e per qualunque nome custom attaccato da un
        tool esterno — forge non ha bisogno di sapere cosa sia.

        Il conteggio ricco per tipo (fori per tipo, pieghe raggruppate) è del
        consumatore che li ha letti (snapbend `describe_features`, D88).
        """
        if self.detected is None:
            return {}
        return {f"{name}_count": len(items) for name, items in self.detected.items()}

    def to_dict(self) -> dict:
        return {
            "label":                self.label,
            "source_file":          self.source_file,
            "area":                 round(self.area, 4),
            "inner_contours_count": len(self.inners),
            "bbox": {
                "minx": round(self.bbox[0], 4),
                "miny": round(self.bbox[1], 4),
                "maxx": round(self.bbox[2], 4),
                "maxy": round(self.bbox[3], 4),
            },
            "outer":  list(self.outer.polygon.exterior.coords),
            "inners": [list(i.polygon.exterior.coords) for i in self.inners],
            "custom": self.custom,
        }
