"""
adapters/dxf/copy_adapter.py
-----------------------------
Copia entità DXF da un modelspace a un altro.

Questo modulo conosce ezdxf e scrive su msp.
Non contiene logica geometrica — solo I/O su entità DXF.

Funzioni pubbliche:
    copy_entity — copia una singola entità nel target_msp
"""

from typing import Dict, Any

_COPY_HANDLERS: Dict[str, Any] = {}


def _register_copy(*dxftypes: str):
    def decorator(fn):
        for t in dxftypes:
            _COPY_HANDLERS[t] = fn
        return fn
    return decorator


def copy_entity(entity, target_msp) -> None:
    """
    Copia una singola entità DXF nel target_msp.

    Gestisce: LINE, CIRCLE, ARC, TEXT, MTEXT, MULTILEADER, INSERT,
              LWPOLYLINE (preserva closed), SPLINE, ELLIPSE.
    Tipi non registrati vengono ignorati silenziosamente.
    """
    handler = _COPY_HANDLERS.get(entity.dxftype())
    if handler is None:
        return None
    attribs = entity.dxfattribs()
    attribs.pop('handle', None)
    attribs.pop('owner',  None)
    attribs.pop('color',  None)
    attribs.pop('true_color', None)

    try:
        return handler(entity, target_msp, attribs)  # ← return
    except Exception as ex:
        print(f"  [WARN] Copia {entity.dxftype()} fallita: {ex}")

        return None


@_register_copy('LINE')
def _copy_line(entity, msp, attribs) -> None:
    return msp.add_line(entity.dxf.start, entity.dxf.end, dxfattribs=attribs)
    


@_register_copy('CIRCLE')
def _copy_circle(entity, msp, attribs) -> None:
    return msp.add_circle(entity.dxf.center, entity.dxf.radius, dxfattribs=attribs)


@_register_copy('ARC')
def _copy_arc(entity, msp, attribs) -> None:
    return msp.add_arc(
        entity.dxf.center, entity.dxf.radius,
        entity.dxf.start_angle, entity.dxf.end_angle,
        dxfattribs=attribs,
    )


@_register_copy('TEXT')
def _copy_text(entity, msp, attribs) -> None:
    return msp.add_text(entity.dxf.text, dxfattribs=attribs)


@_register_copy('MTEXT')
def _copy_mtext(entity, msp, attribs) -> None:
    return msp.add_mtext(entity.text, dxfattribs=attribs)


@_register_copy('MULTILEADER')
def _copy_multileader(entity, msp, attribs) -> None:
    try:
        msp.doc.entitydb
        new_entity = entity.copy()
        msp.add_entity(new_entity)
    except Exception as ex:
        print(f"  [WARN] Copia MULTILEADER fallita: {ex}")


@_register_copy('INSERT')
def _copy_insert(entity, msp, attribs) -> None:
    return msp.add_blockref(entity.dxf.name, entity.dxf.insert, dxfattribs=attribs)


@_register_copy('LWPOLYLINE')
def _copy_lwpolyline(entity, msp, attribs) -> None:
    pts = list(entity.get_points(format='xyseb'))
    return msp.add_lwpolyline(pts, format='xyseb', dxfattribs=attribs, close=entity.closed)


@_register_copy('POLYLINE')
def _copy_polyline(entity, msp, attribs) -> None:
    pts = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
    safe_attribs = {k: v for k, v in attribs.items() if k in ('layer', 'linetype', 'lineweight')}
    return msp.add_lwpolyline(pts, dxfattribs=safe_attribs, close=entity.is_closed)

@_register_copy('SPLINE')
def _copy_spline(entity, msp, attribs) -> None:
    new_entity = entity.copy()
    new_entity.dxf.layer = attribs.get('layer', entity.dxf.layer)
    new_entity.dxf.color = attribs.get('color', entity.dxf.color)
    return msp.add_entity(new_entity)


@_register_copy('ELLIPSE')
def _copy_ellipse(entity, msp, attribs) -> None:
    return msp.add_ellipse(
        entity.dxf.center,
        entity.dxf.major_axis,
        entity.dxf.ratio,
        entity.dxf.start_param,
        entity.dxf.end_param,
        dxfattribs=attribs,
    )
