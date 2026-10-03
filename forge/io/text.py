"""
io/text.py
----------
`to_text(result)` — renderer testuale del modello forge per un lettore che è
un modello linguistico (MAP.md D84).

Un fatto per riga, in Markdown. Ogni contorno chiuso ha un id corto (`C1`,
`C1.3`) che quote e frecce riusano: "quale quota misura cosa" è un
riferimento scritto, non una cosa da indovinare. Le forme con un nome
(`contour_shape`) stanno su una riga; le altre si scrivono lato per lato. Le
spline restano esatte, con estremi, ingombro e lunghezza calcolati da forge.
Ogni collezione di `cluster.detected` si scrive in modo generico, come fa
`to_dxf` (D70): forge non sa cosa sia, la riporta. Niente viene perso: quello
che forge non ha capito sta nell'ultima sezione.

Non riesegue nessuna fase: legge `Dimension.references`/`Leader.target`
dove `anchor_annotations` li ha già scritti.
"""

from __future__ import annotations

import dataclasses
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from shapely.geometry import Point
from shapely.prepared import prep

from ..core.primitives.segments import ArcSeg, CircleSeg, EllipseSeg, LineSeg, SplineSeg
from ..core.shape import contour_shape
from ..model import ForgeResult
from ..model.annotation import Dimension, Leader

FORMAT_VERSION = 0
"""Versione del formato, scritta in testa: cambia quando cambia la sintassi."""

_PATH = re.compile(r"clusters\[(\d+)\]\.(\w+)(?:\[(\d+)\])?$")


class _Writer:
    """Numeri arrotondati e id dei contorni per una sola chiamata di `to_text`."""

    def __init__(self, result: ForgeResult, decimals: int, spline_data: bool):
        self.decimals = decimals
        self.spline_data = spline_data
        self.ids: dict[int, str] = {}
        for i, cluster in enumerate(result.clusters, start=1):
            self.ids[id(cluster.outer)] = f"C{i}"
            for j, inner in enumerate(cluster.inners, start=1):
                self.ids[id(inner)] = f"C{i}.{j}"

    def num(self, value: float) -> str:
        text = f"{value:.{self.decimals}f}".rstrip("0").rstrip(".")
        return "0" if text in ("-0", "") else text

    def pt(self, p) -> str:
        return f"({self.num(p[0])},{self.num(p[1])})"

    def deg(self, radians: float) -> str:
        return self.num(math.degrees(radians) % 360.0)

    def label(self, path: Optional[str]) -> Optional[str]:
        """`clusters[0].inners[2]` → `C1.3`; una collezione di `detected` → `C1.holes[1]`."""
        if not path:
            return None
        m = _PATH.match(path)
        if m is None:
            return path
        cluster, name, index = int(m.group(1)) + 1, m.group(2), m.group(3)
        if name == "outer":
            return f"C{cluster}"
        if name == "inners" and index is not None:
            return f"C{cluster}.{int(index) + 1}"
        return f"C{cluster}.{name}[{int(index) + 1}]" if index is not None else f"C{cluster}.{name}"

    # --- geometria ---------------------------------------------------------

    def segment(self, s) -> list[str]:
        """Un segmento: una riga, più le righe dei dati per una spline."""
        if isinstance(s, LineSeg):
            return [f"line {self.pt(s.start)} {self.pt(s.end)}"]
        if isinstance(s, ArcSeg):
            return [f"arc centre {self.pt(s.center)} R{self.num(s.radius)} "
                    f"{self.deg(s.start_angle)}..{self.deg(s.end_angle)}deg {'ccw' if s.ccw else 'cw'}"]
        if isinstance(s, CircleSeg):
            return [f"circle centre {self.pt(s.center)} R{self.num(s.radius)}"]
        if isinstance(s, EllipseSeg):
            return [f"ellipse centre {self.pt(s.center)} major axis {self.pt(s.major_axis)} "
                    f"ratio {self.num(s.ratio)} params {self.num(s.start_param)}..{self.num(s.end_param)}"]
        if isinstance(s, SplineSeg):
            return self.spline(s)
        return [type(s).__name__]

    def spline(self, s: SplineSeg) -> list[str]:
        # quello che un lettore non sa calcolare dai punti di controllo: estremi,
        # ingombro, lunghezza (sulla curva, non sul poligono — D42). I dati
        # esatti solo se chiesti: a un lettore non servono, e pesano.
        pts = s.discretize()
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        length = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
        lines = [f"spline degree {s.degree}, {len(s.control_points)} control points"
                 f"{', closed' if s.closed else ''}, from {self.pt(pts[0])} to {self.pt(pts[-1])}, "
                 f"bbox {self.pt((min(xs), min(ys)))}-{self.pt((max(xs), max(ys)))}, "
                 f"length {self.num(length)}"]
        if not self.spline_data:
            return lines
        lines.append("  ctrl " + " ".join(self.pt(p) for p in s.control_points))
        if not _uniform_knots(s.knots, s.degree):
            lines.append("  knots " + " ".join(self.num(k) for k in s.knots))
        if s.weights and any(abs(w - 1.0) > 1e-12 for w in s.weights):
            lines.append("  weights " + " ".join(self.num(w) for w in s.weights))
        return lines

    def contour(self, contour) -> list[str]:
        """Una forma con un nome su una riga; le altre lato per lato."""
        shape = contour_shape(contour)
        if shape is not None and shape.kind == "circle":
            return [f"circle D{self.num(shape.diameter or shape.length)} centre {self.pt(shape.center)}"]
        if shape is not None and shape.kind in ("rectangle", "stadium"):
            axis = "" if not shape.angle else f" axis {self.num(shape.angle)}deg"
            return [f"{shape.kind} {self.num(shape.length)} x {self.num(shape.width)} "
                    f"centre {self.pt(shape.center)}{axis}"]
        kind = shape.kind if shape is not None else "closed contour"
        segments = list(getattr(contour, "segments", None) or [])
        head = f"{kind}, {len(segments)} segments:"
        return [head] + ["  " + line for s in segments for line in self.segment(s)]

    def detected_item(self, item: Any) -> str:
        """Un elemento di `detected`, generico: tipo, contorni che è, campi semplici."""
        parts = [type(item).__name__]
        same = [self.ids[id(c)] for c in (getattr(item, "contours", None) or [item]) if id(c) in self.ids]
        if same:
            parts.append("is " + ", ".join(same))
        values = (
            {f.name: getattr(item, f.name) for f in dataclasses.fields(item)}
            if dataclasses.is_dataclass(item) else vars(item) if hasattr(item, "__dict__") else {}
        )
        for key, value in values.items():
            if key.startswith("_"):
                continue
            if isinstance(value, bool) or isinstance(value, (str, int)) and value != "":
                parts.append(f"{key}={value}")
            elif isinstance(value, float):
                parts.append(f"{key}={self.num(value)}")
            elif isinstance(value, tuple) and len(value) in (2, 3) and all(isinstance(v, (int, float)) for v in value):
                parts.append(f"{key}={self.pt(value)}")
        return " ".join(parts)


def _first_point(s) -> Optional[tuple]:
    """Un punto che sta sul segmento, per dire in quale pezzo cade."""
    if isinstance(s, LineSeg):
        return s.start
    pts = s.discretize() if hasattr(s, "discretize") else []
    return pts[0] if pts else None


def _uniform_knots(knots, degree: int) -> bool:
    """Nodi bloccati agli estremi e passo interno costante: non serve scriverli."""
    if not knots:
        return True
    inner = knots[degree:len(knots) - degree]
    steps = [b - a for a, b in zip(inner, inner[1:])]
    clamped = (len(set(round(k, 9) for k in knots[:degree + 1])) == 1
               and len(set(round(k, 9) for k in knots[-degree - 1:])) == 1)
    return clamped and (not steps or max(steps) - min(steps) < 1e-9)


def to_text(result: ForgeResult, source_name: str = "", decimals: int = 3,
            spline_data: bool = False) -> str:
    """
    Il `ForgeResult` come testo per un modello linguistico (`.forge.md`).

    Sezioni: contorni, linee aperte non ancora classificate, quote e frecce,
    testi, `detected`, e quello che non è stato capito. Coordinate a
    `decimals` cifre. Una linea aperta si elenca se sta dentro un cluster e
    nessuno l'ha classificata; con un ruolo già deciso (cornice, cartiglio...)
    o fuori da tutti i cluster si conta soltanto. Una spline è
    descritta da estremi, ingombro e lunghezza; `spline_data=True` aggiunge
    punti di controllo, nodi e pesi (i dati esatti stanno comunque in `to_dxf`).
    """
    w = _Writer(result, decimals, spline_data)
    title = f"# forge reading of {source_name}" if source_name else "# forge reading"
    out = [title,
           f"format: forge-text {FORMAT_VERSION} · drawing units · y up · {decimals} decimals",
           "legend: Cn = cluster n (its outer contour); Cn.k = k-th closed contour inside it; "
           "-> = what a dimension measures or a leader points at",
           ""]

    out.append("## contours")
    for i, cluster in enumerate(result.clusters, start=1):
        lines = w.contour(cluster.outer)
        out.append(f"C{i}: outer {lines[0]}")
        out += lines[1:]
        for j, inner in enumerate(cluster.inners, start=1):
            lines = w.contour(inner)
            out.append(f"C{i}.{j}: {lines[0]}")
            out += lines[1:]

    # una linea aperta dentro un pezzo fa parte della sua lettura (l'arco di una
    # filettatura, un asse); fuori da tutti i pezzi si conta soltanto
    outers = [prep(c.outer.polygon) for c in result.clusters if getattr(c.outer, "polygon", None) is not None]
    unknown, by_role, outside = [], Counter(), 0
    for feature in result.trash_entities:
        role = getattr(feature, "role", None) or "unknown"
        segments = getattr(feature, "segments", None) or []
        if role != "unknown" or not segments:
            by_role[role] += 1
            continue
        start = _first_point(segments[0])
        if start is not None and not any(o.covers(Point(start)) for o in outers):
            outside += 1
            continue
        styles = getattr(feature, "styles", None) or []
        dash = styles[0].dash_kind if styles else "continuous"
        body = "; ".join(line for s in segments for line in w.segment(s))
        unknown.append(f"{dash}: {body}")
    out += ["", "## open edges (inside a cluster, not part of a closed contour, not classified)"] + (unknown or ["(none)"])

    out += ["", "## dimensions and leaders"]
    texts, lost = [], []
    for a in result.annotations:
        if isinstance(a, Dimension):
            measured = "" if a.measured_value is None else f" measured {w.num(a.measured_value)}"
            refs = [w.label(p) for p in a.references]
            if refs:
                out.append(f"dim {a.dim_type} '{a.display_text}'{measured} -> {', '.join(refs)}")
            else:
                lost.append(f"dim {a.dim_type} '{a.display_text}'{measured} at {w.pt(a.position)}: "
                            f"no element found")
        elif isinstance(a, Leader):
            text = f" '{a.display_text}'" if a.display_text else ""
            if a.target:
                out.append(f"leader{text} at {w.pt(a.position)} -> {w.label(a.target)}")
            else:
                lost.append(f"leader{text} at {w.pt(a.position)}: points at nothing")
        elif getattr(a, "display_text", ""):
            inside = f" in C{a.cluster_ref + 1}" if a.cluster_ref is not None else ""
            texts.append(f"'{a.display_text}' at {w.pt(a.position)}{inside}")
    out += ["", "## texts"] + (texts or ["(none)"])

    out += ["", "## detected (attached by whoever read the drawing further)"]
    detected = [f"C{i}.{name}[{k}]: {w.detected_item(item)}"
                for i, cluster in enumerate(result.clusters, start=1) if cluster.detected is not None
                for name, items in cluster.detected.items()
                for k, item in enumerate(items, start=1)]
    out += detected or ["(none)"]

    out += ["", "## not understood"]
    out += lost
    if outside:
        out.append(f"{outside} open edges outside every cluster, not listed")
    out += [f"{n} open edges with role {role}, not listed" for role, n in sorted(by_role.items())]
    if not result.is_valid:
        out.append("result is NOT valid: " + "; ".join(result.errors))
    out += [f"warning: {m}" for m in result.warnings]
    if out[-1] == "## not understood":
        out.append("(nothing)")
    return "\n".join(out) + "\n"


def save_text(result: ForgeResult, path: str | Path, source_name: str = "", decimals: int = 3,
              spline_data: bool = False) -> None:
    """Scrive `to_text(result)` su `path` (per convenzione `<nome>.forge.md`)."""
    Path(path).write_text(to_text(result, source_name, decimals, spline_data), encoding="utf-8")
