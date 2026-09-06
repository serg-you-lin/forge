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

    def reversed(self) -> "LineSeg":
        """Stessa linea, percorsa al contrario."""
        return LineSeg(start=self.end, end=self.start)


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

    def reversed(self) -> "ArcSeg":
        """Stesso arco fisico, percorso al contrario: scambia gli angoli e nega ccw."""
        return ArcSeg(
            center=self.center,
            radius=self.radius,
            start_angle=self.end_angle,
            end_angle=self.start_angle,
            ccw=not self.ccw,
        )

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

        # Distanza (con segno) dal midpoint al centro lungo la perpendicolare.
        # `radius * cos(sweep/2)` è negativo per sweep > π (arco maggiore,
        # |bulge| > 1): il centro sta dalla parte opposta della corda rispetto
        # all'arco minore. `sqrt(r² - half_chord²)` sarebbe sempre positivo e
        # sceglierebbe l'arco minore anche quando il bulge chiede il maggiore.
        d = radius * math.cos(sweep / 2.0)

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

    def reversed(self) -> "SplineSeg":
        """
        Spline con la parametrizzazione invertita — stesso luogo geometrico
        percorso al contrario.

        Invertire una B-spline NON è solo invertire i punti di controllo:
        va invertito anche il vettore dei nodi e rimappato sul dominio
        originale ``U'[i] = a + b - U[m-i]`` (con ``a = U[0]``, ``b = U[-1]``),
        e vanno invertiti i pesi. Invertire i soli control point lascia la
        curva accoppiata a un vettore nodi sbagliato: la curva emessa in DXF
        risulta deformata all'interno (gli endpoint combaciano lo stesso
        perché una spline clamped interpola il primo e l'ultimo CP).

        `approx_points` / `fit_points` sono solo campioni: si invertono e basta.
        Le tangenti si scambiano E si negano (la tangente entrante all'inizio
        diventa quella uscente alla fine, con verso opposto).
        """
        if self.knots:
            a, b = self.knots[0], self.knots[-1]
            new_knots = [a + b - k for k in reversed(self.knots)]
        else:
            new_knots = []

        def _neg(v):
            return None if v is None else (-v[0], -v[1], -v[2])

        return SplineSeg(
            degree=self.degree,
            control_points=list(reversed(self.control_points)),
            knots=new_knots,
            weights=list(reversed(self.weights)) if self.weights else None,
            approx_points=list(reversed(self.approx_points)) if self.approx_points else None,
            fit_points=list(reversed(self.fit_points)) if self.fit_points else None,
            closed=self.closed,
            periodic=self.periodic,
            flags=self.flags,
            knot_tolerance=self.knot_tolerance,
            fit_tolerance=self.fit_tolerance,
            control_point_tolerance=self.control_point_tolerance,
            start_tangent=_neg(self.end_tangent),
            end_tangent=_neg(self.start_tangent),
        )

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


def segment_endpoints(segment) -> Tuple[Point, Point]:
    """
    (start, end) di un segmento primitivo, in coordinate XY non arrotondate.

    Unica sede di questo calcolo — usata dall'adapter per costruire gli Edge e
    dal gap solver per lavorare su geometria pura.
    """
    if isinstance(segment, LineSeg):
        return segment.start, segment.end

    if isinstance(segment, ArcSeg):
        start = (
            segment.center[0] + segment.radius * math.cos(segment.start_angle),
            segment.center[1] + segment.radius * math.sin(segment.start_angle),
        )
        end = (
            segment.center[0] + segment.radius * math.cos(segment.end_angle),
            segment.center[1] + segment.radius * math.sin(segment.end_angle),
        )
        return start, end

    if isinstance(segment, SplineSeg):
        # approx_points = risultato del flattening: sono i punti reali sulla
        # curva, quindi gli endpoint più affidabili.
        if segment.approx_points:
            s, e = segment.approx_points[0], segment.approx_points[-1]
            return (s[0], s[1]), (e[0], e[1])
        if segment.fit_points:
            s, e = segment.fit_points[0], segment.fit_points[-1]
            return (s[0], s[1]), (e[0], e[1])
        if segment.control_points:
            return segment.control_points[0], segment.control_points[-1]
        return (0.0, 0.0), (0.0, 0.0)

    if isinstance(segment, CircleSeg):
        pt = (segment.center[0] + segment.radius, segment.center[1])
        return pt, pt

    return (0.0, 0.0), (0.0, 0.0)


def segment_is_closed(segment, tolerance: float = DEFAULT_TOLERANCE) -> bool:
    """
    True se gli endpoint del segmento coincidono entro ``tolerance``.

    Unica sede del test di chiusura di un segmento primitivo — usata
    dall'adapter per riconoscere le spline chiuse (loop degenere).
    """
    start, end = segment_endpoints(segment)
    return math.hypot(start[0] - end[0], start[1] - end[1]) < tolerance


@dataclass
class CircleSeg:
    """Cerchio geometrico puro."""
    center: Point
    radius: float
    
    def __post_init__(self):
        if self.radius <= 0:
            raise ValueError(f"Raggio deve essere positivo: {self.radius}")

    def reversed(self) -> "CircleSeg":
        """Un cerchio è simmetrico: invertirlo lo lascia identico."""
        return CircleSeg(center=self.center, radius=self.radius)

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
