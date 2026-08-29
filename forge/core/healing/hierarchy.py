# forge/core/healing/hierarchy.py

from typing import Optional
from shapely.geometry import Polygon

from ...model.feature import ClosedFeature
from ...model.part import ForgePart, ForgeContour
from ...model.hole import Hole, HOLE_TYPE_UNKNOWN
from ...model.role import ContourRole
from ...rules.thresholds import HOLE_DIAMETER_THRESHOLD


MIN_CONTOUR_AREA = 1e-3
MIN_SINGLE_LOOP_DIAMETER = 0.05


# ---------------------------------------------------------------------------
# Conversione loop → ClosedFeature
# ---------------------------------------------------------------------------

def _single_loop_geometry(loop, poly):
    if len(loop) != 1:
        return None, None
    if poly is None or poly.is_empty:
        return None, None

    minx, miny, maxx, maxy = poly.bounds
    width  = maxx - minx
    height = maxy - miny
    if width <= 0 or height <= 0:
        return None, None
    if abs(width - height) / max(width, height) > 0.15:
        return None, None

    return min(width, height), ((minx + maxx) / 2, (miny + maxy) / 2)


def loop_to_closed_feature(
    loop,
    role: ContourRole = ContourRole.UNKNOWN,
    polygon=None,
    segments: list = None,
) -> Optional[ClosedFeature]:
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

        diameter = None
        center   = None
        if len(loop) == 1:
            diameter, center = _single_loop_geometry(loop, poly)
            if diameter is not None and diameter < MIN_SINGLE_LOOP_DIAMETER:
                return None

        return ClosedFeature(
            role=role,
            polygon=poly,
            segments=segments or [],
            diameter=diameter,
            center=center,
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Albero di contenimento
# ---------------------------------------------------------------------------

def _place(proxy: ClosedFeature, nodes: list) -> bool:
    for node in nodes:
        if node[0].polygon.contains(proxy.polygon):
            if not _place(proxy, node[1]):
                node[1].append([proxy, []])
            return True
    return False


def _build_tree(proxies: list) -> list:
    proxies_sorted = sorted(proxies, key=lambda p: round(p.polygon.area, 6), reverse=True)
    roots = []
    for proxy in proxies_sorted:
        if not _place(proxy, roots):
            roots.append([proxy, []])
    return roots


# ---------------------------------------------------------------------------
# Costruzione semantica
# ---------------------------------------------------------------------------

def _make_hole(
    proxy: ClosedFeature,
    geometric_hint: str = "",
    outer_proxy: Optional[ClosedFeature] = None,
) -> Hole:
    role = proxy.role if proxy.role != ContourRole.UNKNOWN else (
        ContourRole.HOLE if proxy.diameter is not None and proxy.diameter < HOLE_DIAMETER_THRESHOLD
        else ContourRole.INNER
    )
    return Hole(
        polygon=proxy.polygon,
        diameter=proxy.diameter or 0.0,
        center=proxy.center or (0.0, 0.0),
        hole_type=HOLE_TYPE_UNKNOWN,
        geometric_hint=geometric_hint,
        role=role,
        outer_diameter=outer_proxy.diameter if outer_proxy else None,
        segments=list(proxy.segments),
    )


def _make_inner(proxy: ClosedFeature, parent_role: ContourRole = ContourRole.UNKNOWN) -> ForgeContour:
    role = (
        proxy.role if proxy.role not in (ContourRole.UNKNOWN, ContourRole.INNER)
        else parent_role if parent_role not in (ContourRole.UNKNOWN, ContourRole.INNER)
        else ContourRole.INNER
    )
    return ForgeContour(
        polygon=proxy.polygon,
        role=role,
        segments=list(proxy.segments),
    )


def _process_children(
    children: list,
    holes: list,
    inners: list,
    classified_proxies: set,
    parent_role: ContourRole = ContourRole.UNKNOWN,
):
    for child_proxy, grandchildren in children:
        classified_proxies.add(id(child_proxy.polygon))

        if grandchildren:
            for gc_proxy, _ in grandchildren:
                classified_proxies.add(id(gc_proxy.polygon))
                if gc_proxy.diameter is not None:
                    holes.append(_make_hole(gc_proxy, geometric_hint="countersink", outer_proxy=child_proxy))
                else:
                    inners.append(_make_inner(gc_proxy, parent_role=parent_role))
        else:
            if child_proxy.diameter is not None:
                holes.append(_make_hole(child_proxy))
            else:
                inners.append(_make_inner(child_proxy, parent_role=parent_role))


# ---------------------------------------------------------------------------
# HierarchyBuilder
# ---------------------------------------------------------------------------

class HierarchyBuilder:
    def __init__(self, label: str, source_file: str, label_map: dict, entities_in_loops: set = None):
        self.label       = label
        self.source_file = source_file
        self.label_map   = label_map
        # entities_in_loops tenuto temporaneamente per compatibilità — non usato

    def build(self, proxies: list) -> tuple[list[ForgePart], list]:
        self._classified_proxies: set[int] = set()

        valid = [p for p in proxies if getattr(p, "polygon", None) is not None]
        if not valid:
            return [], self._collect_trash(proxies)

        tree  = _build_tree(valid)
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
                segments=list(father_proxy.segments),
            )
            self._classified_proxies.add(id(father_proxy.polygon))

            holes  = []
            inners = []
            _process_children(children, holes, inners, self._classified_proxies, parent_role=father_proxy.role)

            part = ForgePart(
                outer=outer,
                holes=holes,
                inners=inners,
                label=self.label,
                source_file=self.source_file,
                custom={},
            )
            parts.append(part)

        return parts

    def _collect_trash(self, proxies: list) -> list:
        STRUCTURAL_ROLES = {ContourRole.OUTER, ContourRole.INNER, ContourRole.HOLE}
        return [
            p for p in proxies
            if id(getattr(p, "polygon", None)) not in self._classified_proxies
            and getattr(p, "role", ContourRole.UNKNOWN) not in STRUCTURAL_ROLES
        ]