"""
adapters/dxf/bending_adapter.py
--------------------------------
Costruzione di BendingLine da OpenShape con source_ref LINE ezdxf.

Unico punto del progetto che conosce la struttura interna di un'entità
LINE ezdxf per produrre una BendingLine core.
"""

import math

from shapely.geometry import LineString

from ...model.shape import OpenShape
from ...model import BendingLine


def bending_line_from_proxy(proxy: OpenShape, part_label: str) -> BendingLine:
    """
    Costruisce una BendingLine da un proxy con shape_type == "line".

    Args:
        proxy:      OpenShape con source_ref entità LINE ezdxf
        part_label: label del ForgePart contenitore
    """
    entity = proxy.source_ref
    geom   = LineString([
        (entity.dxf.start.x, entity.dxf.start.y),
        (entity.dxf.end.x,   entity.dxf.end.y),
    ])
    return BendingLine(
        source_ref=entity,
        geometry=geom,
        length=geom.length,
        angle_deg=math.degrees(math.atan2(
            entity.dxf.end.y - entity.dxf.start.y,
            entity.dxf.end.x - entity.dxf.start.x,
        )) % 180,
        part_label=part_label,
    )
