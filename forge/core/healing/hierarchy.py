
# forge/core/healing/hierarchy.py

from typing import Optional
from shapely.geometry import Polygon

from ...model.shape import ClosedShape
from ...model.part import ForgePart, ForgeContour
from ...model.hole import Hole, HOLE_TYPE_UNKNOWN
from ...model.role import ContourRole, layer_to_role
from ...rules.thresholds import HOLE_DIAMETER_THRESHOLD
from forge.adapters.dxf.layers import LAYER_OUTER, LAYER_INNER, LAYER_HOLE, color_for_layer
from forge.adapters.dxf.virtual_adapter import _loop_to_contour


# ---------------------------------------------------------------------------
# Conversione loop → ClosedShape (ex closed_adapter)
# ---------------------------------------------------------------------------

def loop_to_closed_shape(loop, role: ContourRole = ContourRole.UNKNOWN, ctx=None) -> Optional[ClosedShape]:
    """
    Converte un loop (lista di (Edge, bool)) in ClosedShape.

    ctx : DxfWriteContext associato al loop, se disponibile — usato come
          source_ref/vs_id quando il loop richiede materializzazione
          (più entità fuse, o singola LINE/ARC che verrà rimossa da
          _remove_superseded_line_arc). Per un loop degenere composto da
          una singola entità "durevole" (CIRCLE, SPLINE chiusa, POLYLINE/
          LWPOLYLINE chiusa) — mai toccata da _remove_superseded_line_arc —
          si mantiene invece il riferimento diretto all'entità originale,
          che resta valido per tutto il ciclo di vita di write()/split().
    """
    from shapely.geometry import Polygon
    from ...core.topology.loop_finder import LoopFinder

    # ctx.polygon (quando disponibile) è già ricostruito da parse_loop()/
    # build_polygon() con la geometria esatta degli archi (bulge analitico).
    # LoopFinder._loop_to_points() usa invece edge.geometry, un'approssimazione
    # a campionamento fisso pensata SOLO per la topologia (loop detection) —
    # riusarla qui produrrebbe un'area leggermente diversa da quella scritta
    # su DXF in write(). Ricostruire da zero solo se ctx non è disponibile.
    if ctx is not None and getattr(ctx, "polygon", None) is not None:
        poly = ctx.polygon
    else:
        pts = LoopFinder._loop_to_points(loop)
        if len(pts) < 3:
            return None
        poly = Polygon(pts)

    try:
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            return None

        first_ref  = loop[0][0].source_ref if loop else None
        first_type = getattr(first_ref, "dxftype", lambda: None)()
        is_durable = (
            len(loop) == 1
            and first_ref is not None
            and first_type not in ("LINE", "ARC")
        )
        source_ref = first_ref if is_durable else ctx

        # diameter/center hanno senso solo per un vero cerchio (CIRCLE) —
        # un loop composito (più LINE/ARC assemblati) non è un cerchio anche
        # se la sua bbox è piccola: usare la bbox come "diametro" farebbe
        # classificare come Hole qualunque sagoma piccola invece di Inner.
        is_circle = len(loop) == 1 and first_type == "CIRCLE"
        diameter = None
        center = None
        if is_circle:
            minx, miny, maxx, maxy = poly.bounds
            diameter = min(maxx - minx, maxy - miny)
            center = ((minx + maxx) / 2, (miny + maxy) / 2)

        return ClosedShape(
            polygon=poly,
            diameter=diameter,
            center=center,
            source_ref=source_ref,
            role=role,
            is_virtual=not is_durable,
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Classificazione proxy — agnostica, zero accessi a source_ref
# ---------------------------------------------------------------------------

def _place(proxy: ClosedShape, nodes: list) -> bool:
    for node in nodes:
        if node[0].polygon.contains(proxy.polygon):
            if not _place(proxy, node[1]):
                node[1].append([proxy, []])
            return True
    return False


def _build_tree(proxies: list[ClosedShape]) -> list:
    # Arrotondare la chiave di sort evita che forme congruenti (es. fori
    # identici a coordinate diverse) vengano riordinate in modo instabile
    # per via del solo rumore in virgola mobile dell'area (shoelace non è
    # invariante per traslazione oltre la 12a-13a cifra significativa) —
    # sort() è stabile: a parità di area arrotondata, l'ordine di
    # attraversamento originale viene preservato.
    proxies_sorted = sorted(proxies, key=lambda p: round(p.polygon.area, 6), reverse=True)
    roots = []
    for proxy in proxies_sorted:
        if not _place(proxy, roots):
            roots.append([proxy, []])
    return roots


# ---------------------------------------------------------------------------
# Costruzione semantica
# ---------------------------------------------------------------------------

def _proxy_origin(proxy: ClosedShape) -> str:
    """
    Layer DXF di provenienza per un proxy virtuale (loop di più entità
    fuse) — letto dal DxfWriteContext (proxy.source_ref quando is_virtual)
    prima che hierarchy azzeri source_ref su Hole/ForgeContour.
    """
    if not proxy.is_virtual:
        return ""
    return getattr(proxy.source_ref, "origin", "") or ""


def _make_hole(proxy: ClosedShape, geometric_hint: str = "",
               outer_proxy: Optional[ClosedShape] = None) -> Hole:
    role = proxy.role if proxy.role != ContourRole.UNKNOWN else (
        ContourRole.HOLE if proxy.diameter < HOLE_DIAMETER_THRESHOLD else ContourRole.INNER
    )
    is_virtual = proxy.is_virtual
    return Hole(
        polygon=proxy.polygon,
        diameter=proxy.diameter,
        center=proxy.center,
        hole_type=HOLE_TYPE_UNKNOWN,
        geometric_hint=geometric_hint,
        role=role,
        source_ref=proxy.source_ref if not is_virtual else None,
        vs_id=id(proxy.source_ref) if is_virtual else None,
        origin=_proxy_origin(proxy),
        outer_diameter=outer_proxy.diameter if outer_proxy else None,
        outer_source_ref=outer_proxy.source_ref if outer_proxy and not outer_proxy.is_virtual else None,
    )


def _make_inner(proxy: ClosedShape, parent_role: ContourRole = ContourRole.UNKNOWN) -> ForgeContour:
    is_virtual = proxy.is_virtual
    role = proxy.role if proxy.role not in (ContourRole.UNKNOWN, ContourRole.INNER) else \
           parent_role if parent_role not in (ContourRole.UNKNOWN, ContourRole.INNER) else \
           ContourRole.INNER
    return ForgeContour(
        polygon=proxy.polygon,
        role=role,
        source_ref=proxy.source_ref if not is_virtual else None,
        vs_id=id(proxy.source_ref) if is_virtual else None,
        origin=_proxy_origin(proxy),
    )


def _process_children(children: list, holes: list, inners: list,
                      classified_virtual_ids: set, classified_entity_ids: set,
                      parent_role: ContourRole = ContourRole.UNKNOWN):
    for child_node in children:
        child_proxy, grandchildren = child_node

        if grandchildren:
            _register(child_proxy, classified_virtual_ids, classified_entity_ids)

            for gc_node in grandchildren:
                gc_proxy, _ = gc_node

                if gc_proxy.diameter is not None:
                    holes.append(_make_hole(
                        gc_proxy,
                        geometric_hint="countersink",
                        outer_proxy=child_proxy,
                    ))
                else:
                    inners.append(_make_inner(gc_proxy, parent_role=parent_role))

                _register(gc_proxy, classified_virtual_ids, classified_entity_ids)

        else:
            is_hole = child_proxy.diameter is not None
            if is_hole:
                obj = _make_hole(child_proxy)
                holes.append(obj)
            else:
                obj = _make_inner(child_proxy, parent_role=parent_role)
                inners.append(obj)

            _register(child_proxy, classified_virtual_ids, classified_entity_ids)

            if child_proxy.is_virtual:
                from ...adapters.dxf.layers import ROLE_TO_LAYER
                default_layer = LAYER_HOLE if is_hole else LAYER_INNER
                assigned_layer = ROLE_TO_LAYER.get(obj.role, default_layer)
                try:
                    child_proxy.source_ref.layer = assigned_layer
                    child_proxy.source_ref.color = color_for_layer(assigned_layer)
                except Exception:
                    pass


def _register(proxy: ClosedShape, classified_virtual_ids: set,
              classified_entity_ids: set):
    if proxy.is_virtual:
        classified_virtual_ids.add(id(proxy.source_ref))
    else:
        classified_entity_ids.add(id(proxy.source_ref))


def _collect_entity_ids(father_proxy: ClosedShape, children: list) -> set:
    ids = {id(father_proxy.source_ref)}
    for child_proxy, grandchildren in children:
        ids.add(id(child_proxy.source_ref))
        for gc_proxy, _ in grandchildren:
            ids.add(id(gc_proxy.source_ref))
    return ids


# ---------------------------------------------------------------------------
# Entry point — monkey-patched su HealStep
# ---------------------------------------------------------------------------

def _build_hierarchy(self):
    from ...core.topology.loop_finder import edges_to_open_shapes

    # Converti virtual_shapes in ClosedShape
    virtual_proxies = []
    for ctx in self.result._virtual_shapes:
        # Edge.layer è già una stringa cached — zero accessi a source_ref.dxf
        loop_layer = ctx.loop[0][0].layer if ctx.loop else ""
        role = layer_to_role(loop_layer, self.result.label_map)
        shape = loop_to_closed_shape(ctx.loop, role=role, ctx=ctx)
        if shape is not None:
            virtual_proxies.append(shape)

    open_proxies = edges_to_open_shapes(
        self.adapter.to_edges(),
        exclude_ids=self.entities_in_loops,
        label_map=self.result.label_map,
    )

    self._all_proxies = virtual_proxies + open_proxies
    proxies = [p for p in self._all_proxies if hasattr(p, 'polygon') and p.polygon is not None]

    if not proxies:
        self.result.errors.append("Nessuna geometria chiusa trovata dopo healing.")
        self.result.is_valid = False
        return

    tree = _build_tree(proxies)

    for root_node in tree:
        father_proxy, children = root_node

        outer = ForgeContour(
            polygon=father_proxy.polygon,
            role=ContourRole.OUTER,
            source_ref=father_proxy.source_ref if not father_proxy.is_virtual else None,
            vs_id=id(father_proxy.source_ref) if father_proxy.is_virtual else None,
            origin=_proxy_origin(father_proxy),
        )

        _register(father_proxy, self.classified_virtual_ids, self.classified_entity_ids)

        if father_proxy.is_virtual:
            father_proxy.source_ref.layer = LAYER_OUTER
            father_proxy.source_ref.color = color_for_layer(LAYER_OUTER)

        holes  = []
        inners = []

        _process_children(
            children, holes, inners,
            self.classified_virtual_ids, self.classified_entity_ids,
            parent_role=father_proxy.role,
        )

        entity_ids = _collect_entity_ids(father_proxy, children)
        for hole in holes:
            if hole.source_ref is not None:
                entity_ids.add(id(hole.source_ref))
            if hole.outer_source_ref is not None:
                entity_ids.add(id(hole.outer_source_ref))
        for inner in inners:
            if inner.source_ref is not None:
                entity_ids.add(id(inner.source_ref))

        part = ForgePart(
            outer=outer,
            holes=holes,
            inners=inners,
            label=self.label,
            source_file=self.source_file,
            custom={},
            entity_ids=entity_ids,
        )

        if father_proxy.is_virtual:
            self.result._vs_to_part[id(father_proxy.source_ref)] = part
        for child_proxy, grandchildren in children:
            if child_proxy.is_virtual:
                self.result._vs_to_part[id(child_proxy.source_ref)] = part
            for gc_proxy, _ in grandchildren:
                if gc_proxy.is_virtual:
                    self.result._vs_to_part[id(gc_proxy.source_ref)] = part

        self.result.parts.append(part)


def _build_trash(self):
    STRUCTURAL_ROLES = {
        ContourRole.OUTER,
        ContourRole.INNER,
        ContourRole.HOLE,
    }

    self.result.trash_entities += [
        proxy for proxy in self._all_proxies
        if id(proxy.source_ref) not in self.classified_entity_ids
        and id(proxy.source_ref) not in self.classified_virtual_ids
        and proxy.role not in STRUCTURAL_ROLES
        and (
            proxy.role != ContourRole.UNKNOWN
            or id(proxy.source_ref) not in self.entities_in_loops
        )
    ]
    self.result.parts.sort(key=lambda p: p.outer.polygon.area, reverse=True)