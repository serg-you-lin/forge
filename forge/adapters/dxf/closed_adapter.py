from typing import Optional

from ...model.shape import ClosedShape
from ...model.role import ContourRole
from .geometry_adapter import entity_to_polygon
from .virtual_adapter import DxfWriteContext


def entity_to_closed(entity, role: ContourRole = ContourRole.UNKNOWN) -> Optional[ClosedShape]:
    """
    Converte un'entità ezdxf in ClosedShape.

    `role` viene passato dall'adapter dopo la traduzione label_map → ContourRole.
    Qui non si tocca origin né label_map — questa funzione è pura geometria.
    """
    poly = entity_to_polygon(entity)
    if poly is None:
        return None

    entity_type = entity.dxftype()

    if entity_type == "CIRCLE":
        return ClosedShape(
            polygon=poly,
            source_ref=entity,
            role=role,
            shape_type="circle",
            diameter=entity.dxf.radius * 2,
            center=(entity.dxf.center.x, entity.dxf.center.y),
        )

    if entity_type in ("LWPOLYLINE", "POLYLINE"):
        return ClosedShape(
            polygon=poly,
            source_ref=entity,
            role=role,
            shape_type="polyline",
        )

    if entity_type == "SPLINE":
        return ClosedShape(
            polygon=poly,
            source_ref=entity,
            role=role,
            shape_type="spline",
        )

    if entity_type == "ELLIPSE":
        return ClosedShape(
            polygon=poly,
            source_ref=entity,
            role=role,
            shape_type="ellipse",
        )

    return None


def contour_to_closed(ctx: DxfWriteContext, role: ContourRole = ContourRole.UNKNOWN) -> ClosedShape:
    """
    Converte un DxfWriteContext (virtual shape dal core) in ClosedShape.

    Le virtual shape di solito non hanno un layer DXF — role rimane UNKNOWN
    salvo che l'adapter non lo sappia già (es. virtual outer ricostruito).
    """
    return ClosedShape(
        polygon=ctx.polygon,
        source_ref=ctx,
        role=role,
        is_virtual=True,
        shape_type="virtual",
    )