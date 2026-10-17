"""
topo/core/topology/rim.py
--------------------------
I segmenti di una faccia letti dal suo bordo: quando il poligono di una
faccia è noto (l'unione delle facce di D100, un lobo di un giro che tocca se
stesso) ma gli edge della rete non si chiudono in un giro che lo segua, si
percorre l'anello del poligono e ogni suo tratto diventa l'edge su cui
giace, tagliato fra i due capi (D106). L'ordine viene dall'anello, la forma
dagli edge: archi restano archi, spline restano spline.

Puro: solo Edge, primitive e shapely.
"""

from __future__ import annotations

import math
from typing import List

from shapely import STRtree
from shapely.geometry import Point as ShapelyPoint, Polygon
from shapely.geometry.polygon import orient

from .edge import Edge
from .noding import edge_geometry
from ..primitives.segments import LineSeg, segment_endpoints
from ..primitives.trim import sub_segment


def face_segments(edges: List[Edge], polygon: Polygon, band: float):
    """
    (segments, styles) lungo il bordo esterno di `polygon`, in senso
    antiorario. Un lato del bordo sta su un edge se dista meno di `band` da
    lui; il bordo si divide fra gli edge col minor numero di cambi
    (`_rim_runs`), e ogni tratto è il suo edge tagliato fra i due capi
    (`sub_segment`) — intero se lo copre tutto. Un edge che corre sul bordo
    solo in parte (un incrocio che shapely nodifica e la rete piana no) dà
    così proprio la sua parte.
    """
    pts = list(orient(polygon, 1.0).exterior.coords)[:-1]
    n = len(pts)
    geoms = [edge_geometry(e) for e in edges]
    runs = _rim_runs(pts, geoms, _side_cover(pts, geoms, band))
    segments, styles = [], []
    for (j, _), first, last in runs:
        edge = edges[j]
        a, b = pts[first % n], pts[last % n]
        via = pts[(first + 1) % n] if last - first > 1 else ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        piece = _trimmed(edge.segment, a, b, via, band)
        if piece is None:
            # spline senza taglio esatto (periodica): il tratto resta quello
            # dell'anello, entro la tolleranza di discretizzazione
            chain = [LineSeg(start=pts[i % n], end=pts[(i + 1) % n]) for i in range(first, last)]
        else:
            chain = [piece]
        segments += chain
        styles += [edge.style] * len(chain)
    return segments, styles


def _side_cover(pts: list, geoms: list, band: float) -> List[set]:
    """Per ogni lato dell'anello, gli (edge, verso) che distano meno di `band`
    dal suo punto medio (almeno il più vicino): il verso dice se il lato
    percorre l'edge come lui (+1) o al contrario (-1). Un tratto tiene un
    verso solo — dove l'anello torna indietro lungo lo stesso edge (la
    punta di una faccia fra due curve quasi tangenti) il tratto finisce."""
    tree = STRtree(geoms)
    cover = []
    for i in range(len(pts)):
        p, q = pts[i], pts[(i + 1) % len(pts)]
        mid = ShapelyPoint((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        near = [int(j) for j in tree.query(mid, predicate="dwithin", distance=band)]
        near = near or [int(tree.query_nearest(mid)[0])]
        cover.append({(j, _sense(geoms[j], mid, p, q, band)) for j in near})
    return cover


def _sense(geom, mid, p, q, step: float) -> int:
    """+1 se il lato p→q va nel verso di `geom` vicino a `mid`, -1 se contro."""
    if geom.length == 0:
        return 1
    d = geom.project(mid)
    a = geom.interpolate(max(d - step, 0.0))
    b = geom.interpolate(min(d + step, geom.length))
    return 1 if (b.x - a.x) * (q[0] - p[0]) + (b.y - a.y) * (q[1] - p[1]) >= 0 else -1


def _rim_runs(pts: list, geoms: list, cover: List[set]) -> list:
    """
    [((edge, verso), primo vertice, ultimo vertice)] lungo l'anello: copertura greedy
    a portata massima — si tiene l'edge finché copre, poi si passa a quello
    che copre più avanti — che dà il minor numero di tratti; dove due edge
    coprono entrambi (sovrapposti, o quasi tangenti) il taglio cade sul
    vertice più vicino a tutti e due, il loro punto di contatto. Indici dei
    vertici non ridotti modulo n: crescenti, ultimo = primo + n.
    """
    n = len(cover)

    def reach(j: tuple, k: int) -> int:
        m = 0
        while m < n and j in cover[(k + m) % n]:
            m += 1
        return m

    def best(k: int) -> tuple:
        return max(sorted(cover[k % n]), key=lambda j: reach(j, k))

    s = min(range(n), key=lambda i: (len(cover[i]), i))
    owners, starts = [best(s)], [s]
    k = s + reach(owners[0], s)
    while k < s + n:
        owners.append(best(k))
        starts.append(k)
        k += reach(owners[-1], k)
    if len(owners) == 1:
        return [(owners[0], s, s + n)]
    if owners[-1] == owners[0]:
        owners.pop()
        starts[0] = starts.pop() - n

    count = len(owners)
    cuts: List[int] = []
    for i in range(count):
        before, after = owners[i - 1], owners[i]
        low = cuts[-1] + 1 if cuts else starts[i - 1] - (n if i == 0 else 0) + 1
        high = starts[i + 1] - 1 if i + 1 < count else min(starts[0] + n, cuts[0] + n) - 1
        lo = starts[i]
        while lo - 1 >= low and {before, after} <= cover[(lo - 1) % n]:
            lo -= 1
        hi = starts[i]
        while hi + 1 <= high and {before, after} <= cover[hi % n]:
            hi += 1

        def gap(v: int) -> float:
            at = ShapelyPoint(pts[v % n])
            return geoms[before[0]].distance(at) + geoms[after[0]].distance(at)

        cuts.append(min(range(lo, hi + 1), key=lambda v: (gap(v), abs(v - starts[i]))))
    return [(owners[i], cuts[i], cuts[i + 1] if i + 1 < count else cuts[0] + n)
            for i in range(count)]


def _trimmed(seg, a, b, via, band: float):
    """`seg` da `a` a `b`: un capo entro `band` da un estremo di `seg` è
    quell'estremo (il nodo vero, non la sua proiezione); se tutti e due lo
    sono, il segmento intero."""
    s0, s1 = segment_endpoints(seg)
    if math.dist(s0, s1) > band:
        sa = min((s0, s1), key=lambda e: math.dist(a, e))
        sb = min((s0, s1), key=lambda e: math.dist(b, e))
        if math.dist(a, sa) <= band and math.dist(b, sb) <= band and sa != sb:
            return seg if sa == s0 else seg.reversed()
        a = sa if math.dist(a, sa) <= band else a
        b = sb if math.dist(b, sb) <= band else b
    return sub_segment(seg, a, b, via)
