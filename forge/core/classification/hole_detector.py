
"""
core/classification/hole_detector.py
-------------------------------
Rileva fori filettati e svasature da primitive geometriche pure.

    is_threaded_hole     — True se il cerchio è un foro filettato
    is_countersink_outer — True se il cerchio è il cerchio esterno di svasatura

Zero dipendenze da formato — lavora su CircularArcSeg e tuple (x, y).
"""

import math
from typing import Optional, Tuple

from forge.core.primitives.segments import CircularArcSeg


def is_threaded_hole(
    center:           Tuple[float, float],
    radius:           float,
    all_arcs:         list[CircularArcSeg],
    tolerance_center: float = 1.0,
    angle_tolerance:  float = 35.0,
) -> bool:
    """
    True se esiste un arco a ~270° concentrico al cerchio e con raggio maggiore.

    Args:
        center:           centro del cerchio (x, y)
        radius:           raggio del cerchio
        all_arcs:         tutti gli archi del documento come CircularArcSeg
        tolerance_center: distanza massima tra centri (mm)
        angle_tolerance:  tolleranza sull'angolo swept (gradi)
    """
    for arc in all_arcs:
        swept = (arc.end_angle - arc.start_angle) % 360
        if (
            abs(swept - 270) < angle_tolerance
            and arc.radius > radius
            and math.hypot(center[0] - arc.center[0], center[1] - arc.center[1]) < tolerance_center
        ):
            return True
    return False


def is_countersink_outer(
    center:    Tuple[float, float],
    radius:    float,
    siblings:  list[Tuple[Tuple[float, float], float]],
    tolerance: float = 1.0,
) -> bool:
    """
    True se esiste un cerchio concentrico con raggio minore (svasatura).

    Args:
        center:    centro del cerchio da testare (x, y)
        radius:    raggio del cerchio da testare
        siblings:  lista di (center, radius) dei cerchi candidati
        tolerance: distanza massima tra centri (mm)
    """
    for other_center, other_radius in siblings:
        if other_radius >= radius:
            continue
        if math.hypot(center[0] - other_center[0], center[1] - other_center[1]) < tolerance:
            return True
    return False