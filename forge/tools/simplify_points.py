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

La matematica generica su una sequenza di punti (angolo interno, deduplica,
fit a cerchio, `detect_corners` stesso) vive in `core/geometry.py` (D38) —
qui restano solo l'orchestrazione (spezzare sui corner, decidere linea vs
arco/cerchio vs spline) e il fit spline (specifico di questa ricostruzione).
`detect_corners` resta importabile da qui per compatibilità con chi già lo
usa da `forge.tools.simplify_points`.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple, Union

from ezdxf.math import BSpline

from ..core.primitives.segments import ArcSeg, CircleSeg, LineSeg, SplineSeg, Point
from ..core.geometry import (
    DEFAULT_ANGLE_THRESHOLD_DEG,
    DEFAULT_DUPLICATE_TOLERANCE,
    detect_corners,
    drop_duplicate_points,
    fit_circle_kasa,
    arc_angles,
)

DEFAULT_MIN_POINTS_FOR_SPLINE = 4
DEFAULT_SPLINE_DEGREE = 3
DEFAULT_ARC_FIT_TOLERANCE = None  # disattivato: nessun fit ad arco finché non richiesto


# ---------------------------------------------------------------------------
# fit_primitives
# ---------------------------------------------------------------------------

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


def _try_fit_arc(
    points: List[Point], arc_fit_tolerance: float, duplicate_tolerance: float
) -> Optional[Union[ArcSeg, CircleSeg]]:
    """
    Prova un fit a cerchio su `points`; lo accetta solo se lo scostamento
    massimo dei punti dal cerchio è entro `arc_fit_tolerance`. Un tratto che si
    richiude su se stesso (primo e ultimo punto coincidenti) diventa un
    `CircleSeg` completo, altrimenti un `ArcSeg` fra i due estremi.
    """
    fit = fit_circle_kasa(points)
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

    start_angle, end_angle, ccw = arc_angles(points, center)
    return ArcSeg(center=center, radius=radius, start_angle=start_angle, end_angle=end_angle, ccw=ccw)


def _fit_spline(points: List[Point], degree: int, closed: bool = False) -> SplineSeg:
    """
    Un solo SplineSeg passante per `points` (curva di fit globale, non ai
    minimi quadrati). Niente `fit_points` in uscita (MAP.md D41): control
    points + nodi bastano a definire la curva per intero, `fit_points` è solo
    metadato opzionale per un editor — averlo comunque, insieme ai control
    points, in un DXF ha reso alcuni lettori CAM incapaci di leggere la
    spline (letto: SigmaNest), forse perché provano a ricostruire la curva
    dai fit points con una loro logica invece di usare quella già data.
    `closed` va passato dal chiamante: solo lui sa se questo tratto è
    l'intero contorno chiuso o solo un arco fra due spigoli.
    """
    pts_3d = [(x, y, 0.0) for x, y in points]
    bspline = BSpline.from_fit_points(pts_3d, degree=degree)
    return SplineSeg(
        degree=bspline.degree,
        control_points=[(p.x, p.y) for p in bspline.control_points],
        knots=list(bspline.knots()),
        closed=closed,
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
    # Un solo tratto con `closed=True` è l'intero contorno (MAP.md D41: mai
    # più di uno per costruzione di `_split_into_stretches`, sia con zero
    # spigoli sia con un solo spigolo che chiude il giro su se stesso) — è
    # l'unico caso in cui la spline risultante deve portare `closed=True`.
    whole_loop_as_one_stretch = closed and len(stretches) == 1
    primitives: List[Union[LineSeg, ArcSeg, CircleSeg, SplineSeg]] = []

    for stretch in stretches:
        pts = drop_duplicate_points(stretch, duplicate_tolerance)
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

        primitives.append(_fit_spline(pts, spline_degree, closed=whole_loop_as_one_stretch))

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
