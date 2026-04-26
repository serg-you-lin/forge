import ezdxf
import shutil
import numpy as np
from collections import defaultdict
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union, snap


# ---------------------------------------------------------------------------
# Utilità geometriche
# ---------------------------------------------------------------------------

def arc_endpoints(entity):
    """Restituisce (start_pt, end_pt) cartesiani di un ARC."""
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    r = entity.dxf.radius
    start_pt = (
        cx + r * np.cos(np.radians(entity.dxf.start_angle)),
        cy + r * np.sin(np.radians(entity.dxf.start_angle)),
    )
    end_pt = (
        cx + r * np.cos(np.radians(entity.dxf.end_angle)),
        cy + r * np.sin(np.radians(entity.dxf.end_angle)),
    )
    return start_pt, end_pt


def arc_to_bulge(entity, reversed=False):
    """
    Converte un ARC DXF nel bulge factor per LWPOLYLINE.
    Se reversed=True l'arco viene percorso al contrario (end->start):
      - il punto di inserimento diventa end_pt
      - il bulge viene negato
    Restituisce (entry_pt, exit_pt, bulge).
    """
    start_angle = entity.dxf.start_angle
    end_angle   = entity.dxf.end_angle
    if end_angle < start_angle:
        end_angle += 360.0
    delta = end_angle - start_angle
    bulge = np.tan(np.radians(delta) / 4.0)

    start_pt, end_pt = arc_endpoints(entity)

    if reversed:
        return end_pt, start_pt, -bulge
    else:
        return start_pt, end_pt, bulge


def arc_to_linestrings(entity, num_segments=32):
    """Approssima un ARC con segmenti (usato solo per polygonize nel fallback)."""
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    r = entity.dxf.radius
    start = np.radians(entity.dxf.start_angle)
    end   = np.radians(entity.dxf.end_angle)
    if start > end:
        end += 2 * np.pi
    angles = np.linspace(start, end, num_segments + 1)
    pts = [(cx + r * np.cos(a), cy + r * np.sin(a)) for a in angles]
    return [LineString([pts[i], pts[i + 1]]) for i in range(len(pts) - 1)]


def round_point(pt, decimals=1):
    """Quantizza un punto per confrontare nodi vicini come se fossero uguali."""
    return (round(pt[0], decimals), round(pt[1], decimals))


# ---------------------------------------------------------------------------
# Costruzione grafo topologico
# ---------------------------------------------------------------------------

def build_node_graph(msp, decimals=1):
    """
    Costruisce un grafo: nodo -> [(entità, altro_nodo)].
    I nodi sono gli estremi (quantizzati) di LINE e ARC.
    """
    graph = defaultdict(list)

    for entity in msp.query('LINE ARC'):
        if entity.dxftype() == 'LINE':
            s = round_point((entity.dxf.start.x, entity.dxf.start.y), decimals)
            e = round_point((entity.dxf.end.x,   entity.dxf.end.y),   decimals)
        else:
            s_pt, e_pt = arc_endpoints(entity)
            s = round_point(s_pt, decimals)
            e = round_point(e_pt, decimals)

        graph[s].append((entity, e))
        graph[e].append((entity, s))

    return graph


def find_closed_loops(graph):
    """
    Percorre il grafo cercando catene chiuse di entità.
    Restituisce lista di loop, dove ogni elemento è (entity, reversed).
    reversed=True significa che l'entità va percorsa dal suo end verso il suo start.
    """
    visited_edges = set()
    loops = []

    for start_node in graph:
        for (entity, next_node) in graph[start_node]:
            if id(entity) in visited_edges:
                continue

            # Determina se questa entità va percorsa in avanti o al contrario
            if entity.dxftype() == 'LINE':
                e_start = round_point((entity.dxf.start.x, entity.dxf.start.y))
            else:
                s_pt, _ = arc_endpoints(entity)
                e_start = round_point(s_pt)
            is_reversed = (e_start != start_node)

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

                # Determina direzione di attraversamento
                if next_entity.dxftype() == 'LINE':
                    ne_start = round_point((next_entity.dxf.start.x, next_entity.dxf.start.y))
                else:
                    ns_pt, _ = arc_endpoints(next_entity)
                    ne_start = round_point(ns_pt)
                # Il nodo da cui arriviamo è il "current_node precedente"
                # ovvero il nodo di uscita dell'entità precedente
                prev_node = chain[-1]
                if prev_node[0].dxftype() == 'LINE':
                    if prev_node[1]:  # reversed
                        arrive_from = round_point((prev_node[0].dxf.start.x, prev_node[0].dxf.start.y))
                    else:
                        arrive_from = round_point((prev_node[0].dxf.end.x, prev_node[0].dxf.end.y))
                else:
                    _, ep = arc_endpoints(prev_node[0])
                    sp, _ = arc_endpoints(prev_node[0])
                    arrive_from = round_point(ep if not prev_node[1] else sp)

                ne_reversed = (ne_start != arrive_from)
                chain.append((next_entity, ne_reversed))

            if current_node == start_node:
                loops.append(chain)

    return loops


# ---------------------------------------------------------------------------
# Classificazione outer / hole tramite Shapely
# ---------------------------------------------------------------------------

def classify_loops(loops):
    shapely_polygons = []
    for loop in loops:
        pts = []
        for entity, rev in loop:
            if entity.dxftype() == 'LINE':
                if rev:
                    pts.append((entity.dxf.end.x, entity.dxf.end.y))
                else:
                    pts.append((entity.dxf.start.x, entity.dxf.start.y))
            else:
                entry_pt, _, _ = arc_to_bulge(entity, reversed=rev)
                pts.append(entry_pt)
        shapely_polygons.append(Polygon(pts) if len(pts) >= 3 else None)

    outer, holes = [], []
    for i, (loop, poly) in enumerate(zip(loops, shapely_polygons)):
        if poly is None or not poly.is_valid:
            outer.append(loop)
            continue
        is_hole = any(
            j != i
            and shapely_polygons[j] is not None
            and shapely_polygons[j].contains(poly)
            for j in range(len(shapely_polygons))
        )
        holes.append(loop) if is_hole else outer.append(loop)

    return outer, holes


# ---------------------------------------------------------------------------
# Scrittura LWPOLYLINE con bulge reale
# ---------------------------------------------------------------------------

def loop_to_lwpolyline(msp, loop, layer):
    """
    Converte una catena ordinata di (entità, reversed) in una LWPOLYLINE.
    Ogni vertice ha il punto di ingresso corretto e il bulge giusto (negato se reversed).
    """
    pts_with_bulge = []

    for entity, rev in loop:
        if entity.dxftype() == 'LINE':
            if rev:
                sx, sy = entity.dxf.end.x, entity.dxf.end.y
            else:
                sx, sy = entity.dxf.start.x, entity.dxf.start.y
            pts_with_bulge.append((sx, sy, 0.0, 0.0, 0.0))
        else:  # ARC
            entry_pt, _, bulge = arc_to_bulge(entity, reversed=rev)
            pts_with_bulge.append((entry_pt[0], entry_pt[1], 0.0, 0.0, bulge))

    msp.add_lwpolyline(
        pts_with_bulge,
        format='xyseb',
        dxfattribs={'layer': layer},
        close=True,
    )


# ---------------------------------------------------------------------------
# Pipeline principale
# ---------------------------------------------------------------------------

def heal_in_place(input_path, output_path, tolerance=0.05):
    node_decimals = round(-np.log10(tolerance * 2))

    shutil.copy2(input_path, output_path)
    doc = ezdxf.readfile(output_path)
    msp = doc.modelspace()

    all_lines = list(msp.query('LINE'))
    all_arcs  = list(msp.query('ARC'))
    if not all_lines and not all_arcs:
        print("Nessun segmento trovato.")
        return

    # 1. Costruisci il grafo topologico
    graph = build_node_graph(msp, decimals=node_decimals)

    # 2. Trova i loop chiusi
    loops = find_closed_loops(graph)
    print(f"Loop chiusi trovati: {len(loops)}")

    if not loops:
        print("Nessun loop trovato via grafo, uso polygonize come fallback.")
        segments = []
        for l in all_lines:
            segments.append(LineString([
                (l.dxf.start.x, l.dxf.start.y),
                (l.dxf.end.x,   l.dxf.end.y),
            ]))
        for a in all_arcs:
            segments.extend(arc_to_linestrings(a))
        merged   = unary_union(segments)
        snapped  = snap(merged, merged, tolerance)
        polygons = list(polygonize(snapped))
        print(f"Poligoni Shapely ricostruiti: {len(polygons)}")
        for poly in polygons:
            msp.add_lwpolyline(list(poly.exterior.coords), dxfattribs={'layer': 'OuterContour'}, close=True)
            for interior in poly.interiors:
                msp.add_lwpolyline(list(interior.coords), dxfattribs={'layer': 'HEALED_HOLE'}, close=True)
        doc.save()
        print(f"Salvato in {output_path}")
        return

    # 3. Classifica outer vs hole
    outer_loops, hole_loops = classify_loops(loops)
    print(f"  Outer: {len(outer_loops)} | Holes: {len(hole_loops)}")

    # 4. Scrivi PRIMA le LWPOLYLINE (entità ancora vive nel doc)
    for loop in outer_loops:
        loop_to_lwpolyline(msp, loop, layer='OuterContour')
    for loop in hole_loops:
        loop_to_lwpolyline(msp, loop, layer='HEALED_HOLE')

    # 5. Cancella DOPO le entità originali
    entities_in_loops = {id(e) for loop in loops for e, _ in loop}
    deleted = 0
    for entity in list(msp.query('LINE ARC')):
        if id(entity) in entities_in_loops:
            msp.delete_entity(entity)
            deleted += 1
    print(f"Entità originali cancellate: {deleted}")

    doc.save()
    print(f"Salvato in {output_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    heal_in_place(
        r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\snapmark_develops\examples\input\F2.dxf",
        "healed_older_mode.dxf",
        tolerance=0.05,
    )