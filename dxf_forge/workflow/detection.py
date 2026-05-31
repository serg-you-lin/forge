

"""
workflow/detection.py
---------------------
Step semantico post-heal: rileva il significato delle entità geometriche.

Posizione nella pipeline:
    heal()      → geometria pura — crea Hole(hole_type=UNKNOWN, geometric_hint=...)
    detect()    → semantica — promuove Hole.hole_type al tipo definitivo
    inject()    → serializzazione dati CAM

Responsabilità di detect() sui fori:
    1. Special layers (certezza 1.0)
       Hole su layer noto → hole_type promosso immediatamente.
       Priorità assoluta su hint geometrico e inferenza.

    2. Hint geometrico da heal() (certezza < 1.0)
       heal() ha già identificato la struttura: Hole.geometric_hint != ""
       detect() legge l'hint e promuove senza ricalcolare la geometria.
       Confidenza: countersink 0.85, threaded 0.80.

    3. Interpreter (inferenza — certezza variabile)
       Tutto ciò che resta in trash dopo i passi 1 e 2.

NON è responsabilità di detect():
    - costruire loop o topologia               → heal()
    - aprire o salvare file                    → il chiamante
    - scrivere layer/colore nel DXF            → _apply_to_msp()
    - serializzare metriche nel JSON           → inject()

Nota su special_layers e fori:
    Se un Hole.source_layer è in special_layers con work_type "countersink"
    o "threaded_hole", il layer vince sull'hint geometrico.
    Questo è l'unico caso in cui un foro che heal() ha visto come liscio
    può diventare filettato — perché il CAD designer lo ha messo su un layer
    dedicato senza usare il simbolo grafico standard.
"""

from __future__ import annotations

import math
from typing import Optional

from shapely.geometry import LineString, Point

from ..models import (
    ForgeResult,
    ForgePart,
    ForgeContour,
    GeometryHints,
    Hole,
    BendingLine,
    ClassifiedEntity,
    BaseInterpreter,
    HOLE_TYPE_PLAIN,
    HOLE_TYPE_COUNTERSINK,
    HOLE_TYPE_THREADED,
    HOLE_TYPE_UNKNOWN,
)
from ..core.geometry import (
    is_threaded_hole,
)
from ..rules.layers import WORK_TYPE_TO_LAYER, VALID_WORK_TYPES

# Work type → hole_type: mappa per special_layers sui fori
_WORK_TYPE_TO_HOLE_TYPE = {
    "countersink":   HOLE_TYPE_COUNTERSINK,
    "threaded_hole": HOLE_TYPE_THREADED,
}


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def detect(
    result:         ForgeResult,
    msp,
    special_layers: dict                     = None,
    interpreter:    Optional[BaseInterpreter] = None,
    bending_tolerance: float                    = 1.0,
) -> None:
    """
    Rileva la semantica geometrica e popola geometry_hints e part.custom.

    Sovrascrive geometry_hints esistenti — idempotente per design.
    Se chiamato due volte, il secondo risultato rimpiazza il primo.

    Args:
        result:         ForgeResult prodotto da heal()
        msp:            modelspace ezdxf — stesso oggetto passato a heal()
        special_layers: dict {nome_layer: work_type}
                        es. {"BEND": "bending", "FORI_FILETTATI": "threaded_hole"}
                        Certezza 1.0 — ha priorità su tutto, incluso geometric_hint.
                        Se None, solo detection via hint geometrico.
        interpreter:    implementazione di BaseInterpreter.
                        Se None, il trash residuo non viene interpretato.
    """
    if special_layers:
        unknown = {v.lower() for v in special_layers.values()} - VALID_WORK_TYPES
        if unknown:
            result.warnings.append(
                f"detect(): work_type sconosciuti in special_layers: {unknown}. "
                f"Valori validi: {VALID_WORK_TYPES}"
            )
        result.special_layers = special_layers

    all_arcs = list(msp.query("ARC"))

    if special_layers:
        _detect_special_layers(result, msp, special_layers)

    _detect_bending_lines(result, bending_tolerance=bending_tolerance)

    _detect_holes(result, all_arcs)

    if interpreter is not None:
        _run_interpreter(result, msp, interpreter)


# ---------------------------------------------------------------------------
# Step 1 — special layers (certezza 1.0)
# ---------------------------------------------------------------------------

def _detect_special_layers(
    result:         ForgeResult,
    msp,
    special_layers: dict,
) -> None:
    """
    Classifica entità trash e Hole su layer speciali noti.

    Per i Hole: promuove hole_type direttamente — non crea ClassifiedEntity
    perché il foro è già un oggetto di dominio, non un'entità generica.
    Per le entità trash (bending, engrave, ecc.): crea ClassifiedEntity come prima.
    """
    layer_to_work  = {k.lower(): v.lower() for k, v in special_layers.items()}
    classified_ids = set()

    # --- entità trash (bending, engrave, marking, ecc.) ---
    for entity in result.trash_entities:
        if not entity.dxf.hasattr("layer"):
            continue
        layer     = entity.dxf.layer.lower()
        work_type = layer_to_work.get(layer)
        if work_type is None:
            continue
        data = _extract_data(entity, work_type)
        ce   = ClassifiedEntity(
            entity=entity,
            work_type=work_type,
            confidence=1.0,
            source="special_layers",
            data=data,
        )
        result.classified_entities.append(ce)
        _assign_to_part(ce, result)
        classified_ids.add(id(entity))

    result.trash_entities = [
        e for e in result.trash_entities if id(e) not in classified_ids
    ]

    # --- Hole sui part: promozione diretta da layer speciale ---
    for part in result.parts:
        for hole in part.holes:
            check_layer = (hole.source_layer or hole.layer).lower()
            work_type   = layer_to_work.get(check_layer)
            if work_type is None:
                continue
            hole_type = _WORK_TYPE_TO_HOLE_TYPE.get(work_type)
            if hole_type is None:
                continue
            hole.hole_type  = hole_type
            hole.confidence = 1.0
            hole.source     = "special_layers"

        # --- contorni inner non-foro su layer speciale ---
        remaining = []
        for inner in part.inners:
            check_layer = (inner.source_layer or inner.layer).lower()
            work_type   = layer_to_work.get(check_layer)
            # print(f"  INNER check_layer={check_layer!r} work_type={work_type!r} entity={inner.entity} polygon={inner.polygon is not None}")
            if work_type is None:
                remaining.append(inner)
                continue
            data = _extract_data(inner.entity, work_type) if inner.entity is not None else {
                "length": round(inner.polygon.exterior.length, 4),
                "layer":  inner.source_layer,
            }
            ce = ClassifiedEntity(
                entity=inner.entity,
                work_type=work_type,
                confidence=1.0,
                source="special_layers",
                data=data,
                polygon=inner.polygon,  # ← UNICA AGGIUNTA
            )
            result.classified_entities.append(ce)
            if inner.vs_id is not None:
                result._suppressed_vs_ids.add(inner.vs_id)
            _assign_to_part(ce, result)
        part.inners = remaining

# ---------------------------------------------------------------------------
# Step 2 — promozione fori da geometric_hint (certezza < 1.0)
# ---------------------------------------------------------------------------

def _detect_holes(result: ForgeResult, all_arcs: list) -> None:
    #print("\n--- ENTER DETECT HOLES ---")
    for part in result.parts:
        for hole in part.holes:
            # print(f"[detect_holes] hole entity={hole.entity} source={hole.source} hole_type={hole.hole_type} geometric_hint={hole.geometric_hint}")

            # ✔️ HARD LOCK: già deciso da special_layers
            if hole.source == "special_layers":
                #print("[SPECIAL SET]", id(hole), hole.source, hole.hole_type)
                continue

            # ✔️ già classificato in modo definitivo altrove
            if hole.hole_type != HOLE_TYPE_UNKNOWN:
                continue

            if hole.geometric_hint == "countersink":
                hole.hole_type  = HOLE_TYPE_COUNTERSINK
                hole.confidence = 0.85
                hole.source     = "geometric"
                continue

            if hole.geometric_hint == "threaded":
                hole.hole_type  = HOLE_TYPE_THREADED
                hole.confidence = 0.85
                hole.source     = "geometric"
                continue

            if hole.entity is not None and is_threaded_hole(hole.entity, all_arcs):
                hole.hole_type  = HOLE_TYPE_THREADED
                hole.confidence = 0.80
                hole.source     = "geometric"
            else:
                hole.hole_type  = HOLE_TYPE_PLAIN
                hole.confidence = 1.0
                hole.source     = "geometric"

            # print(f"  → dopo detect: hole_type={hole.hole_type}")


# ---------------------------------------------------------------------------
# Step 3 — interpreter
# ---------------------------------------------------------------------------

def _run_interpreter(
    result:      ForgeResult,
    msp,
    interpreter: BaseInterpreter,
) -> None:
    """
    Passa il trash residuo all'interpreter per ogni part.

    I ClassifiedEntity prodotti vengono aggiunti a result.classified_entities
    e assegnati al part via _assign_to_part().
    I Hole sono già stati gestiti nei passi 1 e 2 — l'interpreter
    non li riceve e non li modifica.
    """
    if not result.trash_entities:
        return

    for part in result.parts:
        hints_dict = {
            "bend_line_ids": part.geometry_hints.bend_line_ids,
        }

        classified = interpreter.classify(
            entities=result.trash_entities,
            outer_poly=part.outer.polygon,
            inner_polys=[h.polygon for h in part.holes] + [i.polygon for i in part.inners],
            msp=msp,
            hints=hints_dict,
        )

        classified_ids = set()
        for ce in classified:
            result.classified_entities.append(ce)
            _assign_to_part(ce, result)
            classified_ids.add(id(ce.entity))

        result.trash_entities = [
            e for e in result.trash_entities if id(e) not in classified_ids
        ]


# ---------------------------------------------------------------------------
# Assegnazione al part contenitore
# ---------------------------------------------------------------------------

def _assign_to_part(ce: ClassifiedEntity, result: ForgeResult) -> None:
    """
    Assegna un ClassifiedEntity al ForgePart contenitore geometricamente.

    Scrive su:
        part.geometry_hints  → id() per _apply_to_msp() e snapmark
        part.custom          → dati CAM per inject()

    Nota: countersink_ids e threaded_hole_ids sono stati rimossi da
    GeometryHints — quelle informazioni vivono ora su Hole.hole_type.
    _assign_to_part gestisce solo entità non-Hole (bending, engrave, ecc.).
    """
    probe = _entity_probe_point(ce)
    if probe is None:
        return

    work_type = ce.work_type.lower()

    for part in result.parts:
        if not part.outer.polygon.contains(probe):
            continue

        if work_type == "bending":
            part.geometry_hints.bend_line_ids.add(id(ce.entity))
            part.entity_ids.add(id(ce.entity))

        _write_custom(ce, part)
        return

    result.warnings.append(
        f"detect(): entità {ce.work_type} non contenuta in nessun part "
        f"(source={ce.source}). Registrata in classified_entities."
    )

    

def _write_custom(ce: ClassifiedEntity, part: ForgePart) -> None:
    """
    Scrive i dati CAM di un ClassifiedEntity in part.custom.

    Struttura part.custom:
        "bending_lines"    → lista dati geometrici linee di piega
        "engrave_entities" → lista dati bulinature
        "marking_entities" → lista dati marcature

    Nota: countersink_data e threaded_hole_data non esistono più in custom —
    i dati dei fori si leggono da part.holes[i].to_dict().
    """
    key_map = {
        "bending": "bending_lines",
        "engrave": "engrave_entities",
        "marking": "marking_entities",
    }

    work_type = ce.work_type.lower()
    key       = key_map.get(work_type, f"{work_type}_entities")

    if key not in part.custom:
        part.custom[key] = []

    part.custom[key].append({
        **ce.data,
        "confidence": ce.confidence,
        "source":     ce.source,
    })


# ---------------------------------------------------------------------------
# Helpers — estrazione dati CAM e geometria
# ---------------------------------------------------------------------------

def _extract_data(entity, work_type: str) -> dict:
    """
    Estrae i dati CAM rilevanti da un'entità ezdxf.

    inject() usa questi dati direttamente — non riapre le entità.
    Nota: countersink e threaded_hole non passano più da qui —
    i loro dati vivono su Hole.to_dict().
    """
    work_type = work_type.lower()

    if work_type == "bending" and entity.dxftype() == "LINE":
        start = (entity.dxf.start.x, entity.dxf.start.y)
        end   = (entity.dxf.end.x,   entity.dxf.end.y)
        geom  = LineString([start, end])
        dx    = end[0] - start[0]
        dy    = end[1] - start[1]
        return {
            "start":     start,
            "end":       end,
            "length":    round(geom.length, 4),
            "angle_deg": round(math.degrees(math.atan2(dy, dx)) % 180, 4),
            "layer":     entity.dxf.layer,
        }

    if work_type in ("engrave", "marking"):
        return {
            "length": round(_entity_length(entity), 4) if _entity_length(entity) else None,
            "layer":  entity.dxf.layer if entity.dxf.hasattr("layer") else "",
        }

    return {
        "layer": entity.dxf.layer if entity.dxf.hasattr("layer") else "",
    }


def _entity_probe_point(ce: ClassifiedEntity) -> Optional[Point]:
    """Punto rappresentativo dell'entità per il containment check."""
    # print(f"  [probe] entity={ce.entity} polygon={ce.polygon is not None if hasattr(ce, 'polygon') else 'NO_ATTR'}")
    if ce.entity is None:
        if ce.polygon is not None:
            return ce.polygon.centroid
        return None
    entity = ce.entity
    try:
        dtype = entity.dxftype()
        if dtype == "LINE":
            return Point(
                (entity.dxf.start.x + entity.dxf.end.x) / 2,
                (entity.dxf.start.y + entity.dxf.end.y) / 2,
            )
        if dtype in ("CIRCLE", "ARC"):
            return Point(entity.dxf.center.x, entity.dxf.center.y)
        if dtype == "LWPOLYLINE":
            pts = list(entity.get_points())
            if pts:
                return Point(
                    sum(p[0] for p in pts) / len(pts),
                    sum(p[1] for p in pts) / len(pts),
                )
    except Exception:
        pass
    return None

def _entity_length(entity) -> Optional[float]:
    """Lunghezza di un'entità aperta (LINE, ARC) per engrave e marking."""
    try:
        dtype = entity.dxftype()
        if dtype == "LINE":
            dx = entity.dxf.end.x - entity.dxf.start.x
            dy = entity.dxf.end.y - entity.dxf.start.y
            return math.sqrt(dx * dx + dy * dy)
        if dtype == "ARC":
            start_a = math.radians(entity.dxf.start_angle)
            end_a   = math.radians(entity.dxf.end_angle)
            delta   = (end_a - start_a) % (2 * math.pi)
            return entity.dxf.radius * delta
    except Exception:
        pass
    return None



def _detect_bending_lines(result: ForgeResult, bending_tolerance: float = 1.0) -> None:
    """
    Step geometrico: individua LINE interne all'outer di ogni part
    e popola geometry_hints.bend_line_ids.

    Criteri:
        1. entità di tipo LINE
        2. midpoint contenuto nell'outer del part (o sulla boundary, tolleranza 1.0)
        3. non già classificata da special_layers

    Nota: non rimuove le entità da trash — restano disponibili
    per l'interpreter che le classificherà come "bending".
    """
        
    classified_ids = {id(ce.entity) for ce in result.classified_entities}

    for entity in result.trash_entities:
        if entity.dxftype() != "LINE":
            continue
        if id(entity) in classified_ids:
            continue

        s = Point(entity.dxf.start.x, entity.dxf.start.y)
        e = Point(entity.dxf.end.x,   entity.dxf.end.y)

        for part in result.parts:
            outer    = part.outer.polygon
            boundary = outer.boundary

            if s.distance(e) < bending_tolerance:
                continue
            if boundary.distance(s) < 1.0 and boundary.distance(e) < 1.0:
                midpoint = Point(
                    (entity.dxf.start.x + entity.dxf.end.x) / 2,
                    (entity.dxf.start.y + entity.dxf.end.y) / 2,
                )
                if outer.contains(midpoint):
                    part.geometry_hints.bend_line_ids.add(id(entity))
                    break


