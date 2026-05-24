"""
graph.py
--------
Costruisce il grafo topologico delle entità DXF e trova i loop chiusi.

Il grafo modella LINE/ARC/SPLINE come archi tra i loro endpoint arrotondati.
Ogni nodo è un punto (x, y) arrotondato a `decimals` cifre decimali.
Ogni arco è una tupla (entity, nodo_opposto).

Funzioni pubbliche:
  build_node_graph     — costruisce il grafo da un modelspace ezdxf
  find_closed_loops    — trova tutti i loop chiusi nel grafo
  classify_loops       — classifica i loop in outer e inner
  check_loop_ambiguity — rileva nodi con più di 2 connessioni
  entity_endpoints     — restituisce (start, end) di un'entità
  round_point          — arrotonda un punto a `decimals` decimali
  spline_to_points     — discretizza una SPLINE in lista di punti
  spline_endpoints     — restituisce (start, end) di una SPLINE
  arc_to_bulge         — converte un ARC in (entry_point, bulge, exit_point)
"""

import math
from collections import defaultdict
from shapely.geometry import Polygon, LinearRing

from .geometry import arc_endpoints, arc_to_bulge, round_point, spline_to_points

# ---------------------------------------------------------------------------
# Helpers — endpoint
# ---------------------------------------------------------------------------

_SUPPORTED_TYPES = frozenset({'LINE', 'ARC', 'SPLINE'})


def spline_endpoints(spline):
    """
    Restituisce (start, end) di una SPLINE come tuple (x, y).
    Restituisce (None, None) se non riesce.
    """
    try:
        pts = list(spline.flattening(0.01))
        if len(pts) < 2:
            return None, None
        return (pts[0][0], pts[0][1]), (pts[-1][0], pts[-1][1])
    except Exception:
        return None, None


def entity_endpoints(entity):
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
        return spline_endpoints(entity)
    return None, None


def _normalized_endpoints(entity, decimals):
    """
    Single entry point per ottenere gli endpoint normalizzati di un'entità.
    Restituisce (None, None) se il tipo non è supportato o il calcolo fallisce.
    """
    if entity.dxftype() not in _SUPPORTED_TYPES:
        return None, None
    s, e = entity_endpoints(entity)
    if s is None or e is None:
        return None, None
    return round_point(s, decimals), round_point(e, decimals)


# ---------------------------------------------------------------------------
# Costruzione grafo
# ---------------------------------------------------------------------------

def build_node_graph(msp, decimals=1, exclude_layers=None):
    """
    Costruisce il grafo topologico degli endpoint di LINE/ARC/SPLINE.
    Nodi = endpoint arrotondati, archi = entità.

    Args:
        msp:            modelspace ezdxf
        decimals:       cifre decimali per arrotondamento nodi
        exclude_layers: set di nomi layer (lowercase) da escludere dal grafo
    """
    exclude_layers = set(exclude_layers or [])

    def _is_excluded(entity):
        if not exclude_layers:
            return False
        layer = entity.dxf.layer.lower() if entity.dxf.hasattr('layer') else ''
        return any(sl in layer for sl in exclude_layers)

    graph = defaultdict(list)

    for entity in msp:
        if _is_excluded(entity):
            continue
        s, e = _normalized_endpoints(entity, decimals)
        if s is None:
            continue
        graph[s].append((entity, e))
        graph[e].append((entity, s))

    return graph


# ---------------------------------------------------------------------------
# Ricerca loop
# ---------------------------------------------------------------------------

def find_closed_loops(graph):
    """
    Trova tutti i loop chiusi nel grafo.
    Restituisce lista di loop, ognuno come lista di (entity, is_reversed).

    Strategia:
    - visited_edges è condiviso tra tutte le iterazioni: ogni entità
      entra in al massimo un loop (come nella versione originale).
    - Dopo aver trovato un loop, corregge l'orientamento: se il poligono
      è CW (orario), inverte la chain per renderlo CCW (antiorario).
      Questo garantisce che classify_loops riceva sempre loop con
      orientamento consistente, indipendentemente dalla direzione
      scelta dall'algoritmo greedy.
    """
    visited_edges = set()
    loops = []

    for start_node in graph:
        for (entity, next_node) in graph[start_node]:
            if id(entity) in visited_edges:
                continue

            e_start, e_end = entity_endpoints(entity)
            if e_start is None:
                continue
            is_reversed = (round_point(e_start) != start_node)

            chain = [(entity, is_reversed)]
            visited_edges.add(id(entity))
            current_node = next_node

            while current_node != start_node:
                candidates = [
                    (e, n) for (e, n) in graph[current_node]
                    if id(e) not in visited_edges
                ]
                if not candidates:
                    break
                next_entity, current_node = candidates[0]
                visited_edges.add(id(next_entity))

                ne_start, _ = entity_endpoints(next_entity)
                if ne_start is None:
                    break
                prev_entity, prev_rev = chain[-1]
                prev_s, prev_e = entity_endpoints(prev_entity)
                if prev_s is None:
                    break
                arrive_from = round_point(prev_s if prev_rev else prev_e)
                ne_reversed = (round_point(ne_start) != arrive_from)
                chain.append((next_entity, ne_reversed))

            if current_node != start_node:
                continue

            # Corregge orientamento: se CW, inverti → sempre CCW
            pts = []
            for e, rev in chain:
                if e.dxftype() == 'LINE':
                    pts.append(
                        (e.dxf.end.x, e.dxf.end.y) if rev
                        else (e.dxf.start.x, e.dxf.start.y)
                    )
                elif e.dxftype() == 'ARC':
                    entry_pt, _, _ = arc_to_bulge(e, reversed=rev)
                    pts.append(entry_pt)
            if len(pts) >= 3:
                try:
                    if not LinearRing(pts).is_ccw:
                        chain = [(e, not rev) for e, rev in reversed(chain)]
                except Exception:
                    pass

            loops.append(chain)

    return loops


# ---------------------------------------------------------------------------
# Classificazione loop
# ---------------------------------------------------------------------------

def classify_loops(loops):
    """
    Classifica i loop in outer e inner usando Shapely contains.

    Un loop è inner se è contenuto dentro un altro loop.
    Tutti gli altri sono outer.
    Loop non validi (< 3 punti, geometria degenere) vanno in outer.
    """
    shapely_polygons = []
    for loop in loops:
        pts = []
        for entity, rev in loop:
            if entity.dxftype() == 'LINE':
                pts.append(
                    (entity.dxf.end.x, entity.dxf.end.y) if rev
                    else (entity.dxf.start.x, entity.dxf.start.y)
                )
            elif entity.dxftype() == 'ARC':
                entry_pt, _, _ = arc_to_bulge(entity, reversed=rev)
                pts.append(entry_pt)
            elif entity.dxftype() == 'SPLINE':
                spline_pts = spline_to_points(entity)
                if rev:
                    spline_pts = list(reversed(spline_pts))
                pts.extend(spline_pts)
        shapely_polygons.append(Polygon(pts) if len(pts) >= 3 else None)

    outer, inners = [], []
    for i, (loop, poly) in enumerate(zip(loops, shapely_polygons)):
        if poly is None or not poly.is_valid:
            outer.append(loop)
            continue
        is_inner = any(
            j != i
            and shapely_polygons[j] is not None
            and shapely_polygons[j].contains(poly)
            for j in range(len(shapely_polygons))
        )
        inners.append(loop) if is_inner else outer.append(loop)

    return outer, inners


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def check_loop_ambiguity(loops, graph):
    """
    Restituisce i nodi che hanno più di 2 connessioni all'interno
    dei loop trovati — indicatori di geometria ambigua.
    """
    loop_entity_ids = {id(e) for loop in loops for e, _ in loop}
    branching = []
    for node, connections in graph.items():
        loop_connections = [
            (e, n) for (e, n) in connections
            if id(e) in loop_entity_ids
        ]
        if len(loop_connections) > 2:
            branching.append(node)
    return branching