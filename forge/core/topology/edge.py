"""
core/topology/edge.py
----------------------
Rappresentazione topologica di una entità geometrica lineare — l'unità che
graph.py / loop_finder.py / non_contour_edges.py / gap_solver.py usano per
costruire e percorrere il grafo. Non è una primitiva geometrica (quelle sono
LineSeg/ArcSeg/SplineSeg/CircleSeg/EllipseSeg in core/primitives/segments.py,
math puro senza semantica): `Edge` ne avvolge una con ruolo, provenienza e
stile — dati di dominio, zero riferimento all'entità sorgente di alcun formato.

Vive in core/ (non più in adapters/bridge/, D18) perché è core il suo
consumatore principale: ogni adapter (DXF, PDF, ...) costruisce Edge, ma è
il core a definirne la forma, esattamente come per le primitive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple, Union

from ..primitives.segments import LineSeg, ArcSeg, SplineSeg, CircleSeg, EllipseSeg
from ...model.style import EdgeStyle

Segment = Union[LineSeg, ArcSeg, SplineSeg, CircleSeg, EllipseSeg]


@dataclass
class Edge:
    """
    Layer intermedio tra l'entità sorgente grezza (di qualsiasi formato) e il
    topology engine. Dati puri — nessun riferimento all'entità sorgente.

    Campi:
        role       : ruolo semantico (stringa: costante ContourRole o slug di un
                     consumatore) — assegnato dall'adapter prima di costruire
                     l'Edge, mai derivato dal layer DXF qui dentro
        start      : endpoint arrotondato alla tolerance
        end        : endpoint arrotondato alla tolerance
        segment    : primitiva geometrica nativa — mai discretizzata qui,
                     la discretizzazione avviene nel LoopFinder via .discretize()
        style      : aspetto grezzo (linetype/colore) dell'entità sorgente —
                     captato dall'adapter, mai interpretato qui (Cluster E).

    Deliberatamente NIENTE campo che dica "veniva da una LWPOLYLINE chiusa"
    o simili: se un percorso è già chiuso è un fatto che il grafo di forge
    scopre da sé (`Graph.degenerate_loops`, un loop trovato dal
    `LoopFinder`) — non un'informazione che l'adapter può accorciare
    consegnandola come flag. Un flag così è la provenienza nel formato
    sorgente travestita da proprietà topologica: un adapter PDF/SVG non
    avrebbe modo di popolarlo, e il core non deve mai aver bisogno che lo
    faccia (trovato e tolto: MAP.md, seguito D50).
    """
    role:    str
    start:   Tuple[float, float]
    end:     Tuple[float, float]
    segment: Segment
    style:   EdgeStyle = field(default_factory=EdgeStyle)
