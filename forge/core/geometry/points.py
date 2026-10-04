"""
forge/core/geometry/points.py
-----------------------------
Sequenze ordinate di punti: angolo interno, spigoli, doppioni, fit di un
cerchio, angoli di un arco, b-spline interpolante.
"""

import math
from typing import Optional, Tuple, List
import numpy as np

from ..primitives.segments import LineSeg, ArcSeg

Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# Sequenze di punti — angolo interno, deduplica, fit a cerchio (D38)
# ---------------------------------------------------------------------------
# Matematica generica su una sequenza ordinata di punti (x, y): non sa nulla
# di primitive forge (LineSeg/ArcSeg/...) né di come il chiamante la userà.
# Nata dentro tools/simplify_points.py (D33/D36), spostata qui perché un
# secondo consumatore (un futuro tool linguette) ne ha bisogno senza
# duplicarla — `core/primitives/fitting.py` resta l'orchestratore che decide
# quando/come usarla per ricostruire linee/archi/spline.

DEFAULT_ANGLE_THRESHOLD_DEG = 50.0
DEFAULT_DUPLICATE_TOLERANCE = 1e-6


def interior_angle_deg(prev_pt: Point, curr_pt: Point, next_pt: Point) -> float:
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
        if interior_angle_deg(prev_pt, curr_pt, next_pt) < angle_threshold_deg:
            corners[i] = True
    return corners


def drop_duplicate_points(
    points: List[Point], tolerance: float = DEFAULT_DUPLICATE_TOLERANCE
) -> List[Point]:
    """Rimuove punti consecutivi coincidenti entro `tolerance`."""
    if not points:
        return []
    cleaned = [points[0]]
    for p in points[1:]:
        last = cleaned[-1]
        if math.hypot(p[0] - last[0], p[1] - last[1]) > tolerance:
            cleaned.append(p)
    return cleaned


def fit_circle_kasa(points: List[Point]) -> Optional[Tuple[Point, float, float]]:
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


def arc_angles(points: List[Point], center: Point) -> Tuple[float, float, bool]:
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


def interpolate_bspline(points: List[Point], degree: int = 3) -> Tuple[List[Point], List[float]]:
    """
    B-spline di grado `degree` che passa per tutti i `points` (interpolazione
    globale, Piegl & Tiller cap. 9.2.1): parametri per lunghezza di corda,
    nodi "natural" per grado dispari e mediati per grado pari. Ritorna
    `(control_points, knots)`, nodi normalizzati in [0, 1].
    """
    n = len(points) - 1
    p = degree
    if n < p:
        raise ValueError(f"Servono almeno {p + 1} punti per una spline di grado {p}")

    dists = [math.dist(points[i], points[i + 1]) for i in range(n)]
    total = sum(dists)
    if total > 0:
        t, acc = [0.0], 0.0
        for d in dists:
            acc += d
            t.append(acc / total)
        t[-1] = 1.0
    else:
        t = [i / n for i in range(n + 1)]

    if p % 2:
        inner = t[2:n - p + 2]
    else:
        inner = [sum(t[j:j + p]) / p for j in range(1, n - p + 1)]
    knots = [0.0] * (p + 1) + list(inner) + [1.0] * (p + 1)

    basis = np.array([_bspline_basis_row(u, p, knots, n) for u in t])
    control = np.linalg.solve(basis, np.array(points, dtype=np.float64))
    return [(float(x), float(y)) for x, y in control], knots


def _bspline_basis_row(u: float, p: int, knots: List[float], n: int) -> List[float]:
    """Le n+1 funzioni di base N_i,p(u) (Cox-de Boor, Piegl & Tiller A2.2)."""
    row = [0.0] * (n + 1)
    if u >= knots[n + 1]:
        row[n] = 1.0
        return row
    span = p
    while span < n and knots[span + 1] <= u:
        span += 1
    funcs = [1.0] + [0.0] * p
    left, right = [0.0] * (p + 1), [0.0] * (p + 1)
    for j in range(1, p + 1):
        left[j] = u - knots[span + 1 - j]
        right[j] = knots[span + j] - u
        saved = 0.0
        for r in range(j):
            temp = funcs[r] / (right[r + 1] + left[j - r])
            funcs[r] = saved + right[r + 1] * temp
            saved = left[j - r] * temp
        funcs[j] = saved
    for j in range(p + 1):
        row[span - p + j] = funcs[j]
    return row
