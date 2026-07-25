"""
core/primitives/segments.py
---------------------------
Primitive geometriche pure — DTO tra adapter e VirtualShape.

Zero dipendenze da ezdxf, shapely o qualsiasi libreria esterna.
Questi oggetti sono il contratto tra adapter (formato-specifico)
e core (formato-agnostico).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class LineSeg:
    """Segmento rettilineo in WCS."""
    start: Tuple[float, float]
    end:   Tuple[float, float]


@dataclass
class ArcSeg:
    """Arco in WCS, codificato come bulge LWPOLYLINE."""
    start: Tuple[float, float]
    end:   Tuple[float, float]
    bulge: float


@dataclass
class SplineSeg:
    """Spline approssimata come sequenza di punti in WCS."""
    points: List[Tuple[float, float]]


@dataclass
class DiscretizedArcSeg:
    """
    Arco già discretizzato in punti WCS dall'adapter.

    Usato solo nei loop con spline, dove il risultato finale è comunque
    un poligono approssimato. La discretizzazione avviene una volta sola
    nell'adapter — core non ricalcola nulla.
    """
    points: List[Tuple[float, float]]


@dataclass
class CircularArcSeg:
    """Arco standalone in WCS, definito da centro, raggio e angoli."""
    center:      Tuple[float, float]
    radius:      float
    start_angle: float
    end_angle:   float