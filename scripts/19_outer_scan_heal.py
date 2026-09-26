"""
19_outer_scan_heal.py — scan → spezza → heal, risultato in DXF
==============================================================

Prototipo (il codice di spezzamento vive qui finché non si decide se e dove
promuoverlo in core). Per ogni file:

  1. normalizza come heal (collinear / cocircular / weld) — una volta sola,
     PRIMA dello scan: heal rifonderebbe i LineSeg collineari appena spezzati;
  2. outer_candidate_edges sugli edge normalizzati;
  3. spezza ogni candidato LineSeg/ArcSeg nei punti dove incrocia o tocca
     (a T, entro la tolleranza) un altro edge — SplineSeg/EllipseSeg interi;
  4. due varianti, entrambe passate agli step di HealStep SENZA i merge:
       A_tutti   — tutti gli edge, candidati spezzati: heal senza priorità
       B_esterni — solo i pezzi di candidato colpiti da almeno un raggio
  5. to_dxf(include_trash=True) → pipeline_output/outer_scan_heal/

    python scripts/19_outer_scan_heal.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import copy
import math
import os
from dataclasses import replace

import forge
from forge.model.document import ForgeDocument
from forge.core.heal import HealStep
from forge.core.geometry import (
    node_decimals_for, _line_intersection, _circle_line_intersections,
    _circle_circle_intersections,
)
from forge.core.primitives.segments import (
    LineSeg, ArcSeg, DEFAULT_TOLERANCE, segment_endpoints,
)
from forge.rules.validator import validate_result
from forge.core.healing.normalizer import (
    merge_collinear_overlaps, merge_cocircular_overlaps, weld_degenerate_linesegs,
)
from forge.core.healing.outer_scan import outer_candidate_edges

# --- CONFIG ----------------------------------------------------------------
INPUTS = [
    r"tests/examples/islands/3d_1.dxf",
    r"tests/examples/islands/SHEETCODE_1.dxf",
    r"tests/examples/islands/SHEETCODE_2.dxf",
    r"tests/examples/islands/SHEETCODE_3.dxf",
]
TOLERANCE = 0.05
OUTDIR = r"pipeline_output/outer_scan_heal"
# ---------------------------------------------------------------------------

_EPS = 1e-9
_MIN_PIECE = 1e-4   # mm — sotto, lo spezzone non viene creato


# ---------------------------------------------------------------------------
# Parametrizzazione: LineSeg in t ∈ [0, 1], ArcSeg in s ∈ [0, sweep]
# ---------------------------------------------------------------------------

def _line_param(seg, pt):
    dx, dy = seg.end[0] - seg.start[0], seg.end[1] - seg.start[1]
    l2 = dx * dx + dy * dy
    if l2 < _EPS:
        return None, float("inf")
    t = ((pt[0] - seg.start[0]) * dx + (pt[1] - seg.start[1]) * dy) / l2
    proj = (seg.start[0] + t * dx, seg.start[1] + t * dy)
    return t, math.dist(proj, pt)


def _arc_param(seg, pt):
    phi = math.atan2(pt[1] - seg.center[1], pt[0] - seg.center[0])
    delta = (phi - seg.start_angle) if seg.ccw else (seg.start_angle - phi)
    s = delta % (2 * math.pi)
    if s > seg._sweep() + _EPS:
        # fuori dall'arco: accetta solo se vicino a uno dei due estremi
        s = s - 2 * math.pi if (2 * math.pi - s) < (s - seg._sweep()) else s
    return s, abs(math.dist(pt, seg.center) - seg.radius)


def _param(seg, pt):
    return _line_param(seg, pt) if isinstance(seg, LineSeg) else _arc_param(seg, pt)


def _param_range(seg):
    return 1.0 if isinstance(seg, LineSeg) else seg._sweep()


def _length_of(seg, p0, p1):
    if isinstance(seg, LineSeg):
        return math.dist(seg.start, seg.end) * (p1 - p0)
    return seg.radius * (p1 - p0)


# ---------------------------------------------------------------------------
# Punti di spezzamento
# ---------------------------------------------------------------------------

def _cutters(edge):
    """Il resto del disegno, come rette (p, q) e archi: SplineSeg/EllipseSeg discretizzati."""
    seg = edge.segment
    if isinstance(seg, LineSeg):
        return [("line", seg.start, seg.end)]
    if isinstance(seg, ArcSeg):
        return [("arc", seg)]
    pts = seg.discretize(DEFAULT_TOLERANCE)
    return [("line", pts[i], pts[i + 1]) for i in range(len(pts) - 1)]


def _crossings(seg, cutter):
    """Punti d'incrocio fra il candidato e un cutter (reali, non sul prolungamento)."""
    if cutter[0] == "line":
        p, q = cutter[1], cutter[2]
        if isinstance(seg, LineSeg):
            ix = _line_intersection(seg.start, seg.end, p, q)
            pts = [ix] if ix else []
        else:
            pts = _circle_line_intersections(seg.center[0], seg.center[1], seg.radius, p, q)
        out = []
        for pt in pts:
            t, _ = _line_param(LineSeg(p, q), pt)
            if t is not None and -_EPS <= t <= 1 + _EPS:
                out.append(pt)
        return out
    other = cutter[1]
    if isinstance(seg, LineSeg):
        pts = _circle_line_intersections(other.center[0], other.center[1], other.radius,
                                         seg.start, seg.end)
    else:
        pts = _circle_circle_intersections(seg.center[0], seg.center[1], seg.radius,
                                           other.center[0], other.center[1], other.radius)
    return [pt for pt in pts
            if 0 - _EPS <= _arc_param(other, pt)[0] <= other._sweep() + _EPS]


def _bbox(edge):
    pts = edge.segment.discretize(DEFAULT_TOLERANCE)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _split_params(edge, others, tol):
    seg = edge.segment
    rng = _param_range(seg)
    x0, y0, x1, y1 = _bbox(edge)
    params = []
    for other, (ox0, oy0, ox1, oy1) in others:
        if other is edge:
            continue
        if ox1 < x0 - tol or ox0 > x1 + tol or oy1 < y0 - tol or oy0 > y1 + tol:
            continue
        candidates = []
        for cutter in _cutters(other):
            candidates.extend(_crossings(seg, cutter))
        # contatto a T: estremo dell'altro edge sul candidato, entro tol
        candidates.extend(segment_endpoints(other.segment))
        for pt in candidates:
            p, dist = _param(seg, pt)
            if p is None or dist > tol:
                continue
            if _length_of(seg, 0, p) > _MIN_PIECE and _length_of(seg, p, rng) > _MIN_PIECE:
                params.append(p)
    params.sort()
    dedup = []
    for p in params:
        if not dedup or _length_of(seg, dedup[-1], p) > _MIN_PIECE:
            dedup.append(p)
    return dedup


def _make_edge(edge, seg, decimals):
    s, e = segment_endpoints(seg)
    r = lambda pt: (round(pt[0], decimals), round(pt[1], decimals))
    return replace(edge, start=r(s), end=r(e), segment=seg)


def _split(edge, params, decimals):
    """Pezzi [(p0, p1, Edge)] in ordine di parametro."""
    seg = edge.segment
    bounds = [0.0] + params + [_param_range(seg)]
    out = []
    for p0, p1 in zip(bounds, bounds[1:]):
        if isinstance(seg, LineSeg):
            a = (seg.start[0] + p0 * (seg.end[0] - seg.start[0]),
                 seg.start[1] + p0 * (seg.end[1] - seg.start[1]))
            b = (seg.start[0] + p1 * (seg.end[0] - seg.start[0]),
                 seg.start[1] + p1 * (seg.end[1] - seg.start[1]))
            if p0 == 0.0:
                a = seg.start
            if p1 == 1.0:
                b = seg.end
            piece = LineSeg(start=a, end=b)
        else:
            sign = 1.0 if seg.ccw else -1.0
            piece = ArcSeg(center=seg.center, radius=seg.radius,
                           start_angle=seg.start_angle + sign * p0,
                           end_angle=seg.start_angle + sign * p1, ccw=seg.ccw)
        out.append((p0, p1, _make_edge(edge, piece, decimals)))
    return out


# ---------------------------------------------------------------------------
# Heal senza normalizzazione (già fatta prima dello scan)
# ---------------------------------------------------------------------------

def _heal_without_merge(doc, tol):
    step = HealStep(doc, tol, source_file=doc.source_path)
    step._load()
    if not step.result.is_valid:
        return step.result
    step._split_labeled()
    step._preprocess()
    step.result.all_arcs = [e.segment for e in step.edges if isinstance(e.segment, ArcSeg)]
    step._find_non_contour_edges()
    step._find_loops()
    step._build_hierarchy()
    if step.result.is_valid and step.result.clusters:
        validate_result(step.result)
    return step.result


def _report(tag, result, bbox_area):
    outers = sorted((c.outer.polygon.area for c in result.clusters), reverse=True)
    biggest = outers[0] if outers else 0.0
    return (f"  {tag:10s} valid={result.is_valid} cluster={len(result.clusters)} "
            f"outer max={biggest:.0f} mm² ({biggest / bbox_area:.0%} della bbox)"
            + (f" | {result.errors[0][:60]}" if result.errors else ""))


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    for path in INPUTS:
        stem = os.path.splitext(os.path.basename(path))[0]
        doc = forge.load_dxf(path, tolerance=TOLERANCE)
        decimals = node_decimals_for(TOLERANCE)

        edges = weld_degenerate_linesegs(
            merge_cocircular_overlaps(merge_collinear_overlaps(doc.edges)))
        oc = outer_candidate_edges(edges)

        boxes = [(e, _bbox(e)) for e in edges]
        split_all, outer_pieces = [], []
        n_split = 0
        for e in edges:
            if id(e) not in oc.ids:
                split_all.append(e)
                continue
            if not isinstance(e.segment, (LineSeg, ArcSeg)):
                split_all.append(e)
                outer_pieces.append(e)
                continue
            params = _split_params(e, boxes, TOLERANCE)
            pieces = _split(e, params, decimals)
            n_split += len(pieces) - 1
            hit_params = [_param(e.segment, h.point)[0] for h in oc.hits_of(e)]
            for p0, p1, piece in pieces:
                split_all.append(piece)
                if any(p0 - _EPS <= hp <= p1 + _EPS for hp in hit_params):
                    outer_pieces.append(piece)

        xs = [p[0] for e in edges for p in (e.start, e.end)]
        ys = [p[1] for e in edges for p in (e.start, e.end)]
        bbox_area = (max(xs) - min(xs)) * (max(ys) - min(ys))

        print(f"{stem}: {len(doc.edges)} edge -> {len(edges)} normalizzati, "
              f"{len(oc.edges)} candidati, {n_split} tagli, {len(outer_pieces)} pezzi esterni")
        for tag, variant in (("A_tutti", split_all), ("B_esterni", outer_pieces)):
            vdoc = ForgeDocument(edges=variant, annotations=list(doc.annotations),
                                 source_meta=dict(doc.source_meta), source_path=doc.source_path)
            result = _heal_without_merge(vdoc, TOLERANCE)
            print(_report(tag, result, bbox_area))
            suffix = ""
            if not result.is_valid:
                # to_dxf rifiuta un risultato invalido: qui lo si vuole vedere
                # lo stesso — esce solo la trash, cioè cosa heal non ha chiuso
                result = copy.copy(result)
                result.is_valid, result.errors = True, []
                suffix = "_INVALIDO"
            out = os.path.abspath(os.path.join(OUTDIR, f"{stem}_{tag}{suffix}.dxf"))
            forge.to_dxf(result, vdoc, include_trash=True).saveas(out)
            print(f"     -> {out}")


if __name__ == "__main__":
    main()
