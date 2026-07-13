
"""
adapters/dxf/hole_detector.py
---------------------------------
Rileva fori filettati e svasature in entità DXF.

    is_threaded_arc         — True se l'arco descrive un filetto
    is_threaded_hole        — True se il cerchio è foro filettato
    is_countersink_outer    — True se il cerchio è il cerchio esterno di svasatura
    free_endpoints_from_msp — endpoint liberi nel grafo
"""
import math
import numpy as np

def is_threaded_arc(arc, angle_tolerance: float = 35.0) -> bool:
    if arc.dxftype() != 'ARC':
        return False
    start = arc.dxf.start_angle
    end   = arc.dxf.end_angle
    swept = (end - start) % 360
    return abs(swept - 270) < angle_tolerance


def is_threaded_hole(circle, all_arcs, tolerance_center: float = 1.0) -> bool:
    cx = circle.dxf.center.x
    cy = circle.dxf.center.y
    for arc in all_arcs:
        dist = np.hypot(cx - arc.dxf.center.x, cy - arc.dxf.center.y)
        if (dist < tolerance_center
                and arc.dxf.radius > circle.dxf.radius
                and is_threaded_arc(arc)):
            return True
    return False


def is_countersink_outer(circle, siblings: list, tolerance: float = 1.0) -> bool:
    """
    Restituisce True se `circle` è il cerchio esterno di una svasatura.

    Una svasatura è composta da due cerchi concentrici (stesso centro,
    raggi diversi). Il cerchio esterno contiene il cerchio interno.

    Args:
        circle:    entità CIRCLE ezdxf da testare
        siblings:  lista di ForgeContour con .entity popolato
        tolerance: distanza massima tra centri per considerarli concentrici (mm)
    """
    cx = circle.dxf.center.x
    cy = circle.dxf.center.y
    cr = circle.dxf.radius
    for sibling in siblings:
        other = sibling.entity
        if other is None or other.dxftype() != 'CIRCLE' or other is circle:
            continue
        if other.dxf.radius >= cr:
            continue
        if np.hypot(cx - other.dxf.center.x, cy - other.dxf.center.y) < tolerance:
            return True
    return False