# forge/core/healing/hierarchy.py

from typing import Optional
from shapely.geometry import Polygon

from ...model.feature import ClosedFeature
from ...model.part import ForgePart, ForgeContour
from ...model.role import ContourRole
from ...core.geometry import circular_geometry


MIN_CONTOUR_AREA = 1e-3
MIN_SINGLE_LOOP_DIAMETER = 0.05


# ---------------------------------------------------------------------------
# Conversione loop → ClosedFeature
# ---------------------------------------------------------------------------

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

        # Guard sui micro-cerchi: un loop di una singola primitiva circolare
        # con diametro sotto soglia è rumore, non un contorno. La
        # classificazione hole/inner vera e propria è di detect() (D15) —
        # qui `diameter`/`center` NON vengono stoccati sul feature.
        if len(loop) == 1:
            diameter, _ = circular_geometry(poly, segments)
            if diameter is not None and diameter < MIN_SINGLE_LOOP_DIAMETER:
                return None

        return ClosedFeature(
            role=role,
            polygon=poly,
            segments=segments or [],
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


def _collect_inners(
    children: list,
    inners: list,
    classified_proxies: set,
    parent_role: ContourRole = ContourRole.UNKNOWN,
):
    """
    Appiattisce l'albero di contenimento: ogni discendente di un outer diventa
    un `ForgeContour` in `part.inners`, a qualsiasi profondità.

    heal() si ferma qui — non decide più hole vs inner né riconosce i
    countersink dal nesting (D15). detect(features="holes") ri-deriva il
    nesting per contenimento fra poligoni e promuove i fori.
    """
    for child_proxy, grandchildren in children:
        classified_proxies.add(id(child_proxy.polygon))
        inners.append(_make_inner(child_proxy, parent_role=parent_role))
        if grandchildren:
            _collect_inners(grandchildren, inners, classified_proxies, parent_role=parent_role)


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

            inners = []
            _collect_inners(children, inners, self._classified_proxies, parent_role=father_proxy.role)

            part = ForgePart(
                outer=outer,
                holes=[],
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
