from typing import Optional
from shapely.geometry import Polygon

from ...model.shape import ClosedShape
from ...model.part import ForgePart, ForgeContour
from ...model.hole import Hole, HOLE_TYPE_UNKNOWN
from ...rules.layers import (
    LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
    color_for_layer,
    HOLE_DIAMETER_THRESHOLD, STRUCTURAL_LAYERS,
)


# ---------------------------------------------------------------------------
# Classificazione proxy — agnostica, zero accessi a source_ref
# ---------------------------------------------------------------------------

def _place(proxy: ClosedShape, nodes: list) -> bool:
    """
    Inserisce proxy nell'albero di contenimento ricorsivo.
    Restituisce True se è stato piazzato dentro un nodo esistente.

    Ogni nodo è [ClosedShape, children: list].
    """
    for node in nodes:
        if node[0].polygon.contains(proxy.polygon):
            if not _place(proxy, node[1]):
                node[1].append([proxy, []])
            return True
    return False


def _build_tree(proxies: list[ClosedShape]) -> list:
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
# Costruzione semantica — legge solo ClosedShape, zero .dxf.*
# ---------------------------------------------------------------------------

def _make_hole(proxy: ClosedShape, geometric_hint: str = "",
               outer_proxy: Optional[ClosedShape] = None) -> Hole:
    role = "hole" if proxy.diameter < HOLE_DIAMETER_THRESHOLD else "inner"
    return Hole(
        polygon=proxy.polygon,
        diameter=proxy.diameter,
        center=proxy.center,
        hole_type=HOLE_TYPE_UNKNOWN,
        geometric_hint=geometric_hint,
        role=role,
        origin=proxy.origin,
        source_ref=proxy.source_ref,
        outer_diameter=outer_proxy.diameter if outer_proxy else None,
        outer_source_ref=outer_proxy.source_ref if outer_proxy else None,
    )

def _make_inner(proxy: ClosedShape) -> ForgeContour:
    is_virtual = proxy.is_virtual
    return ForgeContour(
        polygon=proxy.polygon,
        role="inner",
        source_ref=proxy.source_ref if not is_virtual else None,
        origin=proxy.origin,
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

            if child_proxy.is_virtual:
                child_proxy.source_ref.layer = LAYER_INNER
                child_proxy.source_ref.color = color_for_layer(LAYER_INNER)


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
    self._all_proxies = self.adapter.collect_closed(self.open_splines, self.result._virtual_shapes)
    self._all_proxies += self.adapter.to_open()
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
            role="outer",
            source_ref=father_proxy.source_ref if not father_proxy.is_virtual else None,
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

        # mappa vs → part per write() e split()
        if father_proxy.is_virtual:
            self.result._vs_to_part[id(father_proxy.source_ref)] = part
        for child_proxy, grandchildren in children:
            if child_proxy.is_virtual:
                self.result._vs_to_part[id(child_proxy.source_ref)] = part
            for gc_proxy, _ in grandchildren:
                if gc_proxy.is_virtual:
                    self.result._vs_to_part[id(gc_proxy.source_ref)] = part

        self.result.parts.append(part)


# ---------------------------------------------------------------------------
# Trash — entità non classificate che non appartengono a nessun part
# ---------------------------------------------------------------------------

def _build_trash(self):
    self.result.trash_entities += [
        proxy for proxy in self._all_proxies
        if id(proxy.source_ref) not in self.classified_entity_ids
        and id(proxy.source_ref) not in self.classified_virtual_ids
        and proxy.origin != ""
        and proxy.origin.upper() not in STRUCTURAL_LAYERS
        and (
            id(proxy.source_ref) not in self.entities_in_loops
            or proxy.origin.lower() in self.special_layer_names
        )
    ]
    self.result.parts.sort(key=lambda p: p.outer.polygon.area, reverse=True)
