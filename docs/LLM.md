# forge — AI reference

Dense, token-minimal reference for an AI writing code against `forge`. No
narrative, no rationale — those live in `API.md` (full reference), `ARCHITECTURE.md`
(why), `MAP.md` (decision history). Load this file alone to use the library;
load the others only if this one doesn't answer the question.

## What it is

Deterministic 2D-geometry reconstruction engine for sheet/plate manufacturing.
Not a DXF library — DXF is just the first input adapter. Takes messy CAD
geometry (DXF/DWG, experimental PDF, or raw point/primitive dicts) and
produces a lossless domain model: healed closed contours, a containment
hierarchy, classified manufacturing features (holes/bends/engraving),
annotations — then renders that model to DXF, JSON, XML, SVG, or a
render-oriented view-model dict. Everything unclassified survives in
`trash_entities`; nothing from the source is silently dropped.

## Pipeline

```
load_dxf / document_from_msp / load_geometry   →  ForgeDocument   (edges + annotations, zero topology)
heal(doc)                                       →  ForgeResult     (topology only: closed contours, outer/inner tree — NO hole/bend classification)
island(doc)                                     →  ForgeResult     (alternative to heal for drawings of VIEWS: one cluster per island, outer = outer face of its planar network)
detect(result, features=...)                    →  ForgeResult     (mutates in place; opt-in feature classification)
to_dxf / split / to_json / save_json / to_svg / to_view_model  →  render from the model (never re-reads source)
```

`heal_and_detect(doc)` = `heal` + `detect(features="all")`, the 90% path.
`split_to_files(doc, folder)` = `heal_and_detect` + `split` + `.saveas()` per part — the only function that writes to disk on its own.

## Golden path

```python
import forge

doc = forge.load_dxf("part.dxf", tolerance=0.5, label_map={"Bend": "bending"})
check = forge.validate(doc)                      # input validation, optional
result = forge.heal_and_detect(doc, label="P-1024")
if not result.is_valid:                           # ALWAYS check before rendering
    raise SystemExit(result.errors)
forge.to_dxf(result, doc).saveas("out.dxf")
forge.save_json(result, "out.json")
```

## Functions — `forge.<name>`

| name | signature (defaults trimmed) | does |
|---|---|---|
| `load_dxf` | `(path, upgrade=False, explode_inserts=True, flatten_z_flag=True, tolerance=0.05, label_map=None, ignore_layers=None, linetype_map=None, color_map=None) -> ForgeDocument` | reads DXF/DWG via ezdxf (once), audits, upgrades legacy, explodes INSERTs, translates to pure `Edge`/`Annotation`. `label_map`/`linetype_map`/`color_map` assign `Edge.role` at load — authoritative, unknown values become consumer role slugs, not errors. DWG needs ODA File Converter (`ODA_PATH` env var). |
| `document_from_msp` | `(msp, tolerance=0.05, label_map=None, ignore_layers=None, source_path="", linetype_map=None, color_map=None) -> ForgeDocument` | same as `load_dxf` but from an already-open ezdxf `modelspace`; no audit/upgrade/sanitize. |
| `load_geometry` | `(entities: list[dict], tolerance=0.05, source_path="") -> ForgeDocument` | builds a `ForgeDocument` from pure geometry, no file. Entity `type`: `line`(start,end) / `arc`(center,radius,start_angle,end_angle deg,ccw) / `circle`(center,radius) / `polyline`(points,closed) / `spline`(control_points,knots,degree,weights?,fit_points?,closed?) / `ellipse`(center,major_axis vector,ratio?,start_param?,end_param?,ccw?). Optional `role` per entity, same open vocabulary as `label_map`. |
| `validate` | `(doc: ForgeDocument) -> ForgeResult` | input validation, no mutation. `is_valid=False` = unworkable (no geometry / NaN / all-degenerate). Warnings = workable but flagged. |
| `validate_result` | `(result: ForgeResult) -> ForgeResult` | output validation, **mutates** `result`. Called automatically by `heal()` — call manually only if you build a `ForgeResult` another way. |
| `heal` | `(doc, tolerance=None, label="", source_file="", is_structural=None) -> ForgeResult` | topology reconstruction: gap-closing, non-contour edge exclusion (candidates for "something else" — `non_contour_candidates()` exposes the same criterion, see below), loop search, outer/inner containment tree. Does **not** classify holes (D15). `tolerance=None` → reuses `doc.source_meta["tolerance"]`. If no closed outer forms, `result.is_valid=False`. `is_structural(role)->bool` decides which already-labeled edges stay in the graph — `heal()` alone knows only outer/inner; without it a labeled `"hole"` is treated as non-structural (excluded, warned). `heal_and_detect`/`split_to_files` inject `tools.manufacturing_role.is_structural` automatically. |
| `island` | `(doc, tolerance=None, island_gap=10.0, max_gap=0.5, is_structural=None) -> ForgeResult` | the other way to read a document (see "Reading drawings of views" below). Same output contract as `heal()`: one `ForgeCluster` per island (`outer` + `inners` = closed loops inside); an island whose outer lies inside another's becomes interior of the outermost one. Edges with a decided non-structural role (`frame`, `title_block`...) are left out and go to `trash_entities` with their role — same D30 contract as `heal`. No closed outer anywhere → `is_valid=False`. |
| `read_islands` | `(edges, tolerance, island_gap=10.0, max_gap=0.5) -> list[IslandReading]` | `island()` before it becomes a `ForgeResult`: per island what was decided, edge by edge. `IslandReading`: `edges`, `outer: OuterFace\|None`, `inner_loops`, `spurs`, `outside`, `non_contour`, `unclassified`, `nested_in: int\|None`. |
| `read_island` | `(edges, tolerance, max_gap=0.5) -> IslandReading` | one island: normalize (renode, `refit_tessellations`, heal's merge/weld, gaps up to `max_gap`), `split_at_crossings`, `outer_face`, classify the rest. |
| `spatial_islands` | `(edges, gap_tolerance) -> list[Island]` | union-find on edge pairs within true segment distance `gap_tolerance` (STRtree). No notion of closure. `Island`: `edges`, `bbox`, `.width`, `.height`. |
| `split_at_crossings` | `(edges, tolerance, decimals=3) -> NodedEdges` | planar network: `LineSeg`/`ArcSeg`/`CircleSeg` split wherever another edge crosses or touches them (T within `tolerance`). `NodedEdges.pieces`, `.parent_of(piece) -> Edge`. Splines/ellipses stay whole. |
| `outer_face` | `(edges, epsilon=0.0) -> OuterFace\|None` | outer contour of a planar network: walk of its outer face starting from the leftmost geometric point, per connected component, largest area wins. `OuterFace`: `polygon`, `segments`, `styles`, `loop`, `.edges`, `spurs` (walked there and back — axes, marks). |
| `refit_tessellations` | `(edges, max_segment=0.1, min_run=10, arc_fit_tolerance=0.02, node_decimals=3) -> list[Edge]` | a chain of ≥`min_run` short `LineSeg`s (a curve written as points) is refitted as arc/circle/spline; chain ends keep their original nodes. |
| heal steps | `merge_collinear_overlaps`, `merge_cocircular_overlaps`, `weld_degenerate_linesegs`, `split_labeled(edges, is_structural=None) -> (kept, labeled)`, `close_free_gaps(edges, tolerance)`, `dangling_splines(edges)`, `find_non_contour_edges(edges, tolerance) -> set[id]`, `find_loops(edges, non_contour_ids, tolerance) -> LoopSearch`, `repair_merged_corners(edges, tolerance, exclude_ids) -> (edges, n, skipped)`, `structural_loops(loops, is_structural=None)`, `loops_to_features(loops)`, `polygonize_edges(edges, tolerance) -> list[Polygon]`, `polygons_to_features(polygons)`, `edges_to_open_features(edges, exclude_ids, label_map)`, `labeled_features(edges)`, `build_hierarchy(features, label="", source_file="", is_structural=None) -> (clusters, trash)` | `heal()` is a recipe composing these, in this order (D62); compose your own (e.g. stop before `build_hierarchy`). None mutates its input. `LoopSearch`: `edges` (after corner repair — use these downstream), `loops`, `method` (`"exact"`/`"corner_repair"`/`"tolerant"`/`"none"`), `repaired`, `skipped_corners`, `unrepaired_corners`, `open_nodes`. When `method == "none"`, `heal()` falls back to `polygonize_edges` + `polygons_to_features`. |
| `detect` | `(result, features=None, *, max_drill_diameter=32.1, bending_tolerance=1.0, engrave_tolerance=1.0) -> ForgeResult` | classifies features. Bare call = only the `label_map`/`linetype_map`/`color_map` lane + topology cleanup, **no** geometric inference. `features`: `None`/`()` / `"all"` / subset of `{"holes","bending","engrave"}` (= `ALL_FEATURES`). Holes: circular inner contour Ø < `max_drill_diameter` → `Hole` (`plain`/`countersink`/`threaded`); above threshold stays a plain inner contour. **Mutates in place, also returns.** |
| `ALL_FEATURES` | `frozenset({"holes","engrave","bending"})` | the `"all"` set. |
| `describe_features` | `(cluster: ForgeCluster) -> dict` | rich per-type feature counts (`plain_holes_count`, `countersink_count`, `threaded_holes_count`, grouped bend lines, `total_engrave_length`...). `cluster.summary` is the raw always-available count; this is the detailed version for forge's known types. |
| `heal_and_detect` | `(doc, tolerance=None, label="", source_file="", features="all", max_drill_diameter=32.1, bending_tolerance=1.0, engrave_tolerance=1.0) -> ForgeResult` | `heal` + `detect`, `features="all"` by default (unlike bare `detect`). Skips `detect` if `heal` produced no valid parts. |
| `to_dxf` | `(result, source_doc=None, filter_cluster=None, include_annotations=True, include_trash=True, annotation_layer="Annotation", role_styles=None) -> ezdxf.Drawing` | renders the model to a **new** DXF (R2010), never rereads source. `source_doc` only for header vars (`$INSUNITS`...). Raises `ValueError` if `result.is_valid` is `False`. |
| `split` | `(result, source_doc=None, namer=None, include_annotations=True, min_area=50.0, exclude_types=None, on_cluster=None, annotation_layer="Annotation", role_styles=None) -> list[ezdxf.Drawing]` | like `to_dxf` but one `Drawing` per part; pure, doesn't touch disk. Parts under `min_area` mm² dropped (warning). Raises `ValueError` if invalid. |
| `inject` | `(result, data_injector=None, texts=None) -> ForgeResult` | optional CAM enrichment. **Mutates** `cluster.custom`. `data_injector(cluster, list[str]) -> dict`; `texts` must be `list[ForgeText]` from `extract_forge_texts(msp)` (positions needed for per-part geometric filtering). No-op without `data_injector`. |
| `anchor_annotations` | `(result, snap_distance=0.0) -> ForgeResult` | assigns `Annotation.cluster_ref` — which cluster an annotation belongs to, by containment (+ optional snap distance for annotations just outside). |
| `split_to_files` | `(doc, output_folder, label="", source_file="", tolerance=None, namer=None, include_annotations=True, min_area=50.0, exclude_types=None, annotation_layer="Annotation") -> ForgeResult` | full multi-part flow + disk write: `heal → detect → split → .saveas()`. Filename `f"{cluster.label}.dxf"`. **Only** forge function that writes to disk. |
| `to_json` / `save_json` | `(result, indent=2, extra_metadata: Callable[[ForgeCluster], dict]=None) -> str / None(writes path)` | per-part metadata per `rules/metadata_schema.py`, no coordinates. `extra_metadata(cluster)` called once per cluster, result merged in outside the schema. |
| `save_xml` | `(result, path, extra_metadata=None) -> None` | same fields as `save_json`, XML. |
| `to_view_model` | `(result, tolerance=0.05, include_trash=True, include_annotations=True) -> dict` | render-oriented JSON: every feature's coordinates + role + hex color, **discretized to polylines**. Feeds `to_svg`; usable by an external renderer. |
| `to_svg` / `save_svg` | `(result, tolerance=0.05, include_trash=True, include_annotations=True, padding=0.03, background="#1e1e1e", holes_as_circles=True, stroke_width=None, size=None, units=None) -> str / None(writes path)` | SVG render, one `<g data-cluster>` per part, Y flipped. `units="mm"` = true-scale for CAM import. Geometry still discretized — use `to_dxf` for cutting-fidelity output. |
| `write_metadata_to_dxf` / `read_metadata_from_dxf` | `(doc, cluster, extra=None) -> None` / `(doc) -> dict` | writes/reads the `save_json` fields as `FORGE` XDATA on the `OuterContour`-layer entity. |
| `set_schema` | `(schema: dict) -> None` | replaces the active metadata schema at runtime (for pip-installed use where you can't edit `metadata_schema.py`). |
| `extract_forge_texts` | `(msp) -> list[ForgeText]` | texts with position — the required `texts=` arg for `inject`. |
| `extract_texts_from_msp` | `(msp) -> list[str]` | texts as bare strings — **not** usable by `inject`. |
| `inspect_dxf` / `inspect_document` / `inspect_result` / `inspect_file` | see below | 3-level debug print, stdout only. |
| `normalize_role` / `is_structural_role` | `(value) -> str` / `(role) -> bool` | role-vocabulary primitives (see below). `is_structural_role` is the engine's own minimal predicate (outer/inner only) — the *extended* one detect uses is `tools.manufacturing_role.is_structural`. |
| `RoleStyle` | `dataclass(color: tuple[int,int,int]|None, linetype: str|None, lineweight: float|None, layer_name: str|None)` | per-role visual override for `to_dxf`/`split` via `role_styles={role: RoleStyle(...)}`. `None` fields keep forge's default. Wins over anything `register_role_style` registered for the same role. |
| `register_role_style` | `(role, style: RoleStyle) -> None` | registers a `RoleStyle` **once**, applied to every later `to_dxf`/`split` automatically — same idiom as `set_schema`. `tools.manufacturing_role` uses this exact call (no special privilege) to register its own default colors/layer names at import time. |
| `non_contour_candidates` | `(doc, tolerance=None) -> list[Edge]` | same topological criterion `heal()` uses internally to exclude an edge from the contour graph (branching + centroid outside its connected component's convex hull, D49) — asserts **no** meaning (not "bending", not anything). `detect()`'s `_detect_bending` is just one interpretation of these candidates, not privileged. A consumer that never calls `detect()` (framer, the interpreter) and wants a different interpretation (a raised-feature edge in a plan view is not a bend line) calls this to get the same candidate set without re-deriving the criterion, then sets `edge.role` on the returned `Edge`s (references into `doc.edges` — mutation is reflected there) **before** `heal()`. Runs on `doc.edges` as-is, before `heal()`'s own merge/gap-closing preprocessing — meant to decide roles pre-`heal()`, not to predict its exact excluded set to the edge case. |

### Debug/inspect (stdout only, 3 levels in order)

```python
forge.inspect_dxf(path, entities=True, limit=40)          # L1: raw DXF entities, no forge
forge.inspect_document(doc, graph=True, limit=60)         # L2: ForgeDocument — what the adapter understood
forge.inspect_result(result, coords=False)                # L3: ForgeResult — what forge produced
forge.inspect_file(path, tolerance=0.05, label_map=None,
                    run_heal=True, run_detect=True, ...)  # orchestrates all three
```

## Domain types

**`ForgeDocument`** (from `load_dxf`/`document_from_msp`/`load_geometry`): `edges: list[Edge]`, `annotations: list[Annotation]`, `source_meta: dict`, `source_path: str`, `warnings: list[str]`.

**`ForgeResult`** (from `heal`, enriched by `detect`/`inject`): `clusters: list[ForgeCluster]`, `is_valid: bool` (**check before render**), `warnings`/`errors: list[str]`, `trash_entities: list`, `annotations: list[Annotation]`, `classified_entities: list`, `all_arcs: list[ArcSeg]`, `cluster_count` (property). `.to_dict()` for JSON.

**`ForgeCluster`**: `outer: ForgeContour`, `inners: list[ForgeContour]`, `label: str`, `custom: dict` (from `data_injector`), `detected: DetectedFeatures|None` (open-by-name overlay, `None` until something writes to it — D44), `.features(name)` → collection or `[]` (`"holes"` → `list[Hole]`, `"bending_lines"` → `list[BendingLine]`, `"engrave_lines"` → `list[Engraving]`, or a custom name a third party attached), `.summary` property (raw `{name}_count` for every `detected` collection, `{}` if `detected is None`), `.area`, `.bbox`. `ForgeContour` also has `.depth`/`.parent` (D34) — position in the containment tree, needed e.g. by `bridge_tabs`.

A third party attaches its own detection the same way `detect()` does:
```python
cluster.detected = cluster.detected or DetectedFeatures()
cluster.detected.attach("flange_view_hint", [...])
cluster.features("flange_view_hint")   # reads it back
```

**`ForgeContour`**: `role: ContourRole`, `polygon` (shapely), `segments` (native primitives), `.area`, `.bbox`.

**`Annotation`** → `Note`/`Dimension`/`Leader`: `kind` (`"TEXT"`/`"MTEXT"`/`"DIMENSION"`/`"LEADER"`/`"MULTILEADER"`), `position (x,y)`, `data: dict`, `cluster_ref` (set by `anchor_annotations`).

**`ForgeText`** (from `extract_forge_texts`): `content: str`, `position: shapely.Point` — the only shape `inject()` accepts.

## Roles — open vocabulary

**The engine (`core`/`model`) knows exactly three roles**: `unknown`, `outer`, `inner` — nothing else, by design (MAP.md D47, "roles out of core"). Everything else — `hole`/`countersink`/`threaded_hole`/`bending`/`engrave`/`marking` included — is vocabulary owned by `tools.manufacturing_role`, imported by `detect()` and nothing under `core`/`model`. `detect()` gets **no special privilege**: it registers/uses roles through the exact same public mechanisms (`register_role_style`, `heal(is_structural=...)`) a third-party consumer would.

**Any role string is legal** — a consumer can assign anything (`"frame"`, `"title_block"`, `"hole"`, `"section"`...); it passes through `normalize_role()` (slugified `[a-z0-9_-]`, ≤64 chars), forge keeps it without raising, writes it to its own DXF layer on output (`unknown` → `Trash`). Whether `heal()` keeps a labeled edge **inside the topology graph** (structural) or excludes it (decoration) depends entirely on the `is_structural` predicate you pass it:

- No predicate (bare `heal(doc)`): only `outer`/`inner` count as structural. A `label_map`-tagged `"hole"` edge is excluded from the graph, ends up in `trash_entities`, and `heal()` appends a warning.
- `heal(doc, is_structural=forge.tools.manufacturing_role.is_structural)`: also recognizes `hole`/`countersink`/`threaded_hole` as structural (they're real part contours, not decoration) — `bending`/`engrave`/`marking` and any unknown consumer role still get excluded. `heal_and_detect()`/`split_to_files()` pass this automatically — no action needed on the 90% path.

To mark geometry before `heal` excludes it from the graph: set `edge.role = forge.normalize_role("frame")` on `doc.edges` entries.

### Building your own role + palette (external-tool recipe)

A tool built on top of forge (framer, bendly, the interpreter, or your own)
defines its own roles the same way `tools.manufacturing_role` does for
forge's own `detect()` — **no privileged path exists**, this is the only
mechanism. Minimal pattern, one module in your own project:

```python
# your_tool/roles.py
FLANGE_UP = "flange_up"          # any slug — normalize_role() sanitizes it anyway

def is_structural(role) -> bool:
    """
    Only needed if your role marks REAL part-contour geometry (like a hole) —
    something that must stay inside heal()'s loop-finding graph. Skip this
    entirely if your role is decoration/annotation (like frame/title_block):
    forge's default (no predicate) already excludes anything non-outer/inner,
    which is what you want.
    """
    from forge.model.role import is_structural_role
    return is_structural_role(role) or role == FLANGE_UP

def register_defaults() -> None:
    import forge
    forge.register_role_style(FLANGE_UP, forge.RoleStyle(
        color=(255, 165, 0), layer_name="FlangeUp",
    ))

register_defaults()   # call at your module's import time, same as manufacturing_role.py
```

Then, in your pipeline:

```python
import forge
import your_tool.roles as roles

doc = forge.load_dxf("part.dxf", label_map={"FlangeMarks": roles.FLANGE_UP})
result = forge.heal(doc, is_structural=roles.is_structural)   # only if FLANGE_UP is structural
result = forge.detect(result, "all")
forge.to_dxf(result, doc)   # FlangeUp layer, orange — registered once, applies automatically
```

That assumes the CAD source already puts flange edges on their own layer
(`label_map={"FlangeMarks": ...}`). When it doesn't — you only know
geometrically that an edge sits where a bend line *would* sit (both endpoints
on a branching node, interior to its shape's hull) and have to decide for
yourself whether it's really a bend or a raised-feature edge — use
`non_contour_candidates(doc)` instead of a `label_map` layer:

```python
for edge in forge.non_contour_candidates(doc):
    if your_tool.looks_like_flange(edge):     # your own geometry/cross-view logic
        edge.role = roles.FLANGE_UP

result = forge.heal(doc, is_structural=roles.is_structural)
```

Same candidates `heal()` would have excluded and left as `role="unknown"` in
`trash_entities` anyway — this just lets you label them with your own meaning
before `heal()` runs, instead of after, and instead of `detect()`'s default
guess (`"bending"`, confidence 0.9) if you were calling `detect()` at all.

If your role is purely decorative (never part-contour geometry), skip
`is_structural` entirely and skip passing anything to `heal()` — the default
already keeps it out of the graph and routes it to its own named layer via
`normalize_role`. `register_role_style` is what gives it a color/layer name
instead of the generic gray "consumer role" fallback. To attach richer
per-feature data (not just a color), use the `cluster.detected` overlay
instead — see `ForgeCluster` above.

## Reading drawings of views: `island()`

`heal()` reads from the inside (who touches whom, which loops close, which is
inside which). On a drawing of views — several views on a sheet, isometric/3D
projections, near-coincident silhouette lines — that graph is ambiguous.
`island()` reads from the outside: islands by proximity → planar network →
outer face → interior. Choose by the drawing:

| drawing | call |
|---|---|
| flat cutting file, one or more separate parts, exact geometry to stitch | `heal()` / `heal_and_detect()` |
| technical drawing with views (plan, side, isometric) on a sheet | `island()` |

What `island()` does **not** know: which island is a view, a part, the frame,
the title block, a magnifier circle over a view, a break line. Those are
roles — the caller's job (D21, D30). With the frame still in the drawing, the
frame is the only outer and every view becomes its interior.

### Consumer recipe (framer / a drawing reader)

```python
import forge

doc = forge.load_dxf("sheet.dxf")

# 1. your own semantics: mark what is not part geometry, by role
for edge in doc.edges:
    if my_tool.is_frame_or_title_block(edge) or my_tool.is_magnifier_circle(edge):
        edge.role = forge.normalize_role("frame")     # any non-structural slug

# 2. read the rest by islands — marked edges are left out (trash, with their role)
result = forge.island(doc, island_gap=10.0)
for cluster in result.clusters:                     # one view (or part) each
    cluster.outer.polygon, cluster.inners

# 3. need the details per edge (what was a spur, what stayed outside)?
edges = [e for e in doc.edges if e.role == "unknown"]
for reading in forge.read_islands(edges, tolerance=0.05, island_gap=10.0):
    reading.outer, reading.spurs, reading.outside, reading.non_contour, reading.nested_in
```

Composing your own reading from the bricks (same pieces `island()` uses, no
duplicated criteria): `spatial_islands` → `refit_tessellations` →
`split_at_crossings` → `outer_face`. `island()` never calls `heal()`.

Parameters to tune per client/drawing convention, never guessed by forge:
`island_gap` (layout spacing between views), `max_gap` (drawing gaps closed on
a view, default 0.5 mm — a view is not a cutting file).

## Hard rules (violate these = broken output)

- `heal()` never classifies holes/bends — that's `detect(features=...)`, opt-in.
- Bare `detect(result)` does **only** the label/linetype/color lane + cleanup — no geometric inference without `features=`.
- **Always check `result.is_valid` before `to_dxf`/`split`** — they raise `ValueError` otherwise.
- `tolerance` default `0.05`; a gap ≥ 4× tolerance is **not** auto-closed (deliberate — raise `tolerance` or fix the source).
- `label_map`/`linetype_map`/`color_map` are `load_dxf`/`document_from_msp` params, **not** `heal`/`detect` params.
- `to_dxf`/`split` never re-read the source file — they render from the model only.
- Splines are re-emitted as native `SPLINE`, engraving as native per-primitive entities — **never** discretized to `LWPOLYLINE` in DXF output. `to_svg`/`to_view_model` **do** discretize everything (visualization only, not cutting-fidelity).
- Nothing is silently dropped: unclassified geometry → `trash_entities`/`Trash` layer, unmodeled DXF types (`HATCH`,`IMAGE`,`TABLE`,`3DFACE`,`XLINE`...) → warning in `doc.warnings`.
- `island()` and `heal()` are two readings, not two steps: never chain them on the same document. Both return a `ForgeResult`; `detect()`/`to_dxf()`/`split()` work on either.
- `island()` puts closed loops inside an outer in `inners` without saying hole or face — same as `heal()` (D15).
- `inject()` needs `texts` as `list[ForgeText]` (`extract_forge_texts`), not `list[str]` (`extract_texts_from_msp` — different function, wrong shape for `inject`).

## Experimental — importable, not in `__all__`, no stability guarantee

Not documented in `API.md` until proven by a real caller. Import path shown since they aren't `forge.<name>` re-exports beyond the ones listed.

| name | import | signature | does |
|---|---|---|---|
| `rotate_result` | `forge.rotate_result` | `(result, angle_rad, origin=(0,0)) -> ForgeResult` | rigid-rotates an already-healed result; no re-heal (rotation doesn't change topology). |
| `rotate_cluster` | `forge.rotate_cluster` | `(cluster, angle_rad, origin=(0,0)) -> ForgeCluster` | same, one cluster. |
| `rotate_document` | `forge.rotate_document` | `(doc, angle_rad, origin=(0,0), tolerance=0.05) -> ForgeDocument` | rotates a raw pre-heal `ForgeDocument`. |
| `rotate_to_longest` | `forge.rotate_to_longest` | `(result, include_inners=False, target_angle_deg=0.0, origin=None) -> (ForgeResult, float)` | finds the longest structural segment, rotates the result so it lands at `target_angle_deg`; returns result + angle applied. |
| `simplify_points` | `forge.simplify_points` (module: `forge.core.primitives.fitting`) | `(points: list[Point], closed=True, angle_threshold_deg=50.0, min_points_for_spline=4, spline_degree=3, duplicate_tolerance=1e-6, arc_fit_tolerance=None) -> list[LineSeg\|ArcSeg\|CircleSeg\|SplineSeg]` | reconstructs primitives from a dense ordered point sequence (corner detection + refit). Feeds `load_geometry`'s `"spline"` entity type. |
| `bridge_tabs` | `forge.tools.tabs.bridge_tabs` | `(parent_points, child_points, anchor_parent, anchor_child, tab_width) -> BridgeTab` | one positioning tab between a nested island and its direct parent contour — geometric construction, returns 2 flank segments + 4 cut points. |
| `bridge_nested_tabs` | `forge.tools.tabs.bridge_nested_tabs` | `(cluster, tab_width, tab_count=4, discretize_tolerance=0.05) -> list[NestedBridgeResult]` | walks `cluster.inners`, places `tab_count` tabs on every even-depth (≥2) island against its direct parent, in one pass. Scope: line/arc/polyline/circle contours, not spline yet. |

Also recent but stable/documented already: `EllipseSeg` (5th primitive, `"ellipse"` in `load_geometry`), the `"spline"` entity type in `load_geometry`, `RoleStyle`, `ForgeContour.depth`/`.parent`, `cluster.detected`/`.features()` open overlay.

## Module layout (only if you need to import something not re-exported)

```
forge/adapters/   format → primitive translation (dxf, pdf[frozen], geometry)
forge/core/       pure geometry engine: primitives (+ fitting: simplify_points), topology (+ noding, outer_face),
                  healing (+ islands), heal(), island()
forge/model/      the domain: ForgeDocument, ForgeResult, ForgeCluster, Annotation, role.py
forge/tools/      optional ForgeResult stages: detect, anchor, inject, rotate, tabs
                  manufacturing_role.py: hole/countersink/threaded_hole/bending/engrave/marking
                  vocabulary — never imported by core/model (MAP.md D47)
forge/io/         renderers: dxf.py, svg.py, view_model.py, exporter.py (json/xml/xdata)
forge/rules/      palette, metadata schema, validator
forge/recipes.py  heal_and_detect, split_to_files
forge/inspect.py  3-level debug
```
Dependency rule: `core`/`model` never import `adapters`/`tools`/`io`. Everything else imports `core`/`model`/`rules`.
