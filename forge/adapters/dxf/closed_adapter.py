from typing import Optional

from ...model.shape import ClosedShape
from .geometry_adapter import entity_to_polygon
from .virtual_adapter import DxfWriteContext


def entity_to_closed(entity) -> Optional[ClosedShape]:
    poly = entity_to_polygon(entity)
    if poly is None:
        return None

    entity_type = entity.dxftype()
    origin = entity.dxf.layer if entity.dxf.hasattr("layer") else ""

    if entity_type == "CIRCLE":
        return ClosedShape(
            polygon=poly,
            origin=origin,
            source_ref=entity,
            shape_type="circle",
            diameter=entity.dxf.radius * 2,
            center=(entity.dxf.center.x, entity.dxf.center.y),
        )

    if entity_type in ("LWPOLYLINE", "POLYLINE"):
        return ClosedShape(
            polygon=poly, origin=origin,
            source_ref=entity, shape_type="polyline",
        )

    if entity_type == "SPLINE":
        return ClosedShape(
            polygon=poly, origin=origin,
            source_ref=entity, shape_type="spline",
        )

    if entity_type == "ELLIPSE":
        return ClosedShape(
            polygon=poly, origin=origin,
            source_ref=entity, shape_type="ellipse",
        )

    return None


def contour_to_closed(ctx: DxfWriteContext) -> ClosedShape:
    return ClosedShape(
        polygon=ctx.polygon,
        origin=ctx.origin,
        source_ref=ctx,
        is_virtual=True,
        shape_type="virtual",
    )