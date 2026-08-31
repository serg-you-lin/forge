"""
core/topology/edge.py
----------------------
Rappresentazione topologica di una entità geometrica lineare — l'unità che
graph.py / loop_finder.py / bending_detector.py / gap_solver.py usano per
costruire e percorrere il grafo. Non è una primitiva geometrica (quelle sono
LineSeg/ArcSeg/SplineSeg/CircleSeg in core/primitives/segments.py, math puro
senza semantica): `Edge` ne avvolge una con ruolo, provenienza e stile —
dati di dominio, zero riferimento all'entità sorgente di alcun formato.

Vive in core/ (non più in adapters/bridge/, D18) perché è core il suo
consumatore principale: ogni adapter (DXF, PDF, ...) costruisce Edge, ma è
il core a definirne la forma, esattamente come per le primitive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple, Union

from ..primitives.segments import LineSeg, ArcSeg, SplineSeg, CircleSeg
from ...model.role import ContourRole
from ...model.style import EdgeStyle

Segment = Union[LineSeg, ArcSeg, SplineSeg, CircleSeg]


@dataclass
class Edge:
    """
    Layer intermedio tra l'entità sorgente grezza (di qualsiasi formato) e il
    topology engine. Dati puri — nessun riferimento all'entità sorgente.

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
        style      : aspetto grezzo (linetype/colore) dell'entità sorgente —
                     captato dall'adapter, mai interpretato qui (Cluster E).
    """
    role:        ContourRole
    start:       Tuple[float, float]
    end:         Tuple[float, float]
    segment:     Segment
    closed_path: bool = False
    style:       EdgeStyle = field(default_factory=EdgeStyle)
