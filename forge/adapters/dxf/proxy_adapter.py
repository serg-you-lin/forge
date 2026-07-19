from typing import Optional

from ...model.shape_proxy import ShapeProxy
from .geometry_adapter import entity_to_polygon
from .virtual_adapter import DxfWriteContext


def entity_to_proxy(entity) -> Optional[ShapeProxy]:
    """
    Converte un'entità ezdxf chiusa in ShapeProxy.

    Supporta CIRCLE, LWPOLYLINE, POLYLINE, SPLINE ed ELLIPSE.
    Restituisce None se la geometria non è calcolabile o il tipo non è supportato.
    """
    poly = entity_to_polygon(entity)
    if poly is None:
        return None

    entity_type = entity.dxftype()

    if entity_type == "CIRCLE":
        return ShapeProxy(
            polygon=poly,
            origin=entity.dxf.layer if entity.dxf.hasattr("layer") else "",
            source_ref=entity,
            diameter=entity.dxf.radius * 2,
            center=(entity.dxf.center.x, entity.dxf.center.y),
        )

    # if entity_type == "CIRCLE":
    #     return ShapeProxy(
    #         polygon=poly,
    #         origin=entity.dxf.layer if entity.dxf.hasattr("layer") else "",
    #         shape_type="circle",
    #         source_ref=entity,
    #         diameter=entity.dxf.radius * 2,
    #         center=(entity.dxf.center.x, entity.dxf.center.y),
    #     )


    # Explicit type matching instead of substring matching.
    # During refactoring, the previous `"PLINE" in entity_type` check behaved
    # unexpectedly for LWPOLYLINE even though entity_type was a normal str.
    # Keep this explicit to avoid relying on substring detection.

    if entity_type in ("LWPOLYLINE", "POLYLINE"):
        return ShapeProxy(
            polygon=poly,
            origin=entity.dxf.layer if entity.dxf.hasattr("layer") else "",
            source_ref=entity,
        )

    if entity_type == "SPLINE":
        return ShapeProxy(
            polygon=poly,
            origin=entity.dxf.layer if entity.dxf.hasattr("layer") else "",
            source_ref=entity,
        )

    if entity_type == "ELLIPSE":
        return ShapeProxy(
            polygon=poly,
            origin=entity.dxf.layer if entity.dxf.hasattr("layer") else "",
            source_ref=entity,
        )

    # if entity_type in ("LWPOLYLINE", "POLYLINE"):
    #     return ShapeProxy(
    #         polygon=poly,
    #         origin=entity.dxf.layer if entity.dxf.hasattr("layer") else "",
    #         shape_type="polyline",
    #         source_ref=entity,
    #     )

    # if entity_type == "SPLINE":
    #     return ShapeProxy(
    #         polygon=poly,
    #         origin=entity.dxf.layer if entity.dxf.hasattr("layer") else "",
    #         shape_type="spline",
    #         source_ref=entity,
    #     )
    
    # if entity_type == "ELLIPSE":
    #     return ShapeProxy(
    #         polygon=poly,
    #         origin=entity.dxf.layer if entity.dxf.hasattr("layer") else "",
    #         shape_type="ellipse",
    #         source_ref=entity,
    #     )

    return None


def contour_to_proxy(ctx: DxfWriteContext) -> ShapeProxy:
    """
    Converte un DxfWriteContext (loop ricostruito dall'healing) in ShapeProxy.

    Non ha mai diameter/center — un contour ricostruito da LINE+ARC
    non è mai un cerchio.
    """
    return ShapeProxy(
        polygon=ctx.contour.polygon,
        origin=ctx.contour.origin,
        source_ref=ctx,
        is_virtual=True,
    )

