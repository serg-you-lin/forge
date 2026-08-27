"""
adapters/bridge/edge.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple, Union

from ...core.primitives.segments import LineSeg, ArcSeg, SplineSeg, CircleSeg
from ...model.role import ContourRole

Segment = Union[LineSeg, ArcSeg, SplineSeg, CircleSeg]


@dataclass
class Edge:
    """
    Rappresentazione topologica di una entità geometrica lineare.

    Layer intermedio tra l'entità DXF grezza e il topology engine.
    Il riferimento all'entità originale non viene mai perso.

    Campi:
        role       : ruolo semantico — assegnato dall'adapter prima di costruire l'Edge,
                     mai derivato dal layer DXF qui dentro
        start      : endpoint arrotondato alla tolerance
        end        : endpoint arrotondato alla tolerance
        segment    : primitiva geometrica nativa — mai discretizzata qui,
                     la discretizzazione avviene nel LoopFinder via .discretize()
        closed_path: True se il segmento proviene da un percorso già chiuso
                     (LWPOLYLINE/POLYLINE closed). Geometria strutturale di
                     contorno per definizione — non può essere una linea di piega.
    """
    role:        ContourRole
    start:       Tuple[float, float]
    end:         Tuple[float, float]
    segment:     Segment
    closed_path: bool = False

