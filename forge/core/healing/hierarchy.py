# forge/core/healing/hierarchy.py

from typing import Optional

import math
from shapely.geometry import Polygon

from ...bridge.shape import ClosedShape, OpenShape
from ...model.part import ForgePart, ForgeContour
from ...model.hole import Hole, HOLE_TYPE_UNKNOWN
from ...model.role import ContourRole
from ...rules.thresholds import HOLE_DIAMETER_THRESHOLD


MIN_CONTOUR_AREA = 1e-3
MIN_SINGLE_LOOP_DIAMETER = 0.05


# ---------------------------------------------------------------------------
# Conversione loop → ClosedShape
# ---------------------------------------------------------------------------


def _single_loop_geometry(loop, poly):
    """Estrae diametro e centro da un loop degenerato."""
    if len(loop) != 1:
        return None, None
    if poly is None or poly.is_empty:
        return None, None

    minx, miny, maxx, maxy = poly.bounds
    width = maxx - minx
    height = maxy - miny
    if width <= 0 or height <= 0:
        return None, None

    # Verifica che sia circolare
    if abs(width - height) / max(width, height) > 0.15:
        return None, None

    return min(width, height), ((minx + maxx) / 2, (miny + maxy) / 2)


def loop_to_closed_shape(
    loop,
    role: ContourRole = ContourRole.UNKNOWN,
    polygon=None,
    source_ref=None,
    is_virtual: bool = False,
    segments: list = None,
) -> Optional[ClosedShape]:
    """
    Converte un loop (lista di (Edge, bool)) in ClosedShape.

    polygon   : poligono già calcolato, se disponibile.
    source_ref: riferimento opaco associato al loop, se disponibile.

    La funzione resta nel core e non prende decisioni di export o writeback.
    """
    from ...core.topology.loop_finder import LoopFinder

    if polygon is not None:
        poly = polygon
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
        if poly.area <= MIN_CONTOUR_AREA:
            return None

        first_ref = loop[0][0].source_ref if loop else None
        resolved_source_ref = source_ref if source_ref is not None else first_ref

        diameter = None
        center = None
        if len(loop) == 1:
            diameter, center = _single_loop_geometry(loop, poly)
            if diameter is not None and diameter < MIN_SINGLE_LOOP_DIAMETER:
                return None

        return ClosedShape(
            polygon=poly,
            diameter=diameter,
            center=center,
            source_ref=resolved_source_ref,
            role=role,
            is_virtual=is_virtual,
            segments=segments or [],
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helper privati - albero di contenimento
# ---------------------------------------------------------------------------

def _place(proxy: ClosedShape, nodes: list) -> bool:
    for node in nodes:
        if node[0].polygon.contains(proxy.polygon):
            if not _place(proxy, node[1]):
                node[1].append([proxy, []])
            return True
    return False


def _build_tree(proxies: list[ClosedShape]) -> list:
    proxies_sorted = sorted(proxies, key=lambda p: round(p.polygon.area, 6), reverse=True)
    roots = []
    for proxy in proxies_sorted:
        if not _place(proxy, roots):
            roots.append([proxy, []])
    return roots


# ---------------------------------------------------------------------------
# Helper privati - costruzione semantica
# ---------------------------------------------------------------------------

def _proxy_origin(proxy: ClosedShape) -> str:
    if not proxy.is_virtual:
        return ""
    return getattr(proxy.source_ref, "origin", "") or ""


def _make_hole(
    proxy: ClosedShape,
    geometric_hint: str = "",
    outer_proxy: Optional[ClosedShape] = None,
) -> Hole:
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
        segments=list(proxy.segments),
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
        segments=list(proxy.segments),
    )


def _register(proxy: ClosedShape, classified_virtual_ids: set, classified_entity_ids: set):
    if proxy.is_virtual:
        classified_virtual_ids.add(id(proxy.source_ref))
    else:
        classified_entity_ids.add(id(proxy.source_ref))


def _collect_entity_ids(father_proxy, children) -> set:
    ids = set()

    # Colleziona tutte le entità dal loop del DxfWriteContext
    src = father_proxy.source_ref
    if src is not None:
        # Mantieni anche l'id del container virtuale: serve per il mapping
        # vs_id -> part durante heal(), usato poi da write()/split().
        ids.add(id(src))
    if hasattr(src, 'loop'):
        for edge, _ in src.loop:
            if edge.source_ref is not None:
                ids.add(id(edge.source_ref))

    for child_proxy, grandchildren in children:
        child_src = child_proxy.source_ref
        if child_src is not None:
            ids.add(id(child_src))
        if hasattr(child_src, 'loop'):
            for edge, _ in child_src.loop:
                if edge.source_ref is not None:
                    ids.add(id(edge.source_ref))

        for gc_proxy, _ in grandchildren:
            gc_src = gc_proxy.source_ref
            if gc_src is not None:
                ids.add(id(gc_src))
            if hasattr(gc_src, 'loop'):
                for edge, _ in gc_src.loop:
                    if edge.source_ref is not None:
                        ids.add(id(edge.source_ref))

    return ids


def _process_children(
    children: list,
    holes: list,
    inners: list,
    classified_virtual_ids: set,
    classified_entity_ids: set,
    parent_role: ContourRole = ContourRole.UNKNOWN,
):
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


# ---------------------------------------------------------------------------
# HierarchyBuilder
# ---------------------------------------------------------------------------

class HierarchyBuilder:
    """
    Costruisce la gerarchia ForgePart da una lista piatta di ClosedShape.

    Non ha dipendenze da HealStep né da adapter DXF - riceve tutto ciò
    che gli serve nel costruttore e lavora solo su ClosedShape e Polygon.
    """

    def __init__(
        self,
        label: str,
        source_file: str,
        label_map: dict,
        entities_in_loops: set,
    ):
        self.label = label
        self.source_file = source_file
        self.label_map = label_map
        self.entities_in_loops = entities_in_loops

    def build(self, proxies: list) -> tuple[list[ForgePart], list]:
        """
        Restituisce (parts, trash).

        proxies : lista mista di ClosedShape e OpenShape - tutto ciò che
                  il pipeline ha prodotto dopo il loop-finding.

        parts : lista di ForgePart, ordinata per area outer decrescente
        trash : proxy non classificati in nessuna part (ClosedShape o OpenShape)
        """
        self._classified_virtual_ids: set = set()
        self._classified_entity_ids: set = set()

        valid = [p for p in proxies if getattr(p, "polygon", None) is not None]
        if not valid:
            return [], self._collect_trash(proxies)

        tree = _build_tree(valid)
        parts = self._build_parts(tree)
        trash = self._collect_trash(proxies)

        parts.sort(key=lambda p: p.outer.polygon.area, reverse=True)
        return parts, trash

    def _build_parts(self, tree: list) -> list[ForgePart]:
        parts = []

        for root_node in tree:
            father_proxy, children = root_node

            outer = ForgeContour(
                polygon=father_proxy.polygon,
                role=ContourRole.OUTER,
                source_ref=father_proxy.source_ref if not father_proxy.is_virtual else None,
                vs_id=id(father_proxy.source_ref) if father_proxy.is_virtual else None,
                origin=_proxy_origin(father_proxy),
                segments=list(father_proxy.segments),
            )

            _register(father_proxy, self._classified_virtual_ids, self._classified_entity_ids)

            holes = []
            inners = []

            _process_children(
                children,
                holes,
                inners,
                self._classified_virtual_ids,
                self._classified_entity_ids,
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

            self._update_vs_map(father_proxy, children, part)
            parts.append(part)

        return parts

    def _update_vs_map(self, father_proxy: ClosedShape, children: list, part: ForgePart):
        """
        Popola il mapping vs_id → ForgePart su ForgeResult.

        Non disponibile qui (HierarchyBuilder non conosce ForgeResult) -
        il chiamante deve farlo dopo build() se ne ha bisogno.
        """
        pass

    def _collect_trash(self, proxies: list[ClosedShape | OpenShape]) -> list[ClosedShape | OpenShape]:
        STRUCTURAL_ROLES = {
            ContourRole.OUTER,
            ContourRole.INNER,
            ContourRole.HOLE,
        }
        return [
            proxy for proxy in proxies
            if id(proxy.source_ref) not in self._classified_entity_ids
            and id(proxy.source_ref) not in self._classified_virtual_ids
            and proxy.role not in STRUCTURAL_ROLES
            and (
                proxy.role != ContourRole.UNKNOWN
                or id(proxy.source_ref) not in self.entities_in_loops
            )
        ]