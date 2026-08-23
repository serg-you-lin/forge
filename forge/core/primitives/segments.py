"""
forge/core/primitives/segments.py
----------------------------------
Primitive geometriche pure con discretizzazione centralizzata.

Questa è l'UNICA sede della discretizzazione.
Ogni adapter (DXF, PDF, SVG, ...) deve convertire le sue entità in queste
primitive e poi usare SOLO i metodi qui definiti.

La tolleranza è SEMPRE passata come parametro, mai hardcoded.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# COSTANTI DI DISCRETIZZAZIONE — MODIFICARE QUI PER CAMBIARE COMPORTAMENTO
# ---------------------------------------------------------------------------

# Numero minimo di segmenti per archi (evita errori di area su archi grandi)
MIN_SEGMENTS_ARC = 32

# Numero massimo di segmenti per tratto di spline (evita esplosione di punti)
MAX_SEGMENTS_SPLINE = 100

# Angolo fisso (gradi) per archi con raggio molto piccolo
FALLBACK_ANGLE_DEG = 10

# Tolleranza predefinita se non specificata
DEFAULT_TOLERANCE = 0.01


# ---------------------------------------------------------------------------
# LineSeg
# ---------------------------------------------------------------------------

@dataclass
class LineSeg:
    start: Point
    end: Point

    def discretize(self, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """
        Una linea è già esatta: restituisce solo i due endpoint.
        La tolleranza non serve ma la accettiamo per uniformità di interfaccia.
        """
        return [self.start, self.end]


# ---------------------------------------------------------------------------
# ArcSeg
# ---------------------------------------------------------------------------

@dataclass
class ArcSeg:
    center: Point
    radius: float
    start_angle: float  # radianti
    end_angle: float    # radianti
    ccw: bool = True

    def _sweep(self) -> float:
        """Angolo spazzato in radianti, sempre positivo."""
        if self.ccw:
            raw = self.end_angle - self.start_angle
        else:
            raw = self.start_angle - self.end_angle
        sweep = raw % (2 * math.pi)
        if sweep < 1e-12 and abs(raw) > 1e-12:
            sweep = 2 * math.pi
        return sweep

    def discretize(self, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """
        Discretizza l'arco in polilinea con errore di sagitta < tolerance.
        
        Formula: sagitta = r * (1 - cos(θ/2))
        dove θ è l'angolo per segmento.
        
        Usa ALMENO MIN_SEGMENTS_ARC segmenti per archi grandi.
        """
        total_angle = self._sweep()
        
        if total_angle < 1e-12:
            # Arco nullo
            start_pt = self._point_at(self.start_angle)
            return [start_pt, start_pt]
        
        # Calcola angolo per segmento in base alla tolleranza
        if self.radius <= tolerance:
            # Raggio molto piccolo: usa angolo fisso
            angle_per_segment = math.radians(FALLBACK_ANGLE_DEG)
        else:
            ratio = 1.0 - tolerance / self.radius
            ratio = max(-1.0, min(1.0, ratio))
            angle_per_segment = 2.0 * math.acos(ratio)
        
        # Applica il minimo di segmenti
        n_segments = max(MIN_SEGMENTS_ARC, int(math.ceil(total_angle / angle_per_segment)))
        
        # Genera i punti
        pts = []
        for i in range(n_segments + 1):
            t = i / n_segments
            if self.ccw:
                angle = self.start_angle + t * total_angle
            else:
                angle = self.start_angle - t * total_angle
            pts.append(self._point_at(angle))
        
        return pts

    def _point_at(self, angle: float) -> Point:
        """Punto sull'arco all'angolo dato (radianti)."""
        x = self.center[0] + self.radius * math.cos(angle)
        y = self.center[1] + self.radius * math.sin(angle)
        return (x, y)


# ---------------------------------------------------------------------------
# SplineSeg
# ---------------------------------------------------------------------------

@dataclass
class SplineSeg:
    degree: int
    control_points: List[Point]
    knots: List[float]
    weights: Optional[List[float]] = None

    def discretize(self, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """
        Discretizza la spline in polilinea.
        
        FASE 3: implementare valutazione BSpline corretta con controllo
        della tolleranza. Per ora usiamo interpolazione lineare tra i
        punti di controllo come approssimazione.
        """
        if not self.control_points:
            return []
        
        if len(self.control_points) == 1:
            return [self.control_points[0]]
        
        result: List[Point] = []
        
        for i in range(len(self.control_points) - 1):
            p1 = self.control_points[i]
            p2 = self.control_points[i + 1]
            
            dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            
            if dist <= tolerance:
                n_segments = 1
            else:
                n_segments = max(1, int(math.ceil(dist / tolerance)))
                n_segments = min(n_segments, MAX_SEGMENTS_SPLINE)
            
            for j in range(n_segments):
                t = j / n_segments
                x = p1[0] + t * (p2[0] - p1[0])
                y = p1[1] + t * (p2[1] - p1[1])
                result.append((x, y))
        
        result.append(self.control_points[-1])
        
        return result


# ---------------------------------------------------------------------------
# Alias per retrocompatibilità
# ---------------------------------------------------------------------------

CircularArcSeg = ArcSeg