"""
forge/tools/hole_detector.py
----------------------------
Rileva fori filettati e svasature da primitive geometriche pure.

    is_threaded_hole     — True se il cerchio è un foro filettato
    is_countersink_outer — True se il cerchio è il cerchio esterno di svasatura

Euristiche di riconoscimento usate solo da ``detect()`` — non geometria di base
riusabile, quindi vivono qui accanto al loro unico consumatore e non in
``core/`` (MAP.md D25). Zero dipendenze da formato — lavora su ArcSeg e tuple
(x, y).
"""

import math
from typing import Tuple

from forge.core.primitives.segments import ArcSeg
from forge.rules.thresholds import THREADED_ARC_MAX_RADIUS_RATIO


def is_threaded_hole(
    center:           Tuple[float, float],
    radius:           float,
    all_arcs:         list[ArcSeg],
    tolerance_center: float = 1.0,
    angle_tolerance:  float = 35.0,
    max_radius_ratio: float = THREADED_ARC_MAX_RADIUS_RATIO,
) -> bool:
    """
    True se esiste un arco a ~270° concentrico al cerchio e con raggio di poco
    maggiore (anello di cresta della filettatura).

    L'arco deve essere concentrico entro ``tolerance_center``, avere angolo
    swept ~270° entro ``angle_tolerance`` e raggio compreso tra ``radius`` e
    ``radius * max_radius_ratio``. Il vincolo sul rapporto dei raggi esclude i
    falsi positivi in cui un arco molto più grande passa vicino al foro — il
    bordo esterno di una flangia tonda scantonata, l'estremità raggiata di un
    profilo: geometrie che circondano il foro ma non sono anelli filettati.

    Args:
        center:           centro del cerchio (x, y)
        radius:           raggio del cerchio
        all_arcs:         tutti gli archi del documento come ArcSeg
        tolerance_center: distanza massima tra centri (mm)
        angle_tolerance:  tolleranza sull'angolo swept (gradi)
        max_radius_ratio: rapporto massimo arc.radius / radius ammesso
    """
    # Converte tolleranza da gradi a radianti
    angle_tolerance_rad = math.radians(angle_tolerance)
    target_swept = math.radians(270)  # 270 gradi in radianti
    max_arc_radius = radius * max_radius_ratio

    for arc in all_arcs:
        # Calcola angolo swept in radianti
        swept = (arc.end_angle - arc.start_angle) % (2 * math.pi)

        # Verifica se è circa 270 gradi
        if (
            abs(swept - target_swept) < angle_tolerance_rad
            and radius < arc.radius <= max_arc_radius
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