# MAP.md — forge decision log

This file is the **memory of decisions**: what was decided, and above all
*why*. It is not documentation (that's `docs/`) and not a session log (that's
the git log).

Rule: a closed decision is **not re-decided from scratch**. If it needs
reopening, say so explicitly — "reopening decision N".

- **What forge is, how to use it** → `README.md`, `docs/API.md`
- **How it's built inside** → `docs/ARCHITECTURE.md`
- **Refactor history** → git log

---

## The public API contract

```python
doc    = forge.load_dxf("file.dxf")        # the only point that touches ezdxf for reading
result = forge.heal(doc)                   # topology — zero DXF
result = forge.detect(result, "all")       # semantics/features — zero DXF
doc_out = forge.to_dxf(result, doc)        # a new document — no source_ref
doc_out.saveas("output.dxf")

# multi-part
forge.split_to_files(doc, "output/")       # the only function that writes to disk

# future: same contract, a different adapter
doc = forge.load_svg("file.svg")
```

**Guiding principle:** `load_*` produces a `ForgeDocument` of pure data (edges
+ annotations). After loading, the source `ezdxf` document disappears.
`heal`/`detect` never see a format. `to_dxf` builds a **new** document from the
model's own segments — it never copies entities from the source, never carries
`source_ref`. The model is the product; DXF is only one of its
representations.

Full detail of every function in `docs/API.md`.

---

## Summary of concluded phases

- **Phases 1–4 (`refactor/structure`, closed)** — the healing engine
  hardened: one unified DXF entity→primitive dispatcher (which surfaced and
  fixed a real major-arc bug), the `OpenShape`/`ClosedShape` bridge replaced
  by native `OpenFeature`/`ClosedFeature`, `inject()` slimmed to just the
  external-enrichment hook, a 3-level inspector, `load_pdf` frozen, a single
  version source, and SVG output (`to_view_model`/`to_svg`).
- **Module reorganization (Sep 2026)** — `ForgePart`→`ForgeCluster` (D21),
  `pipeline/` dissolved into `core`/`tools`/`io` (D22), numbered scripts
  moved to `scripts/` with CWD-independent paths (D23), dead frame-detector
  code removed (D24), `core/classification/` folded into `tools/` (D25),
  `model/` tidied (D26), `ContourRole` opened to consumer-defined roles that
  get their own DXF layer (D27, D30, D31), `RoleStyle` for per-role
  color/linetype/weight overrides (D37).
- **Annotations & interpretation boundary (Sep 2026)** — one typed
  `Annotation` model replacing two parallel untyped ones (D20); the
  geometric anchoring step renamed `anchor_annotations` to stop overloading
  the word "interpret" (D43); frame/title-block/callout/view-grouping work
  spun out to a future sibling module, `Framer` (D29) — forge stays neutral,
  `Framer` and the interpreter sit above it.
- **Geometry reconstruction toolkit (Sep 2026)** — `load_geometry` made
  public (D32) and extended to splines (D35); `simplify_points`/
  `fit_primitives` built for point-sequence → line/spline (D33) and
  line/arc/spline (D36) reconstruction, plus two real spline-fidelity bugs
  found and fixed along the way (`_fit_spline` closed-loop flags, D41;
  `SplineSeg.discretize()` evaluating the control polygon instead of the
  curve, D42); `bridge_tabs`/`bridge_nested_tabs` for tabs joining nested
  contours across arbitrary depth (D40, superseding the single-contour
  `cut_tabs`, D39).
- **`detect()` overlay (Sep 2026, D44)** — `ForgeCluster.detected` replaces
  fixed `holes`/`bending_lines`/`engrave_lines` fields with an open-by-name,
  `None`-until-written overlay, so any tool — not just forge's own
  `detect()` — can attach a named feature collection without a schema
  change.

---

## Current status

Branch: `main`, version `0.6.18`. Suite: 671 passed + 62 subtests as of the
latest decision below (D44), golden all green.

Still genuinely open:
- `detect_engrave` remains a no-op placeholder (D13) — deferred until
  Federico gets to it.
- Where the hole/countersink/threaded/engrave/marking role taxonomy should
  live (raised alongside D37) — unresolved, needs a redesign (a `structural`
  flag on the role itself instead of a fixed imported list), not a priority
  yet.
- A dashboard is designed as its own repo (D16) but not started.

Everything else that used to sit in an old to-do list here has been resolved
or turned moot: the script rewrite and `to_view_model`/`to_svg` shipped, the
`refactor/structure` branch merged into `main` long ago, and the planned
reorganization of `io/text_utils.py` became moot once D20 deleted that file
outright.

---

## CLOSED DECISIONS

### D1 — Library name: stays `forge` (for now)
`heal` as a package name was considered and rejected (`from heal import heal`
reads badly). `dxf-forge` is misleading — too tied to the file format, when
the point is that the model is format-agnostic — but the rename is deferred.
Importable package: `forge`.

### D2 — `heal_and_detect(doc)` as the 90%-path function ✅
Top-level function doing `heal → detect`, returning the `ForgeResult`. Goes in
the README. `heal()`/`detect()` stay separate and public — a renderer or
nesting tool may want topology alone. Deliberately explicit, slightly awkward
name — a human choice, not "process". `detect()` is skipped if `heal()`
produces no valid parts.

### D3 — `detect()`/`inject()` return the result ✅
They no longer return `None` — they return the (same, mutated) `ForgeResult`,
making the chain explicit: `result = forge.detect(result)`. No test depended
on the `None`.

### D4 — `OpenShape`/`ClosedShape` (bridge) eliminated ✅
`heal` now produces `OpenFeature`/`ClosedFeature` directly; `bridge/shape.py`
deleted. `pts`/`length`/`shape_type` are derived from native segments via
`core/geometry.py`. `OpenFeature`/`ClosedFeature` (`model/feature.py`) are
kept — the "has a polygon / doesn't" distinction is honest and gives
`area`/`bbox` for free. The most invasive change of Phase 4, done sub-step by
sub-step against the golden suite.

### D5 — `source`/`confidence` on detected features ✅
`Hole`, `Engraving`, `BendingLine`, `ClassifiedEntity` stay four separate
types — four manufacturing intents with different consumers. Each carries
`source: str` + `confidence: float`, populated in `detect.py`: the geometric
lane sets `source="geometric"`, the `label_map` lane sets
`source="labeled"`/`confidence=1.0`. **No inheritance hierarchy** — a
convention, not a class tower. `ClassifiedEntity` stays outside the `Feature`
hierarchy by choice (a dict-based escape hatch). Invariant: after `detect()`,
every feature has sensible `source` + `confidence`.

Final model shape:
```
Feature (role)
├── ClosedFeature (polygon, segments) → ForgeContour, Hole
└── OpenFeature   (segments)          → Engraving, BendingLine
ClassifiedEntity  → catch-all, dict-based, outside the hierarchy by choice
```

### D6 — `parse_loop` → `segments_from_loop` ✅
Renamed and moved from `adapters/dxf/parser.py` to
`core/topology/loop_finder.py` (pure domain logic, not DXF parsing).
`_reverse_segment` removed: `LineSeg`/`ArcSeg`/`CircleSeg` gained
`.reversed()` like `SplineSeg` already had.

### D7 — One entity→primitive dispatcher ✅
`parser.py::DxfEntityDispatcher` and `adapter.py::entity_to_primitive` were
near-duplicate copies. Now a single `DxfEntityDispatcher`, used by both
production and tests. **Latent bug found and fixed:** `ArcSeg.from_chord` got
major arcs wrong (`|bulge| > 1`, sweep > 180°) — it used
`sqrt(r² - half_chord²)` (always positive → always a minor arc) instead of the
signed `r·cos(sweep/2)`. It had been masked because production used
`adapter.py`'s correct `_bulge_to_arc`. 5 golden roundtrips caught it the
moment the dispatcher was unified.

### D8 — `inject()` slimmed down ✅
Feature counts (holes by type, bends, engravings, marking) are now
`ForgePart.summary`, a property derived from the model — no longer copied into
`part.custom` by `inject()`. `inject()` now exists only for the external
`data_injector` hook (material/thickness/code from texts); without one it does
nothing. Equivalence proven before touching fixtures (`part.summary ==
inject().part.custom` on all 63 golden parts, 0 mismatches), then a surgical
`"custom"` → `"summary"` rename in fixtures.

### D9 — the inspector becomes a 3-level tool ✅
`dxf_inspect.py` (dead, broken imports) → `forge/inspect.py`, exported. Prints
three levels: (1) raw DXF entities — "what's in the file"; (2)
primitives/edges/graph after `load_dxf` — "what the adapter understood"; (3)
the model after `heal`/`detect` — "what forge produced". For working on real
files.

### D10 — `load_pdf` frozen ✅
Returns `list[Edge]`, not a `ForgeDocument` → `forge.heal()` rejects it.
Removed from `__all__`, marked experimental. Code untouched, still importable
as `forge.load_pdf`. PDF support to be picked up later (or never).

### D11 — Version: single source = `pyproject.toml` ✅
`forge.__version__` reads it via `importlib.metadata.version("forge")`,
fallback `0.0.0+dev`. Nothing else is updated by hand except `pyproject`.

### D12 — SVG: output only, splines discretized ✅
`to_svg(result)` is a model renderer; arcs/circles/splines are flattened to
polylines (fine for viewing, not for cutting). No `SvgAdapter` on input until a
real SVG file shows up.

Implemented in two pieces (`forge/io/`):
- **`to_view_model(result)`** — `ForgeResult` → a JSON dict with every
  feature's geometry + role + hex color. The real contract for an external
  renderer (a JS dashboard).
- **`to_svg`/`save_svg`** — batteries-included SVG built on top of the view
  model. One color per role (a palette shared with DXF), Y flipped, one part =
  one `<g data-part>`, holes as real `<circle>`s.
- `forge/rules/palette.py` extended: `ROLE_TO_COLOR` + `ACI_TO_HEX` +
  `role_to_hex()` (no dependency on ezdxf or the format).

### D13 — `detect_engrave`: deferred
`_detect_engrave` stays a no-op placeholder. The seam is already in
`detect()`'s pipeline (`engrave_tolerance` parameter). When implemented: look
at inner contours with UNKNOWN role and `result.trash_entities`, promote
recognizable patterns (e.g. two near-parallel polylines closer than
`tolerance`) to `Engraving(source="geometric")`. Federico will implement it
once other things are in order.

### D14 — Numbered root scripts: kept, but rewritten
Federico uses them as an API-learning gym. Updated decision: not only kept,
but rewritten and renumbered — ideally one script per `forge.__all__`
function, defaulting to `tests/examples/` so they run with zero setup.
`.gitignore` already covers their output. `13_ARC_splitter` is out of scope
for this work — production code on client files, to be ported to the new API
separately and validated by Federico with his SigmaNest overlay check.

### D15 — `detect()` made parametric; hole classification moved there ✅
Principle: `HOLE_DIAMETER_THRESHOLD` (32.1 mm) is a **process parameter** —
the machine/tool's drilling capacity — not a domain constant. Process
parameters belong to the classification call, not to topology.

Final shape:
- `heal` produces **only** the containment tree: `ForgePart(outer,
  inners=[ForgeContour...])`, zero `Hole`.
- `detect()` is parametric: bare `detect(result)` → laser-cut default,
  `label_map` lane only (authoritative) + topology cleanup, zero `Hole`;
  `detect(result, "holes"|"bending"|"engrave"|"all")` → opt-in geometric
  lanes; `max_drill_diameter` (default 32.1) is a `detect()` argument: Ø
  below → `Hole`, Ø at/above → stays a `ForgeContour` inner.
- `heal_and_detect(..., features="all")` is the 90% path.
- `ClosedFeature.diameter`/`.center` removed: circular geometry comes from
  `core/geometry.circular_geometry`.

Verified across all golden fixtures (`features="all"`): diff on only 7 files,
where circles Ø ≥ 32.1 migrate from `Hole(role="inner")` to
`ForgeContour(role=INNER)` — the intended behavior. Side effect: the old
`Hole(role="inner")` bug from `hierarchy` disappears on its own.

### D16 — Dashboard: a separate repo, not a branch
A future dashboard/UI is an app with its own dependencies (web server or GUI
toolkit) and its own release cycle — it shouldn't pollute the library repo. It
goes in its own repo that does `pip install forge`, like `snapmark` already
does. The `dev_tools/` prototypes (`dashboard.py`, `dashboard_2.py`,
`split_verify*.py`, `dxf_kernel*.py`) are the starting point.

### D17 — World XY position is preserved (invariant, not a decision)
Logged here because it's a guarantee the production flow relies on (split →
import into SigmaNest → overlay the original for a registration check). The
pipeline never translates geometry: `load_dxf` sanitizes the OCS and flattens
Z; `heal` only touches endpoints to close gaps; `to_dxf`/`split` write segment
`center`/`pts` verbatim. Every split part lands at the same absolute XY as the
source. Only intended loss: Z flattened to 0 (correct for sheet/laser).
`test_golden_split` guards this invariant with absolute-coordinate comparison.

### D18 — `to_nester_input`: out of `__all__`, experimental
forge does not do nesting (arranging parts on a sheet to minimize scrap) and
won't, unless a client commissions and pays for it. `to_nester_input` was
written early for a nester that never happened. Same treatment as `load_pdf`
(D10): code stays, importable, but out of `__all__` and undocumented. Geometry
serialization for renderers/tools is `to_view_model` (D12).

### D19 — `adapters/bridge/` eliminated, `Edge` moved to `core/topology/edge.py` ✅
Flagged by Federico: `bridge/` had been left with a single file (`edge.py`)
after `shape.py` was removed (D4) — a folder smell. Deeper issue: `Edge` lived
under `adapters/` but `core/topology/graph.py`, `loop_finder.py`,
`bending_detector.py`, `core/healing/gap_solver.py` and `core/adapter_base.py`
all imported it from there — **`core` depended on `adapters`**, the exact
opposite of the dependency rule (`docs/ARCHITECTURE.md`). `Edge` is not a
primitive (those are pure math in `core/primitives/segments.py`): it's a
topological wrapper (role/style/provenance) around a primitive — it belongs in
`core/topology/`, where its real consumers live. Moved there; DXF/PDF adapters
now import it from `core`. No behavior change. Suite: 579 passed.

### D20 — Annotations: typed model + separate `interpret` phase ✅
Flagged by Federico: annotations were a mess — two parallel, untyped models
for the same thing: `Annotation(kind, position, data=dict)` in
`model/document.py` (from `annotation_extractor.py`, consumed by `write()`),
and `ForgeText(content, position: shapely.Point)` in `model/text.py` (from
`io/text_utils.extract_forge_texts`, consumed by `inject()`) — reading the
same DXF entity twice. `io/text_utils.py` and `annotation_extractor.py` also
imported each other.

Decision:
- **One typed model** in `model/annotation.py`: `Annotation` base +
  `Note`/`Dimension`/`Leader`, plus `RenderedGeometry`/`RenderedText` for the
  flattened image of dimensions/leaders. No `data` dict, no `shapely` in
  fields. `Annotation(data=dict)` and `ForgeText` removed.
- **Adapter = format only.** `annotation_extractor` reads DXF → typed objects;
  `write` does the reverse, faithfully. MTEXT string helpers live in
  `adapters/dxf/mtext.py`.
- **Interpretation gets its own phase**, `forge.interpret_annotations(result)`
  (later renamed `anchor_annotations`, D43) — not inside `detect()`, which
  already does too much. Populates only `Annotation.part_ref` (containing-part
  index); `references`/`target` toward features are stubbed but not computed.
- `inject()` no longer takes `texts=`/`msp`: it filters `result.annotations`
  by containment. `io/text_utils.py` and its two extraction functions removed
  — no real caller, clean break.

Regression found and fixed along the way (`b5b2503`): text-only MULTILEADERs
with no anchor/vertices/geometry (Solid Edge) were being dropped. New golden
fixture added, plus two known pre-existing bugs on it (bending lines
under-detected; title block detected as a cluster — see `TODO.md`). Suite: 610
passed.

### D21 — `ForgePart` → `ForgeCluster` ✅
`heal()` produces **clusters**: spatially separate geometry groups. A cluster
*may* be a workable part, but could also be a view, a section, a detail, or
the title block — "part-ness" is the consumer's interpretation, not something
forge decides. The name `ForgePart` promised a semantics forge doesn't
provide.

Mechanical rename, zero logic changed: `ForgePart`→`ForgeCluster`,
`result.parts`→`result.clusters`, `part_count`→`cluster_count`,
`Annotation.part_ref`→`cluster_ref`, and so on. Output keys renamed
accordingly (JSON/XML/view-model/SVG). Golden regenerated on keys only — no
geometric value touched. Breaking: JSON/XML key names change; no real consumer
read them yet. Suite: 610 passed. Branch `refactor/clusters`, `main` → 0.6.3.

### D22 — `pipeline/` dissolved: `heal`→core, `tools/`, renderers into `io/` ✅
Flagged by Federico: `pipeline/` wasn't "a thing" — it mixed three different
kinds of module, and the name implied a fixed sequence the library doesn't
impose.

- **`heal.py` (`HealStep`+`heal()`) → `forge/core/heal.py`.** The engine's core
  act: `ForgeDocument`→`ForgeResult`. Not optional — every other step works on
  its output.
- **`detect.py`/`interpret.py`/`inject.py` → `forge/tools/`.** Optional,
  composable stages on a `ForgeResult`: each enriches it in place and returns
  it, the caller picks which and in what order — the pattern a future drawing
  interpreter (separate project) generalizes.
- **`write.py` (`to_dxf`/`split`) → `forge/io/dxf.py`.** Renderers of the
  model, exactly like `to_svg`/`to_json`/`to_view_model`.
- **`heal_and_detect`/`split_to_files` → `forge/recipes.py`.** The "90% path"
  shortcuts.
- `forge/pipeline/` and the always-empty `forge/workflow/` deleted.

No behavior change — only files moved and imports updated. `forge.__all__`
unchanged. Suite: 610 passed. Branch `refactor/module-layout`, `main` →
0.6.4. (Frame detection was noted here as belonging to the future interpreter
but staying in forge until that repo existed — superseded by D24.)

### D23 — Numbered scripts moved to `scripts/` + `_paths.py` doing `chdir` ✅
Updates the "at the root" part of D14. Federico worked by copying a script
wherever and hand-writing `INPUT = r"..."`. The real pain wasn't *where* the
scripts live but that a relative path depends on the working directory:
`python scripts/03_detect.py`, VS Code's Run button, and a terminal opened
inside `scripts/` all gave different CWDs. One way, finally: scripts live in
`scripts/`; the first line of each is `import _paths` (`scripts/_paths.py`
does `os.chdir()` to the repo root); `CONFIG` just writes the raw path
(relative from the repo root, or absolute). `13_ARC_splitter` moves to
`scripts/` for consistency but stays out-of-series.

### D24 — Frame detector removed from forge (it was dead code) ✅
Supersedes D22's note. `core/classification/frame_detector.py` and
`adapters/dxf/frame_adapter_dxf.py` were already dead: no test or script
called them, the adapter imported from a path that didn't exist, and
`detect_frame()` had a stray debug `print`. Frame/title-block recognition is,
by decision, the future interpreter's job (memory
`forge-neutral-substrate-agent-layer-above`): it runs *before* `heal` on raw
geometry, which forge doesn't do. Both files deleted (in git history). The
algorithm (ISO √2±5% ratio rectangles + ≥80% containment, conservative) stays
documented in `INTERPRETER.md`/`FRAMER.md` as the spec for the future `Framer`
module. `ContourRole.FRAME` stays in forge as just a label a consumer can
assign — not detection logic. Branch `refactor/kill-frame-deadcode`.

### D25 — `core/classification/` dissolved: `hole_detector` → `tools/` ✅
Only one file left after D24. Flagged by Federico: the folder looked like a
project of its own inside `core/`, out of place. `is_threaded_hole`/
`is_countersink_outer` are recognition heuristics used only by
`tools/detect.py`, not reusable base geometry — they belong under `tools/`
next to their consumer. Moved to `forge/tools/hole_detector.py`. `core/` is
now only the deterministic geometric engine. Suite: 610 passed.

### D26 — `model/` tidied: `ForgeContour` gets its own file ✅
Flagged by Federico: `cluster.py` defined both the container (`ForgeCluster`)
and one of its elements (`ForgeContour`), inconsistent with
`hole.py`/`engraving.py`/`bending_line.py`. `ForgeContour` → `model/contour.py`.
`BaseInterpreter` (an ABC with no implementer, referencing a pre-refactor
`msp` concept) deleted. `ClassifiedEntity` stays in `model/` —
`ForgeResult.classified_entities` holds it, and moving it to `tools/` would
make `model/` depend on `tools/`. Suite: 610 passed.

### D27 — `ContourRole` becomes an open vocabulary ✅
Synthesis of a discussion (ChatGPT's opinion, shared by Federico): forge
doesn't define the world, it provides a geometric language + known roles that
others build on. A closed `ContourRole` that rejects the unknown works against
the "neutral substrate" direction.

Rule:
- **A — the enum is not authoritative, never a reverse-lookup from external
  input.** `ContourRole` stays a collection of known-role constants. forge
  only does membership tests. `ContourRole[x]`/`getattr`/`ContourRole(x)` on
  caller data are forbidden — they raise or reach class attributes. A
  string→role map always goes through `dict.get`.
- **B — a single normalization point, at load.** `model/role.normalize_role`:
  lowercase, `[a-z0-9_-]` charset (rest collapsed to `_`, neutralizing
  injection payloads), ≤ 64 chars; known → constant, unknown-but-valid → kept
  as a slug.
- **C — defense at the sinks too.** Unknown role → `TRASH_LAYER`/
  `COLOR_TRASH`; SVG escapes any role in an attribute. Redundant with B,
  intentionally.
- **D — `role_str(role)`** replaces `.role.value`, which crashes on a plain
  `str`.

Type hint `role: ContourRole` → `role: str` throughout. A custom role
(`title_block`) survives `load → heal` intact, no warning. Suite: 619 passed.
Branch `refactor/open-roles`, `main` → 0.6.7.

### D28 — `BendingDetector` → `NonContourEdgeDetector` (neutral name) ✅
Flagged by Federico: `HealStep` had a `_find_bending_candidates()`/
`BendingDetector` that looked like `detect`'s logic leaking into `heal`.
Verified: the module classifies nothing as a bend — topologically it finds
edges with both endpoints on branching nodes and a centroid inside the convex
hull, and excludes them from the graph before loop search (otherwise a line
crossing the whole part breaks contour closure). This is legitimately `heal`'s
job; only the name borrowed `detect`'s vocabulary. Renamed, not moved. No
behavior change. `main` → 0.6.8.

### D29 — Frame/title-block detection: a `Framer` module, outside forge → `FRAMER.md`
Frame and title-block recognition becomes its own module, `Framer`, a forge
consumer and part of the future interpreter (sibling of the unfolder). Doesn't
enter forge — it runs *before* `heal` on raw geometry, tags edges with
`role="frame"`/`role="title_block"` and hands them back to forge, consistent
with the neutral-substrate principle and D24's removal of the frame detector.
Also the first real test bed for the forge↔consumer interface. Full design,
algorithm, and the three heal-hookup options in `FRAMER.md`.

### D30 — Single structural predicate + `detect()` leaves unknown roles alone ✅
Preparation for Framer's hookup (D29): chose **option B** (see `FRAMER.md`) —
no new forge API, just consolidation so that "a consumer marks `edge.role` on
`doc.edges` before `heal`" is a contract, not a coincidence.

The concept "this role is part-contour topology" had been redefined by hand in
four places that **disagreed** with each other. A custom role had only
survived because all four, for different reasons, happened to exclude it.

- **`model/role.STRUCTURAL_ROLES` + `is_structural_role(role)`** — the single
  source of truth (`{OUTER, INNER, HOLE, COUNTERSINK, THREADED_HOLE}`), moved
  from `rules/thresholds.py`. The four call sites now use it.
- **`heal._split_labeled` generalized**: pulls out of the topology **every**
  edge with a decided, non-structural role (before: only `ENGRAVE`/
  `MARKING`; now also `frame`, label-mapped `bending`, any consumer slug).
  Those edges skip gap solving, corner repair and non-contour detection —
  they land in `trash_entities` with their role intact.
- **`detect()` no longer invents features from a role it doesn't know** (bug:
  D27 had only been applied to `heal`). Fixed a real data-loss bug found on a
  real file: `detect()` was turning any non-UNKNOWN-role trash proxy into a
  disconnected `ClassifiedEntity` that `to_dxf` doesn't rewrite → lost
  geometry. Now `detect()` only touches its known roles; everything else
  stays in trash.
- `forge.normalize_role`/`forge.is_structural_role` promoted to `__all__`.

Suite: 625 passed. Branch `refactor/consolidate-structural-role`, `main` →
0.6.9.

### D31 — `frame` stays out of forge; consumer roles get their own layer ✅
Verified on a real drawing with a frame (tagged by `framer`): frame geometry
came out entirely on the `Trash` layer, mixed with real garbage — D30 kept the
role alive down to `trash_entities`, but the writer discarded it. Federico:
*everything framer-specific — including the role, including in the adapter —
must live outside forge.*

- `ContourRole.FRAME` removed. `frame` is just a consumer slug now, like
  `title_block`/`section`.
- `ROLE_TO_LAYER[FRAME]`/`ROLE_TO_COLOR[FRAME]` removed (they were wrong
  placeholders — a frame isn't a cut contour).
- `_write_trash` now routes by role: known role → its layer; sanitized
  consumer slug → a layer named after the slug (created on the fly, dark
  gray); unknown → `Trash`. Same logic for SVG.

Verified on the real drawing: `frame` lands on an 11-entity `frame` layer,
real trash stays on `Trash` (388 entities). Suite: 626 passed. `main` →
0.6.10.

### D32 — `load_geometry` made public ✅
Was experimental pending a real use case. Verified: `bendly` already uses it
in production to bring generated sheet-metal developments into a
`ForgeDocument` without a file — the real case existed, the note was just
stale. Looking ahead to Smoother (image-reconstructed contours), Federico:
"publish it, someone will definitely use it." No behavior change beyond
entering `forge.__all__`.

### D33 — `simplify_points`: point→primitive reconstruction moved into forge ✅
Analysis of a prior session's `smoother_5.py` script found nothing
image-specific in its corner-detection/refit logic — it takes an ordered,
closed point sequence, detects corners by angle, and refits each stretch as a
line or spline. Federico confirmed and set one condition: the two thresholds
(corner angle, minimum point count for a spline) must be caller-controlled
parameters, not hardcoded constants.

`forge/tools/simplify_points.py`: `detect_corners()` + `fit_primitives()`
(splits on corners, refits each stretch as `LineSeg` or `SplineSeg` via
`ezdxf.math.BSpline.from_fit_points`) + `simplify_points()` chaining them.
Same experimental treatment as `load_geometry`/`load_pdf` before D32:
importable, out of `__all__`, undocumented until proven by a real case
(Smoother).

### D34 — `ForgeContour.depth`/`.parent`: the containment tree is no longer flattened ✅
For placing tabs on deeply nested contours, a downstream tool (Smoother) needs
to know not just "you're nested" but "inside exactly which contour" — depth
alone can't tell apart two sibling holes each with one island of their own.
`hierarchy.py` already built the real tree but deliberately flattened it in
`_collect_inners()`, losing who-contains-whom. Now every `ForgeContour`
carries `depth: int` (0 = outer, 1 = child, 2 = grandchild, ...) and `parent:
Optional[ForgeContour]`, passed down during the same recursion — no recompute.
Federico also reasoned through the "add an outer container later" case: no
reparenting needed, since `_build_tree` recomputes containment from scratch on
every `heal()` call over a fresh geometry batch — the caller's discipline
(don't tag `role="outer"` until you know it'll stay the root) is what matters,
not forge's.

### D35 — `load_geometry` accepts `"spline"` too ✅
Migrating `smoother_5.py` into its own repo exposed the gap immediately:
`forge.simplify_points()` produces `SplineSeg`, but `GeometryAdapter` only
translated `line`/`arc`/`circle`/`polyline`. Federico stated the general
principle: **"all loaders must end up looking alike in their entities — even a
future `load_pdf`/`load_step` must expose the entity vocabulary needed to get
output in the required formats."** Every loader/adapter must cover the full
segment vocabulary `Edge` already supports, not just the subset convenient for
its immediate use case. `GeometryAdapter._spline_edge` added: a `"spline"`
type mirroring `SplineSeg`'s fields 1:1.

### D36 — `fit_primitives` accepts arc/circle fitting too (`arc_fit_tolerance`) ✅
Completes the third case (line/**arc**/spline) planned since D33 but never
implemented. From `smoother` work: a constant-radius curved stretch (a fillet,
a hand-traced hole) always became a `SplineSeg`, even when an `ArcSeg` would
cut better on the laser and is trivial to split for a tab. Confirmed this is
forge's job, not smoother's — the same generic geometric reconstruction as
`simplify_points`. New optional `arc_fit_tolerance: Optional[float] = None`
(default off, zero behavior change for existing callers). When set, each
spline-candidate stretch first tries a least-squares circle fit (Kasa's
algebraic method via `numpy.linalg.lstsq`): within tolerance → `CircleSeg` (if
it closes on itself) or `ArcSeg` (open stretch, angles computed by unwrapping
the real point sequence around the center — not just first/last point, to
avoid confusing an arc over 180° with a shorter one the wrong way). Otherwise
falls back to spline as before.

### D37 — `RoleStyle`: explicit color/linetype/lineweight override per role ✅
Born from a real `framer` case: the frame (consumer role `frame`, D31) always
came out gray (hardcoded `COLOR_CONSUMER`), and the only way to make it black
was to hack the DXF entity after `to_dxf()` — exactly the kind of hack forge
exists to avoid. The role was already consumer-extensible (`normalize_role`);
the palette wasn't — `role_to_color()` has one fixed fallback for any unknown
slug. Discussed with Federico: extensibility should apply the same way to
every style axis (color, linetype, weight), not just color, even though today
only the DXF adapter applies them.

`RoleStyle` (frozen dataclass, exported): `color`/`linetype`/`lineweight`, all
optional. The caller assembles a `Dict[str, RoleStyle]` once and passes it to
`to_dxf`/`split` via `role_styles=` — same idiom as `label_map`/
`linetype_map`, no stateful global. Deliberately not a stateful "builder"
object — forge's API has no builder/registry anywhere, no reason to start
here.

DXF side: the override lands on the **layer**, not the entity (everything
forge writes is BYLAYER, so it propagates automatically). `color`→
`layer.rgb` (true color, since ACI 256-color has no pure black);
`linetype`→registered on the fly if standard, then assigned;
`lineweight`→`layer.dxf.lineweight` in hundredths of mm. Deliberately out of
scope: `to_svg`/a future `to_pdf` (only `to_dxf`/`split` consume it today).

**Open question, raised alongside D37, not yet decided** — where should the
hole/countersink/threaded/engrave/marking role taxonomy live? `ContourRole.
HOLE`/`COUNTERSINK`/`THREADED_HOLE`/`ENGRAVE`/`MARKING` live in `model/role.py`
but are conceptually `detect`'s vocabulary (a tool), not neutral geometry. Not
a mechanical move: `core/heal.py`/`hierarchy.py` read `STRUCTURAL_ROLES`
(which includes exactly those roles) to decide topology, and `core` can't
depend on `tools/`. Probably needs an indirection (e.g. a `structural: bool`
flag on the role itself, not a fixed imported list) before those members can
move — a real redesign, not to be done in passing. Federico expects it'll be
needed eventually, not a priority now.

### D38 — Point-sequence math moved into `core/geometry.py`
`interior_angle_deg`, `detect_corners`, `drop_duplicate_points`,
`fit_circle_kasa`, `arc_angles` were inside `tools/simplify_points.py` (D33,
D36) — pure point-sequence math with zero dependency on forge primitives.
Moved next to the segment/track equivalents already there (`track_points`,
`circular_geometry`, `are_collinear`). `simplify_points.py` stays the
orchestrator, importing them back. `detect_corners` stays re-exported for
existing callers. No behavior change.

*Correction*: the original rationale here claimed a second consumer
(`tools/tabs.py`, D39) justified the move — verified false after the fact
(Federico asked for confirmation): `cut_tabs()` only uses `_distance`, which
was already in `core/geometry.py` beforehand and isn't among the functions
moved here. The move is still justified on its own merits (same family as
`track_points`/`circular_geometry`), just not "proven" by a second real
consumer as originally written.

### D39 — `forge.tools.tabs.cut_tabs`: cutting tabs as a forge tool (draft)
Born from a real need: a smoother-successor must cut tabs on a contour before
fitting it, so a concentric ring stays attached to the rest of the sheet.
Discussed at length whether this belongs in a consumer (smoother) or in
forge:
- Not deterministic in the "reconstruct what's in the drawing" sense — unlike
  `heal`/`detect`, it creates a gap the source drawing didn't have. But `heal`
  already modifies geometry (closes micro-gaps), and `tools/` exists
  precisely for optional, parameter-deterministic operations the caller
  composes — the mechanics (cut a gap of known width at a known position) are
  deterministic given parameters, same as `detect()`'s thresholds; *where/how
  many* stays a process decision of the caller's, never forge's.
- Decisive packaging argument: smoother depends on opencv (a `raster` extra,
  not core forge). Someone who only wants tabs on an already-clean DXF
  shouldn't need an image-processing library.
- Not in the flat public `forge.*` contract, for the same reason
  `detect_corners`/`fit_primitives` weren't before `simplify_points` —
  reachable only as `forge.tools.tabs.cut_tabs` until proven by a real case.

`cut_tabs(points, closed, tab_positions, tab_width)` — `tab_positions` are
point indices (a first-draft choice, not final; nobody uses this in
production yet); `tab_width` is a real cumulative-perimeter distance. Verified
with a synthetic script: a 200-point ring, 4×2mm tabs → 4 open stretches, each
refit to a clean `ArcSeg`.

### D40 — `cut_tabs` deleted, replaced by `bridge_tabs` ✅
`cut_tabs` (D39) only cut a gap within ONE contour — but the real need on the
actual fixture was keeping a grandchild island attached to its direct parent
(a bridge across TWO distinct contours), which `cut_tabs` can't do. `cut_tabs`,
its test, and its scripts were deleted outright — no compat shim, no
independent second use.

`bridge_tabs` design: generalizes to arbitrary depth, in pairs — every island
(even depth ≥ 2) bridges to the void immediately above it in the hierarchy
(its direct parent), never a skipped level (needs `ForgeContour.depth`/
`.parent`, D34). Geometric construction: an ideal line between a point on the
child and the corresponding point on the parent → perpendicular offset by
`±tab_width/2` → two real lines (the tab's flanks) → intersect each with both
contours → new `LineSeg`s + remove the in-between stretch on both contours.
`tab_width` is a real perpendicular-offset distance, not an arc length
(parent and child have different radii). Reuses `core/geometry.py`'s existing
line-circle intersection, no new math for the circle-circle case. Scope:
line/arc/polyline/circle parent-or-child, not spline yet (no line-spline
intersection in core).

Implemented: `bridge_tabs(...)` (one pair, one position, returns the 2 flank
segments + 4 cut points) and `bridge_nested_tabs(cluster, tab_width,
tab_count, ...)` (walks `cluster.inners`, finds every even depth ≥ 2, places
`tab_count` equally-spaced tabs per island, using a new
`core.geometry.polyline_line_intersections` that generalizes the circle-line
intersection to any already-discretized contour). Multi-tab cuts on the same
contour are resolved in one pass (compute all cuts against the intact contour
first, then keep only the arcs between different tabs) to avoid re-cutting an
already-open stretch.

Known unresolved limit: two sibling islands sharing the same direct parent
would be cut independently against the same parent contour, unaware of each
other — not today's fixture's case, to be solved when it comes up. Suite: 668
passed.

### D41 — `_fit_spline`: never `fit_points`, `closed=True` only for a whole-loop stretch ✅
Found by Smoother: a SPLINE written by `to_dxf()` for a closed, corner-free
contour wasn't read by some downstream CAM software (SigmaNest — not an
isolated case, it had happened before on another project). Comparing two
DXFs, the difference wasn't the geometry but two SPLINE group fields: `flags`
always `0` (open) even for fully-closed loops in the broken file, `1` in the
working one; and `fit_points` always present in the broken file, absent in
the working one. Both traced to `_fit_spline()`: it never passed `closed=` and
always wrote `fit_points` alongside control points + knots — per DXF spec the
two curve definitions are alternatives, not cumulative, and some readers
evidently mishandle having both.

**Fix**: `_fit_spline()` no longer writes `fit_points` (control points +
knots fully define the curve; the only loss is an optional "handle" metadata
for an editor). Gains a `closed` parameter, `True` only when the whole closed
contour became a single stretch. Verified end-to-end against the exact broken
pattern, then against the real pipeline (a ~140-contour image) producing the
correct pattern on every spline automatically. Suite: 668 passed, no
regressions.

### D42 — `SplineSeg.discretize()` was evaluating the control polygon, not the curve ✅
Found by Smoother: SVG previews (and the polyline export, sharing
`.discretize()`) of a spline with few control points over a long stretch
looked visibly faceted even though the DXF spline itself was smooth and
correct. Cause: `discretize()` was an explicitly unfinished placeholder —
linear interpolation between control points as a stand-in for real curve
evaluation.

**Fix**: `discretize()` now evaluates the real curve via de Boor's algorithm
(rational if weights are set) and adaptively subdivides each parameter
interval until the midpoint stays within `tolerance` of the chord, capped to
avoid exploding on a non-converging stretch. Pure math only (`math` module —
`core/` must work without `ezdxf` installed; an early attempt reusing
`ezdxf.math.BSpline` was discarded for that reason, not a technical one).
Verified numerically: an 8-control-point spline over a radius-10 semicircle
deviated up to 0.79 units under the old logic, 0.011 with the new one at
`tolerance=0.05`. Suite: 668 passed, no regressions.

### D43 — `interpret_annotations` → `anchor_annotations` ✅
Renamed (`forge/tools/interpret.py`→`forge/tools/anchor.py`). Grew out of a
design discussion with Federico (external LLM opinions gathered for
perspective) about determinism and forge's boundaries: the word "interpret"
was already doing triple duty — this function (pure geometry: `cluster_ref` by
containment), the future interpreter project (`INTERPRETER.md`), and the
generic interpretation concept discussed around D39-D42 — a real source of
confusion, not just an aesthetic complaint.

Stays in forge: this is a naming problem, not a "where does it live" problem.
The function is pure geometric reconstruction (point-in-polygon, optional
snap) — zero judgment about what an annotation means, so none of the work
migrating toward `framer` (frame/title-block/views/callouts) applies to it.
The new name reuses wording the docs already used to describe it ("typed,
**anchored** annotations") instead of introducing a third term. No compat
shim — renamed everywhere.

### D44 — `detect()` as a consumer: `ForgeCluster.detected` becomes an open-by-name overlay ✅
Long design session (2026-09-18, branch `refactor/detect-overlay`), starting
from the tension already flagged in `forge-clusters-not-parts`: `ForgeCluster`
(the neutral product of `heal`) still had `holes`/`bending_lines`/
`engrave_lines`/`custom` wired in as fixed fields, always present as empty
lists the moment `heal()` finished — `detect()` filled them by mutating
directly in about a dozen places. Concrete problem: an empty list couldn't
distinguish "`detect()` never ran" from "it ran and found nothing."

Decisions, in order of discovery:
1. `holes`/`bending_lines`/`engrave_lines` move out of `ForgeCluster`, into an
   `Optional[DetectedFeatures] = None` — `None` until something writes to it.
   `custom` stays a direct cluster field (it's `inject()`'s free-form dict, a
   different kind of thing, no ambiguity to resolve there).
2. No convenience property (e.g. `cluster.holes` returning `[]` when
   `detected` is `None`) — that would reintroduce the exact ambiguity being
   removed. A consumer goes through `cluster.detected.holes` (raises if
   `None`) or the safe accessor `cluster.features(name)` (always `[]`, never
   raises — convenient for a renderer/exporter that just needs to iterate).
3. `DetectedFeatures` is an **open-by-name vocabulary**, not a fixed schema —
   the same move already made for `role` in D27. `detect()` writes
   `cluster.detected.attach("holes", [...])`; an external tool writes
   `attach("flange_view_hint", [...])` with the same method — neither is
   privileged. Motivated by Federico's example: the same geometry `detect()`
   reads as a "bending line" another tool might read as "the rising edge of a
   flange," reconstructing a view across multiple clusters — two equally
   valid readings, not a primary one and a discard.
4. `DetectedFeature` is a `typing.Protocol`, not an ABC — consistent with D5
   ("a convention, not a hierarchy"): the contract is just `source: str` +
   `confidence: float`. Existing types satisfy it with zero changes; a custom
   type doesn't need to inherit anything from forge to "count".
5. `Hole`/`BendingLine`/`Engraving`/`ClassifiedEntity` move to
   `forge/tools/model/`: they're `detect()`'s output, not `heal()`'s geometry.
   First attempt referenced them under `TYPE_CHECKING` only (zero runtime
   import) — **corrected by Federico**: even that is too much — if
   `model/cluster.py`'s first line names `tools`, the "why does model know
   tools exists?" question stands regardless of whether the import is inert.
   `detect()` is just the first of possibly several consumers; it lives
   inside forge because it was developed together with it, not because
   `model` needs to know it exists. Typed `Optional[Any]` instead — zero
   textual mention of `tools/` anywhere in `model/`.
6. `rules/thresholds.py` → `tools/thresholds.py` (both its consumers were
   already in `tools/`). `rules/palette.py` stays put — it maps color for the
   whole role vocabulary, not just detect's.
7. `cluster.summary` becomes generic and stays on the model: `{name}_count:
   len(items)` per collection in `detected`, `{}` if `detected is None` —
   works identically with just `heal()` and for any custom name, without
   forge knowing what it is. The **rich** per-type breakdown that `summary`
   used to give (D8) moved to `tools.detect.describe_features(cluster)`,
   since it needs constants `model/` can't import from `tools/`. The two
   levels coexist.
8. `io/exporter.py::build_metadata()` merges three levels: the generic
   `summary`, forge's `describe_features()`, and a new `extra`/
   `extra_metadata` parameter — an explicit dict or `cluster -> dict`
   callback, same idiom as `data_injector`/`label_map`/`RoleStyle`. Motivated
   by Federico's example: neither the generic summary (just a count) nor
   `describe_features()` (only forge's known types) can ever answer "how many
   upward-facing flanges does this cluster have" — only whoever wrote that
   custom type knows. `metadata_schema.py` itself doesn't change shape — it
   stays a curated allow-list for the external, non-Python boundary
   (CAM/ERP/XDATA).
9. No new overarching API for extensibility: `role_to_color`,
   `DetectedFeatures`, `summary`/`describe_features()`, and
   `build_metadata()`'s `extra` stay small, independent instances of the same
   pattern (known name → rich logic, unknown name → generic fallback), not a
   shared framework — premature from this sample size.
10. `describe_features` promoted to `forge.describe_features` (top-level, in
    `__all__`) — corrected by Federico: `forge.X` flat is the sanctioned
    public front; leaving it the one unpromoted sibling among `detect`/
    `inject`/`anchor_annotations` would have been an exception without a
    reason. `bridge_tabs`/`bridge_nested_tabs` stay unpromoted — unfinished
    work there, not a different principle.

Bug found doing the work: `hierarchy.py::_build_parts` was passing a now-dead
`holes=[]` kwarg to the constructor — caught by the suite (410 tests broke at
once), not by the initial text audit, a reminder that a text audit alone
doesn't substitute for running the suite on a refactor this wide. Suite: 671
passed, 62 subtests, verified end-to-end (not just by counting).

### D45 — `EllipseSeg`: forge's fifth primitive, DXF ELLIPSE support ✅

Gap found while discussing a future point-sequence "rotator" tool: forge had
no `EllipseSeg` at all — `ELLIPSE` was in `loader.py`'s "known roundtrip
types" set (no warning on load) but `DxfEntityDispatcher.parse()` had no case
for it, so any real ELLIPSE entity silently produced no geometry, with no
warning that anything was lost.

Checked before writing any code, not assumed: an ellipse is a native conic
curve type in every real CAD kernel (ACIS/Parasolid/OpenCascade, STEP) and in
SVG (`<ellipse>` and the elliptical-arc `path` command) — not a DXF quirk to
normalize away into a spline. Converting it to a spline would also repeat a
mistake already paid for once: D41's SigmaNest failure came from writing
geometry through a representation richer than what the shape actually was.
Per `loaders-converge-on-same-entity-vocabulary` (D35), it gets its own
primitive, same tier as `LineSeg`/`ArcSeg`/`CircleSeg`/`SplineSeg`.

`EllipseSeg(center, major_axis, ratio, start_param, end_param, ccw=True)` —
`major_axis` is the **vector** from the center (not a point), same
parametrization as the DXF ELLIPSE group (verified against `ezdxf`'s own
`ellipse.py`/`math/ellipse.py` source, not assumed from memory). One class
covers both a full ellipse and an elliptical arc — like `ArcSeg`, unlike
`CircleSeg` (DXF's CIRCLE is always closed, ELLIPSE isn't). `ccw` exists for
the same reason as `ArcSeg.ccw`: a real DXF ELLIPSE is always written
CCW from `start_param` to `end_param`; `ccw=False` is forge-internal state
for walking a segment backwards when a loop gets oriented.

`discretize()` needed adaptive sampling, not `ArcSeg`'s fixed
sagitta-per-angle formula: an ellipse's curvature isn't constant (tightest at
the ends of the major axis, radius `b²/a`). Extracted the adaptive
chord-tolerance subdivision already built for `SplineSeg` (D42) into two
shared functions (`_adaptive_polyline`/`_refine_segment`, parametrized over an
`evaluate(t)` callable) instead of duplicating that recursive logic — `SplineSeg.discretize`
now calls the same shared helper. Also extracted `_angular_sweep` (was
`ArcSeg._sweep`'s body) since `EllipseSeg._sweep` needs the identical
"sweep from start to end in a direction" computation on `start_param`/
`end_param` instead of `start_angle`/`end_angle`.

Touched every place `CircleSeg`/`SplineSeg` already had a case, mirroring the
existing pattern instead of inventing a new one: the DXF parser/dispatcher,
`segment_endpoints`, `to_edges()`'s closed-vs-open branch (generalized the
existing SPLINE-only "parse once, check `segment_is_closed`" branch to also
cover ELLIPSE — same ambiguity, same fix), the DXF exporter (`_add_ellipse`,
mirroring `_add_spline`; wired into `write_segments`/`write_engrave_segments`/
`write_open_segments` — **never** as a discretized fallback), `_segment_key`
dedup, the validator's zero-length exemption, `inspect.py`, and
`GeometryAdapter`/`load_geometry` (`"ellipse"` entity type, same treatment as
`"spline"` in D35 — no real external consumer yet, added anyway because it's
a primitive forge now has, not a speculative feature).

**Regression found and fixed, not introduced**: the `Polylines.dxf` golden
fixture (`tests/examples/golden{,_multipli}/`) contains a real ELLIPSE used
as an inner cutout in one part. Before this decision it was silently dropped
— the golden's expected area for that part was generated under that bug (no
inner subtracted). Verified independently (computed the ellipse's true area
from its own parameters, `π·a·b ≈ 1054.80`, against the old-vs-new area diff,
`1054.25`) before regenerating — not regenerated on faith. Golden
regenerated for that fixture only (`generate_golden.py --only Polylines`,
`generate_golden_split.py --only Polylines`); the sibling parts of the same
split fixture picked up an unrelated, pre-existing staleness for free (a
`"custom"`→`"summary"` key never applied to those specific files since D8,
and a cosmetic WKT ring-rotation from an unrelated shapely/GEOS version
drift) — checked both, neither is a real geometry change.

Suite: 693 passed (was 691 + the new ellipse tests), no other golden touched.
Branch `refactor/ellipse-primitive`.

---

### D46 — `.rotated()` on every primitive, `forge/tools/rotate.py` ✅

First piece of "funzioni geometriche" (TODO.md) actually built, triggered by
a concrete ask: a script that rotates a whole file so its longest OUTER side
becomes horizontal — filtered to `role="outer"`, not just any geometry (a
diagonal internal line, even a long one, must not count).

`.rotated(angle_rad, origin=(0,0))` added to `LineSeg`/`ArcSeg`/`SplineSeg`/
`CircleSeg`/`EllipseSeg` — same tier and pattern as `.reversed()`, pure
math, no format dependency. `ArcSeg`/`EllipseSeg` just shift their angular
fields by `angle`, no re-derivation needed; `SplineSeg` rotates control/
approx/fit points and the tangent *vectors* (rotated around `(0,0)`, never
translated by `origin` — a direction, not a point).

`core/geometry.py` gained `segment_length(segment)` (closed form for
`LineSeg`/`ArcSeg`/`CircleSeg`; `track_length(segment.discretize())` for
`SplineSeg`/`EllipseSeg`, no constant curvature), `longest_segment(segments)`,
and `chord_angle_deg(a, b)` — the exact `atan2(...) % 180` formula
`detect._detect_bending` and `_bending_line_from_data` already had inline
twice, now shared instead of duplicated a third time.

`forge/tools/rotate.py` (new, experimental — importable as
`forge.tools.rotate`, not yet in `forge.__init__`'s top-level surface, same
precautionary stance as `simplify_points` pre-proof, D33):

- `longest_outer_segment(result)` — `(segment, length, angle_deg)` of the
  longest segment across every `cluster.outer.segments` in a `ForgeResult`.
  `None` if there is no outer.
- `rotate_document(doc, angle_rad, origin, tolerance)` — new `ForgeDocument`
  with every `edge.segment.rotated(...)`, endpoints re-rounded exactly like
  the adapter does at load time (`round_point`/`node_decimals_for`) so a
  later `heal()` sees the same coincident nodes. Annotations are **not**
  rotated yet (no real case has needed it) — `doc.annotations` non-empty
  adds a warning instead of silently leaving them in the wrong place.
- `rotate_to_longest_outer(doc, origin=None, target_angle_deg=0.0,
  tolerance=None)` — the orchestrator. Two passes, not one: "outer" only
  exists after topology, so pass 1 is `heal(doc)` purely to measure the
  angle; the actual rotation is applied to the *raw* pre-heal
  `doc.edges` (via `rotate_document`), and the caller re-heals the rotated
  document to get a fresh, valid `ForgeResult` — rotating polygons/
  hierarchy/features of an already-healed `ForgeResult` in place would mean
  touching every derived structure by hand for the same end result.
  `origin` defaults to the bbox center of the document's own edges
  (approximate on arcs — fine for a pivot, the shape doesn't change with
  `origin`, only where it lands).

New fixture `tests/examples/try_for_rotation.dxf` (generator:
`tests/generate_rotation_fixture.py`) — 100x400 rectangle (outer verticale,
lato più lungo = 400) with an internal line diagonal across it, like a
bending line but not parallel to any side, to prove the outer-only filter.
Demo script `scripts/17_rotate_to_longest_outer.py`.

Suite: 716 passed (was 693 + rotation tests), no golden touched.

---

## Closed questions (history)

- **Q1 — hole classification: topology or detection?** → resolved by D15
  (detection, `detect()` parametric). Keeping it in `heal`/`hierarchy` was
  rejected: it would have made `heal` non-skippable on hole/inner semantics,
  against `laser-cutting-default-cam-enrichment-optional`.
- **Q2 — value of `HOLE_DIAMETER_THRESHOLD`** → resolved by D15. `32.1` mm is
  now the *default* of `detect(max_drill_diameter=...)`, not a domain
  constant. Federico keeps it at 32.1 for now ("thinking about toleranced
  holes that might need re-passing"). The constant stays in
  `rules/thresholds.py` as the default's source, overridable per
  machine/tool.

---

## Federico's notes (open questions, kept until they become decisions)

- `inspect_file`/`inspect_dxf` (level 1) are hardcoded to DXF. Fine for now —
  it's already the only real format adapter forge has. `inspect_document`
  (level 2) already works on any `ForgeDocument`, including geometry from
  `load_geometry()` (the path `bendly` uses, zero DXF). Only level 1 and the
  orchestrator need generalizing, and only once a second real format adapter
  exists.
- `inspect_dxf` needs an entity-type filter (only SPLINE, only LWPOLYLINE,
  ...) instead of today's all-or-nothing `entities=` switch. Small, clean
  addition (a `types: Optional[set[str]] = None` parameter), not done yet —
  queued.
- Does layer tagging (`label_map` etc.) matter if `detect(features="all")` is
  never called? **Yes — verified in code, not an impression.**
  `label_map`/`linetype_map`/`color_map` set `edge.role` at load time, before
  `heal()` is even called. `heal()` itself (not `detect()`) already uses
  those roles in `_split_labeled()` to keep non-structural edges
  (tabs/engraving/frame) out of the topology graph — this is how they don't
  break outer/inner detection. `detect()` only adds a second, geometric-
  inference lane on top of what `label_map` hasn't already decided.
