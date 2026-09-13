"""
forge/tools/simplify_points.py
--------------------------------
Ricostruzione di primitive pulite (linea/arco/cerchio/spline) da una sequenza
di punti ordinata e densa — l'inverso della discretizzazione di
core/primitives/segments.py. Il fit ad arco/cerchio è opt-in
(`arc_fit_tolerance`, default `None`): un tratto curvo diventa `ArcSeg`/
`CircleSeg` solo se il chiamante chiede esplicitamente la tolleranza entro cui
accettarlo, altrimenti resta sempre una `SplineSeg` come prima.

    detect_corners  — per ogni punto, True se è uno spigolo (angolo vivo)
    fit_primitives  — spezza la sequenza sui corner e rifitta ogni tratto
    simplify_points — le due sopra in un solo passo

Generico: non sa nulla di immagini né di un formato di file. Chi consegna i
punti (Smoother, da un contorno OpenCV; un adapter DXF con una spline già
discretizzata in LWPOLYLINE; un futuro adapter PDF) decide da dove vengono —
qui c'è solo la ricostruzione geometrica. Le soglie sono SEMPRE parametri del
chiamante, mai hardcoded (stessa regola di core/primitives/segments.py).
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple, Union

import numpy as np
from ezdxf.math import BSpline

from ..core.primitives.segments import ArcSeg, CircleSeg, LineSeg, SplineSeg, Point

DEFAULT_ANGLE_THRESHOLD_DEG = 50.0
DEFAULT_MIN_POINTS_FOR_SPLINE = 4
DEFAULT_SPLINE_DEGREE = 3
DEFAULT_DUPLICATE_TOLERANCE = 1e-6
DEFAULT_ARC_FIT_TOLERANCE = None  # disattivato: nessun fit ad arco finché non richiesto


# ---------------------------------------------------------------------------
# detect_corners
# ---------------------------------------------------------------------------

def _interior_angle_deg(prev_pt: Point, curr_pt: Point, next_pt: Point) -> float:
    """Angolo interno (gradi) in curr_pt fra i lati verso prev_pt e next_pt."""
    v1 = (prev_pt[0] - curr_pt[0], prev_pt[1] - curr_pt[1])
    v2 = (next_pt[0] - curr_pt[0], next_pt[1] - curr_pt[1])
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        return 180.0
    cos_a = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    cos_a = max(-1.0, min(1.0, cos_a))
    return math.degrees(math.acos(cos_a))


def detect_corners(
    points: List[Point],
    angle_threshold_deg: float = DEFAULT_ANGLE_THRESHOLD_DEG,
    closed: bool = True,
) -> List[bool]:
    """
    Per ogni punto, True se l'angolo formato dai due lati adiacenti è sotto
    `angle_threshold_deg` (spigolo vivo da non smussare via col refit spline).

    Args:
        points:               sequenza di punti (x, y), ordinata
        angle_threshold_deg:  soglia in gradi sotto cui un punto è uno spigolo
        closed:               True se `points` è un contorno chiuso (il primo
                               e l'ultimo punto sono adiacenti). False per una
                               polilinea aperta: i due estremi non hanno due
                               lati adiacenti veri e non sono mai spigoli.
    """
    n = len(points)
    if n < 3:
        return [False] * n

    corners = [False] * n
    rng = range(n) if closed else range(1, n - 1)
    for i in rng:
        prev_pt = points[(i - 1) % n]
        curr_pt = points[i]
        next_pt = points[(i + 1) % n]
        if _interior_angle_deg(prev_pt, curr_pt, next_pt) < angle_threshold_deg:
            corners[i] = True
    return corners


# ---------------------------------------------------------------------------
# fit_primitives
# ---------------------------------------------------------------------------

def _drop_duplicate_points(points: List[Point], tolerance: float) -> List[Point]:
    """Rimuove punti consecutivi coincidenti entro `tolerance` (serve al fit spline)."""
    if not points:
        return []
    cleaned = [points[0]]
    for p in points[1:]:
        last = cleaned[-1]
        if math.hypot(p[0] - last[0], p[1] - last[1]) > tolerance:
            cleaned.append(p)
    return cleaned


def _split_into_stretches(
    points: List[Point], is_corner: List[bool], closed: bool
) -> List[List[Point]]:
    """
    Spezza `points` in tratti fra due spigoli consecutivi (estremi inclusi).

    Contorno chiuso senza spigoli → un solo tratto: l'intero loop, richiuso sul
    primo punto. Polilinea aperta: i due estremi aprono/chiudono sempre un
    tratto anche se non sono spigoli (`detect_corners` non li marca mai tali).
    """
    n = len(points)
    indices = [i for i, c in enumerate(is_corner) if c]

    if closed and not indices:
        return [points + [points[0]]]

    if closed:
        start = indices[0]
        pts_rot = points[start:] + points[:start]
        corners_rot = is_corner[start:] + is_corner[:start]
    else:
        pts_rot = points
        corners_rot = is_corner

    stretches: List[List[Point]] = []
    current = [pts_rot[0]]
    for i in range(1, n):
        current.append(pts_rot[i])
        if corners_rot[i]:
            stretches.append(current)
            current = [pts_rot[i]]
    if closed:
        current.append(pts_rot[0])
    stretches.append(current)
    return stretches


def _fit_circle_kasa(points: List[Point]) -> Optional[Tuple[Point, float, float]]:
    """
    Fit algebrico (Kasa) ai minimi quadrati di un cerchio su `points`: minimizza
    `x²+y²+Dx+Ey+F=0`, che è un cerchio di centro `(-D/2,-E/2)` e raggio
    ricavabile da `D,E,F`. Ritorna `(center, radius, max_residual)` —
    `max_residual` è lo scostamento massimo di un punto dal cerchio fittato,
    per decidere se accettarlo. `None` se il fit è degenere (meno di 3 punti,
    punti quasi collineari, raggio non reale).
    """
    if len(points) < 3:
        return None

    pts = np.asarray(points, dtype=float)
    x, y = pts[:, 0], pts[:, 1]
    a_matrix = np.column_stack([x, y, np.ones_like(x)])
    b_vector = -(x**2 + y**2)
    try:
        (d, e, f), *_ = np.linalg.lstsq(a_matrix, b_vector, rcond=None)
    except np.linalg.LinAlgError:
        return None

    center = (-d / 2.0, -e / 2.0)
    radius_sq = (d**2 + e**2) / 4.0 - f
    if radius_sq <= 0:
        return None
    radius = math.sqrt(radius_sq)

    residuals = np.hypot(x - center[0], y - center[1]) - radius
    max_residual = float(np.max(np.abs(residuals)))
    return center, radius, max_residual


def _arc_angles(points: List[Point], center: Point) -> Tuple[float, float, bool]:
    """
    `(start_angle, end_angle, ccw)` in radianti di un arco che passa per
    `points` (in ordine) intorno a `center`. Segue la rotazione reale della
    sequenza "srotolando" gli angoli (come `numpy.unwrap`) invece di guardare
    solo primo e ultimo punto — altrimenti un arco sopra i 180° si confonde
    con uno più corto nel verso sbagliato.
    """
    raw = [math.atan2(p[1] - center[1], p[0] - center[0]) for p in points]
    unwrapped = [raw[0]]
    for angle in raw[1:]:
        delta = angle - unwrapped[-1]
        # riporta il delta fra due punti consecutivi in (-pi, pi]
        while delta > math.pi:
            delta -= 2 * math.pi
        while delta <= -math.pi:
            delta += 2 * math.pi
        unwrapped.append(unwrapped[-1] + delta)

    total = unwrapped[-1] - unwrapped[0]
    ccw = total >= 0
    return raw[0], raw[0] + total, ccw


def _try_fit_arc(
    points: List[Point], arc_fit_tolerance: float, duplicate_tolerance: float
) -> Optional[Union[ArcSeg, CircleSeg]]:
    """
    Prova un fit a cerchio su `points`; lo accetta solo se lo scostamento
    massimo dei punti dal cerchio è entro `arc_fit_tolerance`. Un tratto che si
    richiude su se stesso (primo e ultimo punto coincidenti) diventa un
    `CircleSeg` completo, altrimenti un `ArcSeg` fra i due estremi.
    """
    fit = _fit_circle_kasa(points)
    if fit is None:
        return None
    center, radius, max_residual = fit
    if max_residual > arc_fit_tolerance:
        return None

    closes_on_itself = math.hypot(
        points[0][0] - points[-1][0], points[0][1] - points[-1][1]
    ) <= duplicate_tolerance
    if closes_on_itself:
        return CircleSeg(center=center, radius=radius)

    start_angle, end_angle, ccw = _arc_angles(points, center)
    return ArcSeg(center=center, radius=radius, start_angle=start_angle, end_angle=end_angle, ccw=ccw)


def _fit_spline(points: List[Point], degree: int) -> SplineSeg:
    """Un solo SplineSeg passante per `points` (curva di fit globale, non ai minimi quadrati)."""
    pts_3d = [(x, y, 0.0) for x, y in points]
    bspline = BSpline.from_fit_points(pts_3d, degree=degree)
    return SplineSeg(
        degree=bspline.degree,
        control_points=[(p.x, p.y) for p in bspline.control_points],
        knots=list(bspline.knots()),
        fit_points=pts_3d,
    )


def fit_primitives(
    points: List[Point],
    is_corner: List[bool],
    closed: bool = True,
    min_points_for_spline: int = DEFAULT_MIN_POINTS_FOR_SPLINE,
    spline_degree: int = DEFAULT_SPLINE_DEGREE,
    duplicate_tolerance: float = DEFAULT_DUPLICATE_TOLERANCE,
    arc_fit_tolerance: Optional[float] = DEFAULT_ARC_FIT_TOLERANCE,
) -> List[Union[LineSeg, ArcSeg, CircleSeg, SplineSeg]]:
    """
    Spezza `points` sui corner marcati in `is_corner` e rifitta ogni tratto: un
    tratto con meno di `min_points_for_spline` punti diventa una sequenza di
    `LineSeg` (troppo pochi punti per una curva significativa); altrimenti, se
    `arc_fit_tolerance` è impostato e il tratto sta entro quella tolleranza su
    un cerchio a raggio costante, diventa un `ArcSeg` (o un `CircleSeg` se il
    tratto si richiude su se stesso); in tutti gli altri casi un unico
    `SplineSeg` di grado `spline_degree` passante per tutti i punti del tratto.

    Args:
        points:                 stessa sequenza passata a `detect_corners`
        is_corner:               maschera spigoli, es. da `detect_corners`
        closed:                  stesso significato di `detect_corners`
        min_points_for_spline:   sotto questa cardinalità un tratto resta linee
        spline_degree:           grado della B-spline di fit
        duplicate_tolerance:     distanza sotto cui due punti consecutivi sono
                                  lo stesso punto (il fit spline non tollera
                                  punti coincidenti)
        arc_fit_tolerance:       scostamento massimo (stesse unità dei punti)
                                  entro cui un tratto curvo è considerato un
                                  arco/cerchio a raggio costante invece che una
                                  spline. `None` (default) disattiva il fit ad
                                  arco — nessun cambio di comportamento per chi
                                  non lo passa esplicitamente.
    """
    stretches = _split_into_stretches(points, is_corner, closed)
    primitives: List[Union[LineSeg, ArcSeg, CircleSeg, SplineSeg]] = []

    for stretch in stretches:
        pts = _drop_duplicate_points(stretch, duplicate_tolerance)
        if len(pts) < 2:
            continue
        if len(pts) < min_points_for_spline or len(pts) <= spline_degree:
            for a, b in zip(pts, pts[1:]):
                primitives.append(LineSeg(start=a, end=b))
            continue

        if arc_fit_tolerance is not None:
            arc_or_circle = _try_fit_arc(pts, arc_fit_tolerance, duplicate_tolerance)
            if arc_or_circle is not None:
                primitives.append(arc_or_circle)
                continue

        primitives.append(_fit_spline(pts, spline_degree))

    return primitives


# ---------------------------------------------------------------------------
# simplify_points
# ---------------------------------------------------------------------------

def simplify_points(
    points: List[Point],
    closed: bool = True,
    angle_threshold_deg: float = DEFAULT_ANGLE_THRESHOLD_DEG,
    min_points_for_spline: int = DEFAULT_MIN_POINTS_FOR_SPLINE,
    spline_degree: int = DEFAULT_SPLINE_DEGREE,
    duplicate_tolerance: float = DEFAULT_DUPLICATE_TOLERANCE,
    arc_fit_tolerance: Optional[float] = DEFAULT_ARC_FIT_TOLERANCE,
) -> List[Union[LineSeg, ArcSeg, CircleSeg, SplineSeg]]:
    """
    `detect_corners` + `fit_primitives` in un solo passo — comodo quando serve
    solo il risultato finale. Vedi le due funzioni per il significato dei
    parametri.
    """
    is_corner = detect_corners(points, angle_threshold_deg, closed=closed)
    return fit_primitives(
        points,
        is_corner,
        closed=closed,
        min_points_for_spline=min_points_for_spline,
        spline_degree=spline_degree,
        duplicate_tolerance=duplicate_tolerance,
        arc_fit_tolerance=arc_fit_tolerance,
    )
