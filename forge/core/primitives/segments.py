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

    @classmethod
    def from_chord(cls, start: Point, end: Point, bulge: float) -> "ArcSeg":
        """
        Costruisce un ArcSeg da due punti e il parametro bulge DXF.

        bulge = tan(Δθ / 4), positivo = CCW, negativo = CW.
        Questa è l'unica sede della conversione — parser DXF e altri
        adapter passano qui senza conoscere la geometria interna.
        """
        if abs(bulge) < 1e-9:
            raise ValueError("bulge nullo: usa LineSeg, non ArcSeg")

        ccw = bulge > 0
        half_chord = math.hypot(end[0] - start[0], end[1] - start[1]) / 2.0
        sweep = 4.0 * math.atan(abs(bulge))          # angolo spazzato totale
        radius = half_chord / math.sin(sweep / 2.0)

        # Punto medio della corda
        mx = (start[0] + end[0]) / 2.0
        my = (start[1] + end[1]) / 2.0

        # Versore perpendicolare alla corda (verso il centro)
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        chord_len = 2.0 * half_chord
        nx = -dy / chord_len
        ny =  dx / chord_len

        # Distanza dal midpoint al centro
        d = math.sqrt(max(0.0, radius ** 2 - half_chord ** 2))

        # CCW → centro a sinistra della corda (nx, ny positivo)
        # CW  → centro a destra (nx, ny negativo)
        sign = 1.0 if ccw else -1.0
        cx = mx + sign * d * nx
        cy = my + sign * d * ny

        start_angle = math.atan2(start[1] - cy, start[0] - cx)
        end_angle   = math.atan2(end[1]   - cy, end[0]   - cx)

        return cls(
            center=(cx, cy),
            radius=radius,
            start_angle=start_angle,
            end_angle=end_angle,
            ccw=ccw,
        )

# ---------------------------------------------------------------------------
# SplineSeg
# ---------------------------------------------------------------------------

@dataclass
class SplineSeg:
    degree: int
    control_points: List[Point]
    knots: List[float]
    weights: Optional[List[float]] = None
    approx_points: Optional[List[Point]] = None
    fit_points: Optional[List[Tuple[float, float, float]]] = None
    closed: bool = False
    periodic: bool = False
    flags: int = 0
    knot_tolerance: Optional[float] = None
    fit_tolerance: Optional[float] = None
    control_point_tolerance: Optional[float] = None
    start_tangent: Optional[Tuple[float, float, float]] = None
    end_tangent: Optional[Tuple[float, float, float]] = None

    def discretize(self, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """
        Discretizza la spline in polilinea.
        
        FASE 3: implementare valutazione BSpline corretta con controllo
        della tolleranza. Per ora usiamo interpolazione lineare tra i
        punti di controllo come approssimazione.
        """
        if self.approx_points:
            return list(self.approx_points)

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


@dataclass
class CircleSeg:
    """Cerchio geometrico puro."""
    center: Point
    radius: float
    
    def __post_init__(self):
        if self.radius <= 0:
            raise ValueError(f"Raggio deve essere positivo: {self.radius}")

    def discretize(self, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """
        Discretizza il cerchio in polilinea chiusa.
        Usa il doppio dei segmenti di un arco con lo stesso raggio.
        """
        if self.radius <= tolerance:
            n_segments = 8
        else:
            ratio = 1.0 - tolerance / self.radius
            ratio = max(-1.0, min(1.0, ratio))
            angle_per_segment = 2.0 * math.acos(ratio)
            # Cerchio completo = 2π, quindi il doppio dei segmenti
            n_segments = int(math.ceil(2 * math.pi / angle_per_segment))
        
        # MIN_SEGMENTS_ARC * 2 per coerenza (64 segmenti minimo)
        n_segments = max(MIN_SEGMENTS_ARC * 2, n_segments)
        n_segments = min(n_segments, 128)
        
        # Genera i punti (chiuso)
        pts = []
        for i in range(n_segments + 1):
            angle = 2 * math.pi * i / n_segments
            x = self.center[0] + self.radius * math.cos(angle)
            y = self.center[1] + self.radius * math.sin(angle)
            pts.append((x, y))
        
        return pts
