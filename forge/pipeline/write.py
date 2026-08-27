"""
pipeline/write.py
-----------------
Materializza un ForgeResult in uno o più documenti DXF NUOVI, lavorando
esclusivamente sui segmenti del modello. Zero accesso a source_ref, entity_ids,
msp sorgente.

- `to_dxf(result, ...)`  → un Drawing con tutte le parti (o un sottoinsieme).
- `split(result, ...)`   → un Drawing per parte. Puro: nessun I/O su disco.

L'unica funzione che tocca il disco è `pipeline.split_to_files()`, che è un
wrapper sottile attorno a `split()`.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Set

import ezdxf

from ..model import ForgeResult, ForgePart
from ..model.document import ForgeDocument, Annotation
from ..model.hole import HOLE_TYPE_COUNTERSINK, HOLE_TYPE_THREADED
from ..model.role import ContourRole
from ..adapters.dxf.exporter import write_segments, write_open_segments
from ..adapters.dxf.layers import (
    LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
    TRASH_LAYER,
    WORK_TYPE_TO_LAYER,
    ALL_FORGE_LAYERS,
    ROLE_TO_LAYER,
)
from ..rules.palette import COLOR_TRASH

DEFAULT_MIN_PART_AREA = 50.0  # mm²

ANNOTATION_TYPES = frozenset({"TEXT", "MTEXT", "DIMENSION", "LEADER", "MULTILEADER"})


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def to_dxf(
    result: ForgeResult,
    source_doc: Optional[ForgeDocument] = None,
    filter_part: Optional[Callable[[ForgePart], bool]] = None,
    include_annotations: bool = True,
    include_trash: bool = True,
) -> "ezdxf.document.Drawing":
    """
    Crea un documento DXF nuovo (R2010) e vi materializza il ForgeResult.

    Itera i parts del modello e scrive i segmenti puri di ogni contorno/hole.
    Non legge entità DXF esistenti — se passato, `source_doc` serve solo per
    riportare gli header ($INSUNITS, $MEASUREMENT) e riscrivere le annotazioni.

    Con `include_trash=True` (default) le entità che il pipeline non ha
    classificato (`result.trash_entities`) vengono materializzate sul layer
    `Trash`: un operatore CAM deve poter vedere OGNI entità del disegno di
    partenza, anche archi spuri, frammenti di profilo, centerline. Ometterle
    silenziosamente è una regressione.

    Restituisce il documento ezdxf: sta al chiamante fare doc.saveas(...).
    """
    doc_out = ezdxf.new(dxfversion="R2010")
    if source_doc is not None:
        doc_out.header["$INSUNITS"]    = source_doc.source_meta.get("$INSUNITS", 4)
        doc_out.header["$MEASUREMENT"] = source_doc.source_meta.get("$MEASUREMENT", 1)

    msp = doc_out.modelspace()
    _setup_layers(doc_out)

    written_parts: List[ForgePart] = []

    for part in result.parts:
        if filter_part is not None and not filter_part(part):
            continue
        written_parts.append(part)

        # Contorno esterno
        write_segments(part.outer.segments, msp, ROLE_TO_LAYER.get(part.outer.role, LAYER_OUTER))

        # Contorni interni
        for inner in part.inners:
            write_segments(inner.segments, msp, ROLE_TO_LAYER.get(inner.role, LAYER_INNER))

        # Fori
        for hole in part.holes:
            layer = ROLE_TO_LAYER.get(hole.role, LAYER_HOLE)
            layer = _work_layer_for_hole(hole) or layer
            write_segments(hole.segments, msp, layer)

        # Bending lines (geometria pura)
        _write_bending_lines(msp, part)

        # Engrave lines
        for eng in part.engrave_lines:
            layer_name, _ = WORK_TYPE_TO_LAYER.get("engrave", (TRASH_LAYER, COLOR_TRASH))
            write_segments(eng.segments, msp, layer_name)

    if include_trash and result.trash_entities:
        _write_trash(
            msp, result, written_parts, result.parts,
            restrict_to_written=filter_part is not None,
        )

    if include_annotations and source_doc is not None and source_doc.annotations:
        _write_annotations(msp, source_doc.annotations, written_parts)

    return doc_out


def part_passes_min_area(part: ForgePart, min_area: float) -> bool:
    """True se la parte supera la soglia di area minima (min_area <= 0 = nessun filtro)."""
    return not (min_area > 0 and part.outer.polygon.area < min_area)


def split(
    result: ForgeResult,
    source_doc: Optional[ForgeDocument] = None,
    namer: Optional[Callable] = None,
    include_annotations: bool = True,
    min_area: float = DEFAULT_MIN_PART_AREA,
    exclude_types: Set[str] = None,
    on_part: Optional[Callable] = None,
) -> List["ezdxf.document.Drawing"]:
    """
    Materializza un ForgeResult in un Drawing per parte.

    Funzione PURA: non tocca il disco. Per salvare i file usa
    `pipeline.split_to_files()`, o itera il risultato e chiama `.saveas(...)`.

    Ritorna i Drawing nell'ordine delle parti tenute (quelle che superano
    `min_area`). `namer(i, part)` — se passato — assegna `part.label`, così il
    nome file resta ricavabile a valle come `f"{part.label}.dxf"`.
    """
    exclude_types = exclude_types or set()
    drawings: List["ezdxf.document.Drawing"] = []

    for i, part in enumerate(result.parts):
        if not part_passes_min_area(part, min_area):
            result.warnings.append(
                f"Part {i} scartato: area {part.outer.polygon.area:.2f} mm² "
                f"sotto soglia {min_area} mm²"
            )
            continue

        part.label = namer(i, part) if namer else f"{part.label}_P{i + 1}"

        def _only_this_part(p: ForgePart, _target=part) -> bool:
            return p is _target

        doc_out = to_dxf(
            result,
            source_doc,
            filter_part=_only_this_part,
            include_annotations=include_annotations,
        )

        if exclude_types:
            _remove_excluded_entities(doc_out.modelspace(), {t.upper() for t in exclude_types})

        if on_part is not None:
            on_part(part, doc_out)

        drawings.append(doc_out)

    return drawings


# ---------------------------------------------------------------------------
# Annotazioni
# ---------------------------------------------------------------------------

def _write_annotations(msp, annotations: List[Annotation], parts: List[ForgePart]) -> None:
    """
    Riscrive le annotazioni testuali della sorgente nel documento di output.

    Un'annotazione viene scritta solo se la sua posizione ricade dentro
    l'outer di una delle parti scritte (così split() filtra automaticamente).
    Se non ci sono parti scritte, le annotazioni vengono tutte riportate.
    """
    from shapely.geometry import Point

    polygons = [p.outer.polygon for p in parts if p.outer and p.outer.polygon is not None]

    for ann in annotations:
        if polygons:
            probe = Point(ann.position)
            if not any(poly.covers(probe) for poly in polygons):
                continue

        content = ann.data.get("content", "")
        layer = ann.data.get("layer", "0")
        attribs = {"layer": layer, "color": 256}

        if ann.kind == "MTEXT":
            entity = msp.add_mtext(content, dxfattribs={
                **attribs,
                "char_height": ann.data.get("height") or 2.5,
                "rotation": ann.data.get("rotation") or 0.0,
            })
            entity.set_location(ann.position)
        else:
            # TEXT come default anche per DIMENSION/LEADER senza geometria di quota
            if not content:
                continue
            msp.add_text(content, dxfattribs={
                **attribs,
                "height": ann.data.get("height") or 2.5,
                "rotation": ann.data.get("rotation") or 0.0,
                "insert": ann.position,
            })


# ---------------------------------------------------------------------------
# Trash — entità non classificate, sempre riportate sul layer Trash
# ---------------------------------------------------------------------------

def _trash_probe_point(trash) -> Optional[tuple]:
    """Punto rappresentativo di un'entità trash, per assegnarla a una parte."""
    pts = getattr(trash, "pts", None)
    if pts:
        mid = pts[len(pts) // 2]
        return (mid[0], mid[1])
    for seg in getattr(trash, "segments", []) or []:
        start = getattr(seg, "start", None) or getattr(seg, "center", None)
        if start is not None:
            return (start[0], start[1])
    return None


def _write_trash(
    msp,
    result: ForgeResult,
    written_parts: List[ForgePart],
    all_parts: List[ForgePart],
    restrict_to_written: bool,
) -> None:
    """
    Materializza `result.trash_entities` sul layer Trash.

    In `to_dxf()` (documento intero) le riporta tutte. In `split()` — un file
    per parte — assegna ogni entità trash alla parte più vicina fra TUTTE le
    parti e la scrive solo nel file di quella parte, così non viene duplicata
    in ogni file.
    """
    from shapely.geometry import Point

    written_set = set(id(p) for p in written_parts)
    ref_polys = [
        (p, p.outer.polygon)
        for p in all_parts
        if p.outer is not None and p.outer.polygon is not None
    ]

    for trash in result.trash_entities:
        if restrict_to_written and ref_polys:
            probe = _trash_probe_point(trash)
            if probe is not None:
                nearest = min(
                    ref_polys,
                    key=lambda pp: pp[1].distance(Point(probe)),
                )[0]
                if id(nearest) not in written_set:
                    continue

        segments = list(getattr(trash, "segments", []) or [])
        if segments:
            write_open_segments(segments, msp, TRASH_LAYER)
            continue

        pts = getattr(trash, "pts", None)
        if pts and len(pts) >= 2:
            msp.add_lwpolyline(
                [(x, y) for x, y in pts],
                dxfattribs={"layer": TRASH_LAYER, "color": 256},
                close=False,
            )


# ---------------------------------------------------------------------------
# Helpers interni
# ---------------------------------------------------------------------------

def _work_layer_for_hole(hole) -> Optional[str]:
    """
    Restituisce il layer lavorazione corretto per fori speciali.
    None = layer strutturale standard (LAYER_HOLE).
    """
    if hole.hole_type == HOLE_TYPE_COUNTERSINK:
        layer_name, _ = WORK_TYPE_TO_LAYER.get("countersink", (None, None))
        return layer_name
    if hole.hole_type == HOLE_TYPE_THREADED:
        layer_name, _ = WORK_TYPE_TO_LAYER.get("threaded_hole", (None, None))
        return layer_name
    return None


def _write_bending_lines(msp, part: ForgePart) -> None:
    """
    Materializza le bending lines da geometria pura (bl.geometry).
    Deduplica per coordinate arrotondate.
    """
    layer_name, _ = WORK_TYPE_TO_LAYER.get("bending", (TRASH_LAYER, COLOR_TRASH))
    seen: Set[tuple] = set()

    for bl in part.bending_lines:
        if bl.geometry is None:
            continue
        coords = list(bl.geometry.coords)
        if len(coords) < 2:
            continue
        start = coords[0]
        end   = coords[-1]
        key = (round(start[0], 6), round(start[1], 6),
               round(end[0],   6), round(end[1],   6))
        if key in seen:
            continue
        seen.add(key)
        msp.add_line(start, end, dxfattribs={"layer": layer_name, "color": 256})


def _remove_excluded_entities(msp, excluded_upper: Set[str]) -> None:
    to_delete = [e for e in msp if e.dxftype().upper() in excluded_upper]
    for e in to_delete:
        msp.delete_entity(e)


def _setup_layers(doc) -> None:
    for name, color in ALL_FORGE_LAYERS.items():
        if name not in doc.layers:
            layer = doc.layers.new(name)
        else:
            layer = doc.layers.get(name)
        layer.color = color