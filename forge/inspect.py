"""
forge/inspect.py
----------------
Strumento di ispezione a tre livelli. Serve a *vedere* cosa succede a un file
reale senza leggere il codice — pensato per il debug quando si lavora su file
veri (es. quando si implementerà `detect_engrave`).

I tre livelli, in ordine di pipeline:

    1. inspect_dxf(path)        → entità DXF grezze        — "cosa c'è nel file"
    2. inspect_document(doc)    → edge + primitive + grafo — "cosa ha capito l'adapter"
    3. inspect_result(result)  → il modello di fabbricazione — "cosa ha prodotto forge"

E un orchestratore che li stampa in fila su un file:

    forge.inspect_file("pezzo.dxf", label_map={"Piega": "bending"})

Tutto stampa su stdout con `print`. Nessun logger da configurare.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Optional

from forge.core.geometry import track_points, track_shape_type

__all__ = [
    "inspect_dxf",
    "inspect_document",
    "inspect_result",
    "inspect_file",
]

_RULE = "=" * 72
_SUB = "-" * 72


def _h(title: str) -> None:
    print(f"\n{_RULE}\n{title}\n{_RULE}")


def _p(x, nd: int = 2) -> str:
    """Formatta un punto (x, y) con nd decimali."""
    if x is None:
        return "None"
    return f"({x[0]:.{nd}f}, {x[1]:.{nd}f})"


def _role(r) -> str:
    """Nome del ruolo come stringa piatta ('outer'), non 'ContourRole.OUTER'."""
    return getattr(r, "value", str(r))


# ===========================================================================
# LIVELLO 1 — entità DXF grezze
# ===========================================================================

def inspect_dxf(path: str, entities: bool = True, limit: Optional[int] = 40) -> None:
    """
    Apre un DXF/DWG con ezdxf e stampa cosa contiene, senza toccare forge.

    entities : se True elenca ogni entità con i suoi attributi chiave
    limit    : numero massimo di entità elencate (None = tutte)
    """
    import ezdxf

    _h(f"LIVELLO 1 — DXF grezzo\n{path}")

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    ents = list(msp)

    print(f"\nversione DXF : {doc.dxfversion}")
    print(f"$INSUNITS    : {doc.header.get('$INSUNITS', 'n/d')}   "
          f"$MEASUREMENT : {doc.header.get('$MEASUREMENT', 'n/d')}")

    counts = Counter(e.dxftype() for e in ents)
    print(f"\nentità ({len(ents)} totali):")
    for t, n in sorted(counts.items()):
        print(f"  {t:<14} {n}")

    layers = Counter(
        (e.dxf.layer if e.dxf.hasattr("layer") else "?") for e in ents
    )
    print(f"\nlayer:")
    for name, n in sorted(layers.items()):
        print(f"  {name!r:<24} {n}")

    if not entities:
        return

    print(f"\ndettaglio entità{' (primi %d)' % limit if limit else ''}:")
    for i, e in enumerate(ents):
        if limit is not None and i >= limit:
            print(f"  ... e altre {len(ents) - limit}")
            break
        print(f"  [{i}] {_describe_dxf_entity(e)}")


def _describe_dxf_entity(e) -> str:
    t = e.dxftype()
    layer = e.dxf.layer if e.dxf.hasattr("layer") else "?"
    tag = f"{t:<12} layer={layer!r}"
    try:
        if t == "LINE":
            return f"{tag}  {_p((e.dxf.start.x, e.dxf.start.y))} -> {_p((e.dxf.end.x, e.dxf.end.y))}"
        if t == "ARC":
            return (f"{tag}  c={_p((e.dxf.center.x, e.dxf.center.y))} r={e.dxf.radius:.2f} "
                    f"{e.dxf.start_angle:.1f}°->{e.dxf.end_angle:.1f}°")
        if t == "CIRCLE":
            return f"{tag}  c={_p((e.dxf.center.x, e.dxf.center.y))} r={e.dxf.radius:.2f}"
        if t in ("LWPOLYLINE", "POLYLINE"):
            try:
                n = len(list(e.get_points())) if t == "LWPOLYLINE" else len(list(e.vertices))
            except Exception:
                n = "?"
            closed = getattr(e, "is_closed", getattr(e, "closed", "?"))
            return f"{tag}  vertici={n} chiusa={closed}"
        if t == "SPLINE":
            return f"{tag}  cp={len(e.control_points)} closed={getattr(e, 'closed', '?')}"
        if t in ("TEXT", "MTEXT"):
            txt = (e.dxf.text if t == "TEXT" else e.text)[:40]
            return f"{tag}  {txt!r}"
        if t == "DIMENSION":
            return f"{tag}  text={getattr(e.dxf, 'text', '')!r}"
        if t == "INSERT":
            return f"{tag}  block={e.dxf.name!r}"
    except Exception as ex:
        return f"{tag}  <errore lettura: {ex}>"
    return tag


# ===========================================================================
# LIVELLO 2 — ForgeDocument: edge, primitive, grafo
# ===========================================================================

def inspect_document(doc, graph: bool = True, limit: Optional[int] = 60) -> None:
    """
    Stampa un ForgeDocument prodotto da forge.load_dxf(): cosa ha estratto e
    tradotto l'adapter. `doc` può essere un ForgeDocument o un path (viene
    aperto con load_dxf usando i default).
    """
    if isinstance(doc, str):
        from .adapters.dxf.loader import load_dxf
        doc = load_dxf(doc)

    _h("LIVELLO 2 — ForgeDocument (adapter → dominio)")

    print(f"\nsource_path : {doc.source_path}")
    print(f"source_meta : {doc.source_meta}")
    if getattr(doc, "warnings", None):
        print(f"\nwarnings del loader ({len(doc.warnings)}):")
        for w in doc.warnings:
            print(f"  - {w}")

    edges = doc.edges
    by_role = Counter(_role(e.role) for e in edges)
    by_seg = Counter(type(e.segment).__name__ for e in edges)
    print(f"\nedge: {len(edges)} totali")
    print(f"  per ruolo    : {dict(by_role)}")
    print(f"  per primitiva: {dict(by_seg)}")

    print(f"\ndettaglio edge{' (primi %d)' % limit if limit else ''}:")
    for i, e in enumerate(edges):
        if limit is not None and i >= limit:
            print(f"  ... e altri {len(edges) - limit}")
            break
        cp = " [closed_path]" if e.closed_path else ""
        print(f"  [{i}] role={_role(e.role):<13} {_p(e.start)} -> {_p(e.end)}  "
              f"{_describe_segment(e.segment)}{cp}")

    anns = getattr(doc, "annotations", []) or []
    if anns:
        print(f"\nannotazioni: {len(anns)}")
        kinds = Counter(a.kind for a in anns)
        print(f"  per tipo: {dict(kinds)}")
        for a in anns[:20]:
            content = (a.data.get("content") or "")[:40]
            print(f"  - {a.kind:<10} @ {_p(a.position)}  {content!r}")

    if not graph:
        return

    from .core.topology.graph import build_node_graph
    g = build_node_graph(edges)
    branching = g.branching_nodes()
    open_nodes = g.open_nodes()
    print(f"\ngrafo nodi:")
    print(f"  nodi              : {len(g.nodes)}")
    print(f"  loop degeneri     : {len(g.degenerate_loops)}  (CIRCLE / SPLINE chiusa)")
    print(f"  nodi di branching : {len(branching)} (grado > 2)  {[_p(n) for n in branching[:8]]}")
    print(f"  estremi liberi    : {len(open_nodes)} (grado 1)   {[_p(n) for n in open_nodes[:8]]}")
    if not branching and not open_nodes and g.nodes:
        print("  → grafo pulito: ogni nodo ha grado 2, contorni chiusi")


def _describe_segment(seg) -> str:
    from .core.primitives.segments import LineSeg, ArcSeg, SplineSeg, CircleSeg

    if seg is None:
        return "<nessun segmento>"
    if isinstance(seg, LineSeg):
        d = math.hypot(seg.end[0] - seg.start[0], seg.end[1] - seg.start[1])
        return f"LINE  len={d:.2f}"
    if isinstance(seg, ArcSeg):
        sweep = math.degrees(seg._sweep())
        return (f"ARC   c={_p(seg.center)} r={seg.radius:.2f} sweep={sweep:.1f}° "
                f"{'ccw' if seg.ccw else 'cw'}")
    if isinstance(seg, CircleSeg):
        return f"CIRCLE c={_p(seg.center)} r={seg.radius:.2f}"
    if isinstance(seg, SplineSeg):
        return (f"SPLINE deg={seg.degree} cp={len(seg.control_points)} "
                f"closed={seg.closed} periodic={seg.periodic}")
    return type(seg).__name__


# ===========================================================================
# LIVELLO 3 — ForgeResult: il modello di fabbricazione
# ===========================================================================

def inspect_result(result, coords: bool = False) -> None:
    """
    Stampa un ForgeResult dopo heal() (+ detect()): il prodotto vero di forge.

    coords : se True stampa anche le coordinate dei contorni
    """
    _h("LIVELLO 3 — ForgeResult (il modello)")

    print(f"\nsource_file : {result.source_file}")
    print(f"is_valid    : {result.is_valid}")
    print(f"part_count  : {result.part_count}")

    if result.errors:
        print(f"\nerrori ({len(result.errors)}):")
        for e in result.errors:
            print(f"  ERROR: {e}")
    if result.warnings:
        print(f"\nwarnings ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"  warn: {w}")

    for i, part in enumerate(result.parts):
        _sub_part(i, part, coords)

    trash = result.trash_entities or []
    if trash:
        print(f"\n{_SUB}\ntrash_entities: {len(trash)}  (geometria non classificata)")
        kinds = Counter(
            "closed" if getattr(t, "polygon", None) is not None
            else track_shape_type(track_points(getattr(t, "segments", []) or []))
            for t in trash
        )
        roles = Counter(_role(getattr(t, "role", "?")) for t in trash)
        print(f"  per tipo : {dict(kinds)}")
        print(f"  per ruolo: {dict(roles)}")

    ce = result.classified_entities or []
    if ce:
        print(f"\nclassified_entities: {len(ce)}")
        for c in ce:
            print(f"  - {c.work_type:<12} source={c.source} conf={c.confidence:.2f} "
                  f"@ {_p(c.representative_point)}")

    anns = result.annotations or []
    if anns:
        print(f"\nannotazioni nel modello: {len(anns)}  ({dict(Counter(a.kind for a in anns))})")


def _sub_part(i: int, part, coords: bool) -> None:
    print(f"\n{_SUB}\nPARTE {i}  label={part.label!r}")
    o = part.outer
    print(f"  outer  : role={_role(o.role):<10} area={o.area:.1f}  "
          f"bbox={tuple(round(v, 1) for v in o.bbox)}  segmenti={len(o.segments)}")
    print(f"  area netta (outer - fori - inner): {part.area:.1f}")

    if part.inners:
        print(f"  inners : {len(part.inners)}")
        for inn in part.inners:
            print(f"    - role={_role(inn.role):<10} area={inn.area:.1f} segmenti={len(inn.segments)}")

    if part.holes:
        print(f"  holes  : {len(part.holes)}")
        for hh in part.holes:
            print(f"    - {hh.hole_type:<11} Ø{hh.diameter:.2f} @ {_p(hh.center)}  "
                  f"source={hh.source or 'n/d'} conf={hh.confidence:.2f}")

    if part.bending_lines:
        print(f"  bending: {len(part.bending_lines)}")
        for bl in part.bending_lines:
            print(f"    - len={bl.length:.1f} angle={bl.angle_deg:.1f}°")

    if part.engrave_lines:
        print(f"  engrave: {len(part.engrave_lines)}")
        for en in part.engrave_lines:
            print(f"    - {'chiusa' if en.closed else 'aperta'} len={en.length:.2f} "
                  f"source={en.source} conf={en.confidence:.2f}")

    if part.custom:
        print(f"  custom : {part.custom}")

    if coords:
        print(f"  outer coords: {[tuple(round(c, 1) for c in pt) for pt in o.polygon.exterior.coords]}")


# ===========================================================================
# ORCHESTRATORE — i tre livelli in fila su un file
# ===========================================================================

def inspect_file(
    path: str,
    tolerance: float = 0.05,
    label_map: Optional[dict] = None,
    run_heal: bool = True,
    run_detect: bool = True,
    entities: bool = True,
    coords: bool = False,
    linetype_map: Optional[dict] = None,
    color_map: Optional[dict] = None,
) -> None:
    """
    Apre un file e stampa i tre livelli in fila:
    DXF grezzo → ForgeDocument → ForgeResult.

    run_heal / run_detect : disattivali per fermarti a un livello precedente.
    linetype_map / color_map : come in load_dxf() — seconda lane di
    classificazione sull'aspetto grezzo, usata solo dove label_map non ha
    già deciso il ruolo dal layer.
    """
    from .adapters.dxf.loader import load_dxf

    inspect_dxf(path, entities=entities)

    doc = load_dxf(
        path, tolerance=tolerance, label_map=label_map or {},
        linetype_map=linetype_map, color_map=color_map,
    )
    inspect_document(doc)

    if not run_heal:
        return

    from .pipeline import heal as _heal
    result = _heal(doc, tolerance=tolerance)

    if run_detect and result.is_valid and result.parts:
        from .pipeline.detect import detect as _detect
        _detect(result)

    inspect_result(result, coords=coords)
