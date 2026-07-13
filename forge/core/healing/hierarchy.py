

# from typing import Optional
# from shapely.geometry import Polygon
# import math

# from ...core.geometry import spline_endpoints

# from ...model.part import (
#     ForgePart,
#     ForgeContour,
# )

# from ...model.hole import (
#     Hole,
#     HOLE_TYPE_UNKNOWN,
# )

# from ...adapters.dxf.geometry_adapter import (
#     entity_to_polygon,
# )

# from ...rules.layers import (
#     LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
#     COLOR_INNER,
#     color_for_layer,
#     HOLE_DIAMETER_THRESHOLD, STRUCTURAL_LAYERS,
# )

# from ...adapters.dxf.geometry_adapter import arc_endpoints, spline_to_points


# def _build_hierarchy(self):
#     shapes = []
#     for ctx in self.result._virtual_shapes:
#         shapes.append((ctx, ctx.contour.polygon, "VIRTUAL"))
#     for pline in self.all_plines:
#         poly = entity_to_polygon(pline)
#         if poly:
#             shapes.append((pline, poly, "LWPOLYLINE"))
#     for circle in self.all_circles:
#         poly = entity_to_polygon(circle)
#         if poly:
#             shapes.append((circle, poly, "CIRCLE"))
#     for spline in self.closed_splines:
#         poly = _spline_to_polygon(spline)
#         if poly:
#             shapes.append((spline, poly, "SPLINE"))

#     if not shapes:
#         self.result.errors.append("Nessuna geometria chiusa trovata dopo healing.")
#         self.result.is_valid = False
#         return

#     shapes.sort(key=lambda x: x[1].area, reverse=True)

#     def _place(obj, poly, tipo, nodes):
#         for node in nodes:
#             if node[1].contains(poly):
#                 if not _place(obj, poly, tipo, node[3]):
#                     node[3].append([obj, poly, tipo, []])
#                 return True
#         return False

#     fathers = []
#     for obj, poly, tipo in shapes:
#         if not _place(obj, poly, tipo, fathers):
#             fathers.append([obj, poly, tipo, []])

#     for node in fathers:
#         for child in node[3]:
#             if child[2] == "VIRTUAL":
#                 child[0].layer = LAYER_INNER
#                 child[0].color = color_for_layer(LAYER_INNER)

#     for father in fathers:
#         father_obj, father_poly, father_tipo, children = father

#         outer = ForgeContour(
#             polygon=father_poly,
#             is_inner=False,
#             layer=LAYER_OUTER,
#             entity=father_obj if father_tipo != "VIRTUAL" else None,
#         )

#         if father_tipo == "VIRTUAL":
#             self.classified_virtual_ids.add(id(father_obj))
#         else:
#             self.classified_entity_ids.add(id(father_obj))

#         holes  = []
#         inners = []

#         for child in children:
#             child_obj, child_poly, child_tipo, grandchildren = child

#             if grandchildren:
#                 if child_tipo == "VIRTUAL":
#                     self.classified_virtual_ids.add(id(child_obj))
#                 else:
#                     self.classified_entity_ids.add(id(child_obj))
#                     self.result.trash_entities.append(child_obj)

#                 outer_diameter = child_obj.dxf.radius * 2 if child_tipo == "CIRCLE" else None

#                 for gc in grandchildren:
#                     gc_obj, gc_poly, gc_tipo, _ = gc

#                     if gc_tipo == "CIRCLE":
#                         diameter = gc_obj.dxf.radius * 2
#                         center   = (gc_obj.dxf.center.x, gc_obj.dxf.center.y)
#                         layer    = LAYER_HOLE if diameter < HOLE_DIAMETER_THRESHOLD else LAYER_INNER
#                         holes.append(Hole(
#                             polygon=gc_poly,
#                             diameter=diameter,
#                             center=center,
#                             hole_type=HOLE_TYPE_UNKNOWN,
#                             geometric_hint="countersink",
#                             layer=layer,
#                             source_layer=(
#                                 gc_obj.contour.source_layer if gc_tipo == "VIRTUAL"
#                                 else gc_obj.dxf.layer if gc_obj.dxf.hasattr("layer")
#                                 else ""
#                             ),
#                             entity=gc_obj,
#                             outer_diameter=outer_diameter,
#                             outer_entity=child_obj if child_tipo != "VIRTUAL" else None,
#                         ))
#                     else:
#                         inners.append(ForgeContour(
#                             polygon=gc_poly,
#                             is_inner=True,
#                             layer=LAYER_INNER,
#                             is_hole=False,
#                             entity=gc_obj if gc_tipo != "VIRTUAL" else None,
#                             source_layer=(
#                                 gc_obj.contour.source_layer if gc_tipo == "VIRTUAL"
#                                 else gc_obj.dxf.layer if gc_obj.dxf.hasattr("layer")
#                                 else ""
#                             ),
#                         ))

#                     if gc_tipo == "VIRTUAL":
#                         self.classified_virtual_ids.add(id(gc_obj))
#                     else:
#                         self.classified_entity_ids.add(id(gc_obj))

#             else:
#                 if child_tipo == "CIRCLE":
#                     diameter = child_obj.dxf.radius * 2
#                     center   = (child_obj.dxf.center.x, child_obj.dxf.center.y)
#                     layer    = LAYER_HOLE if diameter < HOLE_DIAMETER_THRESHOLD else LAYER_INNER
#                     holes.append(Hole(
#                         polygon=child_poly,
#                         diameter=diameter,
#                         center=center,
#                         hole_type=HOLE_TYPE_UNKNOWN,
#                         geometric_hint="",
#                         layer=layer,
#                         source_layer=(
#                             child_obj.dxf.layer if child_obj.dxf.hasattr("layer") else ""
#                         ),
#                         entity=child_obj,
#                     ))
#                 else:
#                     inners.append(ForgeContour(
#                         polygon=child_poly,
#                         is_inner=True,
#                         layer=LAYER_INNER,
#                         is_hole=False,
#                         entity=child_obj if child_tipo != "VIRTUAL" else None,
#                         source_layer=(
#                             child_obj.contour.source_layer if child_tipo == "VIRTUAL"
#                             else child_obj.dxf.layer if child_obj.dxf.hasattr("layer")
#                             else ""
#                         ),
#                         vs_id=id(child_obj) if child_tipo == "VIRTUAL" else None,
#                     ))

#                 if child_tipo == "VIRTUAL":
#                     self.classified_virtual_ids.add(id(child_obj))
#                 else:
#                     self.classified_entity_ids.add(id(child_obj))

#         entity_ids = set()
#         entity_ids.add(id(father_obj))

#         for child in children:
#             child_obj, _, child_tipo, grandchildren = child
#             entity_ids.add(id(child_obj))
#             for gc in grandchildren:
#                 gc_obj, _, gc_tipo, _ = gc
#                 entity_ids.add(id(gc_obj))

#         for hole in holes:
#             if hole.entity is not None:
#                 entity_ids.add(id(hole.entity))
#             if hole.outer_entity is not None:
#                 entity_ids.add(id(hole.outer_entity))

#         for inner in inners:
#             if inner.entity is not None:
#                 entity_ids.add(id(inner.entity))

#         part = ForgePart(
#             outer=outer,
#             holes=holes,
#             inners=inners,
#             label=self.label,
#             source_file=self.source_file,
#             custom={},
#             entity_ids=entity_ids,
#         )

#         if father_tipo == "VIRTUAL":
#             self.result._vs_to_part[id(father_obj)] = part

#         for child in children:
#             child_obj, _, child_tipo, grandchildren = child
#             if child_tipo == "VIRTUAL":
#                 self.result._vs_to_part[id(child_obj)] = part
#             for gc in grandchildren:
#                 gc_obj, _, gc_tipo, _ = gc
#                 if gc_tipo == "VIRTUAL":
#                     self.result._vs_to_part[id(gc_obj)] = part

#         self.result.parts.append(part)


# def _build_trash(self):
#     self.result.trash_entities += [
#         e for e in self.msp
#         if id(e) not in self.classified_entity_ids
#         and id(e) not in self.classified_virtual_ids
#         and e.dxf.hasattr("layer")
#         and e.dxf.layer.upper() not in STRUCTURAL_LAYERS
#         and (
#             id(e) not in self.entities_in_loops
#             or e.dxf.layer.lower() in self.special_layer_names
#         )
#     ]

#     self.result.parts.sort(key=lambda p: p.outer.polygon.area, reverse=True)


# def _spline_to_polygon(spline) -> Optional[Polygon]:
#     pts = spline_to_points(spline)
#     if len(pts) < 3:
#         return None
#     try:
#         poly = Polygon(pts)
#         if not poly.is_valid:
#             poly = poly.buffer(0)
#         if poly.geom_type == "MultiPolygon":
#             poly = max(poly.geoms, key=lambda p: p.area)
#         return poly if not poly.is_empty else None
#     except Exception:
#         return None


# def _spline_is_closed(spline, tolerance: float = 0.01) -> bool:
#     s, e = spline_endpoints(spline)
#     if s is None or e is None:
#         return False
#     return math.sqrt((e[0] - s[0]) ** 2 + (e[1] - s[1]) ** 2) < tolerance


from typing import Optional
from shapely.geometry import Polygon

from ...model.shape_proxy import ShapeProxy
from ...model.part import ForgePart, ForgeContour
from ...model.hole import Hole, HOLE_TYPE_UNKNOWN
from ...rules.layers import (
    LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
    color_for_layer,
    HOLE_DIAMETER_THRESHOLD, STRUCTURAL_LAYERS,
)
from ...adapters.dxf.proxy_adapter import entity_to_proxy, contour_to_proxy


# ---------------------------------------------------------------------------
# Costruzione lista proxy — unico punto che conosce DxfWriteContext e ezdxf
# ---------------------------------------------------------------------------

def _collect_proxies(self) -> list[ShapeProxy]:
    """
    Produce la lista flat di ShapeProxy da tutte le sorgenti geometriche.

    È l'unica funzione in questo modulo che sa cosa c'è in HealStep.
    _build_hierarchy riceve solo il risultato — zero entità ezdxf raw.
    """
    proxies = []
    from ...adapters.dxf import proxy_adapter
    print(proxy_adapter.__file__)
        # DEBUG
    print(f"  _virtual_shapes: {len(self.result._virtual_shapes)}")
    print(f"  all_plines:      {len(self.all_plines)}")
    print(f"  all_circles:     {len(self.all_circles)}")
    print(f"  closed_splines:  {len(self.closed_splines)}")


    for ctx in self.result._virtual_shapes:
        proxies.append(contour_to_proxy(ctx))

    for pline in self.all_plines:
        from ...adapters.dxf.geometry_adapter import entity_to_polygon
        poly = entity_to_polygon(pline)
        print(f"  pline dxftype={pline.dxftype()} poly={poly}")
        p = entity_to_proxy(pline)
        print(f"  proxy prodotto: {p is not None}, proxies ora: {len(proxies)}")
        if p:
            proxies.append(p)

    for circle in self.all_circles:
        p = entity_to_proxy(circle)
        if p:
            proxies.append(p)

    for spline in self.closed_splines:
        p = entity_to_proxy(spline)
        if p:
            proxies.append(p)

    return proxies


# ---------------------------------------------------------------------------
# Classificazione proxy — agnostica, zero accessi a source_ref
# ---------------------------------------------------------------------------

def _place(proxy: ShapeProxy, nodes: list) -> bool:
    """
    Inserisce proxy nell'albero di contenimento ricorsivo.
    Restituisce True se è stato piazzato dentro un nodo esistente.

    Ogni nodo è [ShapeProxy, children: list].
    """
    for node in nodes:
        if node[0].polygon.contains(proxy.polygon):
            if not _place(proxy, node[1]):
                node[1].append([proxy, []])
            return True
    return False


def _build_tree(proxies: list[ShapeProxy]) -> list:
    """
    Costruisce l'albero di contenimento padre/figlio.
    Ordina per area decrescente — i padri prima dei figli.
    """
    proxies_sorted = sorted(proxies, key=lambda p: p.polygon.area, reverse=True)
    roots = []
    for proxy in proxies_sorted:
        if not _place(proxy, roots):
            roots.append([proxy, []])
    return roots


# ---------------------------------------------------------------------------
# Costruzione semantica — legge solo ShapeProxy, zero .dxf.*
# ---------------------------------------------------------------------------

def _make_hole(proxy: ShapeProxy, geometric_hint: str = "",
               outer_proxy: Optional[ShapeProxy] = None) -> Hole:
    layer = LAYER_HOLE if proxy.diameter < HOLE_DIAMETER_THRESHOLD else LAYER_INNER
    return Hole(
        polygon=proxy.polygon,
        diameter=proxy.diameter,
        center=proxy.center,
        hole_type=HOLE_TYPE_UNKNOWN,
        geometric_hint=geometric_hint,
        layer=layer,
        source_layer=proxy.source_layer,
        entity=proxy.source_ref,
        outer_diameter=outer_proxy.diameter if outer_proxy else None,
        outer_entity=outer_proxy.source_ref if outer_proxy else None,
    )


def _make_inner(proxy: ShapeProxy) -> ForgeContour:
    is_virtual = proxy.shape_type == "virtual"
    return ForgeContour(
        polygon=proxy.polygon,
        is_inner=True,
        layer=LAYER_INNER,
        is_hole=False,
        entity=proxy.source_ref if not is_virtual else None,
        source_layer=proxy.source_layer,
        vs_id=id(proxy.source_ref) if is_virtual else None,
    )


def _process_children(children: list, holes: list, inners: list,
                       classified_virtual_ids: set, classified_entity_ids: set):
    """
    Classifica i figli di un padre in holes e inners.
    Gestisce anche i nipoti (countersink: cerchio esterno con cerchio interno).
    """
    for child_node in children:
        child_proxy, grandchildren = child_node

        if grandchildren:
            # figlio con nipoti → countersink o tasca con foro
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
                    inners.append(_make_inner(gc_proxy))

                _register(gc_proxy, classified_virtual_ids, classified_entity_ids)

        else:
            # foglia
            if child_proxy.diameter is not None:
                holes.append(_make_hole(child_proxy))
            else:
                inners.append(_make_inner(child_proxy))

            _register(child_proxy, classified_virtual_ids, classified_entity_ids)

            if child_proxy.shape_type == "virtual":
                child_proxy.source_ref.layer = LAYER_INNER
                child_proxy.source_ref.color = color_for_layer(LAYER_INNER)


def _register(proxy: ShapeProxy, classified_virtual_ids: set,
              classified_entity_ids: set):
    if proxy.shape_type == "virtual":
        classified_virtual_ids.add(id(proxy.source_ref))
    else:
        classified_entity_ids.add(id(proxy.source_ref))


def _collect_entity_ids(father_proxy: ShapeProxy, children: list) -> set:
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
    proxies = _collect_proxies(self)
              
    if not proxies:
        self.result.errors.append("Nessuna geometria chiusa trovata dopo healing.")
        self.result.is_valid = False
        return

    tree = _build_tree(proxies)

    for root_node in tree:
        father_proxy, children = root_node

        # contorno esterno
        outer = ForgeContour(
            polygon=father_proxy.polygon,
            is_inner=False,
            layer=LAYER_OUTER,
            entity=father_proxy.source_ref if father_proxy.shape_type != "virtual" else None,
        )

        _register(father_proxy, self.classified_virtual_ids, self.classified_entity_ids)

        if father_proxy.shape_type == "virtual":
            father_proxy.source_ref.layer = LAYER_OUTER
            father_proxy.source_ref.color = color_for_layer(LAYER_OUTER)

        holes  = []
        inners = []
        _process_children(
            children, holes, inners,
            self.classified_virtual_ids, self.classified_entity_ids,
        )

        entity_ids = _collect_entity_ids(father_proxy, children)
        for hole in holes:
            if hole.entity is not None:
                entity_ids.add(id(hole.entity))
            if hole.outer_entity is not None:
                entity_ids.add(id(hole.outer_entity))
        for inner in inners:
            if inner.entity is not None:
                entity_ids.add(id(inner.entity))

        part = ForgePart(
            outer=outer,
            holes=holes,
            inners=inners,
            label=self.label,
            source_file=self.source_file,
            custom={},
            entity_ids=entity_ids,
        )

        # mappa vs → part per write() e split()
        if father_proxy.shape_type == "virtual":
            self.result._vs_to_part[id(father_proxy.source_ref)] = part
        for child_proxy, grandchildren in children:
            if child_proxy.shape_type == "virtual":
                self.result._vs_to_part[id(child_proxy.source_ref)] = part
            for gc_proxy, _ in grandchildren:
                if gc_proxy.shape_type == "virtual":
                    self.result._vs_to_part[id(gc_proxy.source_ref)] = part

        self.result.parts.append(part)


# ---------------------------------------------------------------------------
# Trash — entità non classificate che non appartengono a nessun part
# ---------------------------------------------------------------------------

def _build_trash(self):
    self.result.trash_entities += [
        e for e in self.msp
        if id(e) not in self.classified_entity_ids
        and id(e) not in self.classified_virtual_ids
        and e.dxf.hasattr("layer")
        and e.dxf.layer.upper() not in STRUCTURAL_LAYERS
        and (
            id(e) not in self.entities_in_loops
            or e.dxf.layer.lower() in self.special_layer_names
        )
    ]

    self.result.parts.sort(key=lambda p: p.outer.polygon.area, reverse=True)