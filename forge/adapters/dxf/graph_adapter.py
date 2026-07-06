
"""
adapters/dxf/graph_adapter.py
------------------------------
Traduce entità DXF grezze in Edge topologici.

Unico punto del progetto che conosce sia ezdxf che il modello Edge.
Il core (graph.py) non sa nulla di DXF — riceve solo Edge.

Funzioni pubbliche:
    edges_from_msp — produce list[Edge] da un modelspace ezdxf
"""

import numpy as np
from shapely.geometry import LineString

from ...model.edge import Edge
from ...core.geometry import round_point
from .geometry_adapter import arc_endpoints

# ---------------------------------------------------------------------------
# Tipi supportati — solo entità con due endpoint distinti
# ---------------------------------------------------------------------------

_SUPPORTED_TYPES = frozenset({'LINE', 'ARC', 'SPLINE'})


# ---------------------------------------------------------------------------
# Endpoint DXF → tuple Python
# ---------------------------------------------------------------------------

def _spline_endpoints(spline):
    try:
        pts = list(spline.flattening(0.01))
        if len(pts) < 2:
            return None, None
        return (pts[0][0], pts[0][1]), (pts[-1][0], pts[-1][1])
    except Exception:
        return None, None


def _entity_endpoints(entity):
    """
    Restituisce (start, end) come tuple (x, y) per LINE, ARC, SPLINE.
    Restituisce (None, None) per tipi non supportati.
    """
    t = entity.dxftype()
    if t == 'LINE':
        return (
            (entity.dxf.start.x, entity.dxf.start.y),
            (entity.dxf.end.x,   entity.dxf.end.y),
        )
    if t == 'ARC':
        return arc_endpoints(entity)
    if t == 'SPLINE':
        return _spline_endpoints(entity)
    return None, None


# alias pubblico usato da geometry_adapter per spline_endpoints
entity_endpoints = _entity_endpoints


def _normalized_endpoints(entity, decimals):
    """
    Endpoint arrotondati alla tolerance — chiave dei nodi nel grafo.
    Restituisce (None, None) se il tipo non è supportato o gli endpoint
    non sono calcolabili.
    """
    if entity.dxftype() not in _SUPPORTED_TYPES:
        return None, None
    s, e = _entity_endpoints(entity)
    if s is None or e is None:
        return None, None
    return round_point(s, decimals), round_point(e, decimals)


# ---------------------------------------------------------------------------
# Geometry — approssimazione LineString per il core topologico
# ---------------------------------------------------------------------------

def _entity_to_linestring(entity) -> LineString:
    """
    Produce una LineString shapely dall'entità DXF.
    Usata dal core per classificazione e loop detection — mai per writeback.

    LINE   → segmento diretto
    ARC    → poligonale approssimata (32 segmenti)
    SPLINE → flattening ezdxf
    """
    t = entity.dxftype()

    if t == 'LINE':
        return LineString([
            (entity.dxf.start.x, entity.dxf.start.y),
            (entity.dxf.end.x,   entity.dxf.end.y),
        ])

    if t == 'ARC':
        import numpy as np
        cx, cy = entity.dxf.center.x, entity.dxf.center.y
        r      = entity.dxf.radius
        start  = np.radians(entity.dxf.start_angle)
        end    = np.radians(entity.dxf.end_angle)
        if start > end:
            end += 2 * np.pi
        angles = np.linspace(start, end, 33)
        pts = [(cx + r * np.cos(a), cy + r * np.sin(a)) for a in angles]
        return LineString(pts)

    if t == 'SPLINE':
        try:
            pts = [(p[0], p[1]) for p in entity.flattening(0.01)]
            if len(pts) >= 2:
                return LineString(pts)
        except Exception:
            pass

    # fallback: segmento diretto tra i due endpoint
    s, e = _entity_endpoints(entity)
    if s and e:
        return LineString([s, e])
    return LineString([(0, 0), (0, 0)])


# ---------------------------------------------------------------------------
# Funzione pubblica
# ---------------------------------------------------------------------------

def edges_from_msp(msp, node_decimals, exclude_ids=None, ignore_layers=None) -> list:
    """
    Produce la lista di Edge topologici da un modelspace ezdxf.

    Parametri:
        msp           : modelspace ezdxf
        node_decimals : cifre decimali per l'arrotondamento dei nodi
        exclude_ids   : set di id() di entità da escludere
        ignore_layers : set di nomi layer (lowercase) da ignorare

    Restituisce:
        list[Edge] — pronti per build_node_graph()
    """
    exclude_ids   = set(exclude_ids   or [])
    ignore_layers = set(ignore_layers or [])

    def _is_excluded(entity):
        if id(entity) in exclude_ids:
            return True
        if not ignore_layers:
            return False
        layer = entity.dxf.layer.lower() if entity.dxf.hasattr('layer') else ''
        return any(sl in layer for sl in ignore_layers)

    edges = []
    for entity in msp:
        if _is_excluded(entity):
            continue
        s, e = _normalized_endpoints(entity, node_decimals)
        if s is None:
            continue
        layer    = entity.dxf.layer if entity.dxf.hasattr('layer') else ''
        geometry = _entity_to_linestring(entity)
        edges.append(Edge(entity=entity, layer=layer, start=s, end=e, geometry=geometry))

    return edges