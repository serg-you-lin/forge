Piano completo — refactoring dxf-forge
Contratto finale dell'API pubblica
python
doc = forge.load_dxf("file.dxf")      # unico punto che tocca ezdxf
result = forge.heal(doc)               # core puro — zero DXF
result = forge.detect(result)          # classificazione — zero DXF
doc_out = forge.write(result)          # documento nuovo — zero source_ref
doc_out.saveas("output.dxf")

# split è write per ogni part
paths = forge.split(result, output_folder)

# futuro
doc = forge.load_svg("file.svg")       # stesso contratto, adapter diverso
Cosa è doc — il ForgeDocument

load_dxf() non restituisce un msp ezdxf. Restituisce un oggetto dominio:

python
@dataclass
class ForgeDocument:
    edges:       List[Edge]        # geometria parsata — input per heal()
    annotations: List[Annotation]  # testi, quote, leader — input per write()
    source_meta: dict              # $INSUNITS, $MEASUREMENT, ecc.
    source_path: str

edges e annotations sono dati puri — zero ezdxf dentro. L'adapter li produce e poi il riferimento al msp originale sparisce.

I passi in ordine

Passo 1 — ForgeDocument

Crea model/document.py con il dataclass sopra. Annotation è un dataclass semplice:

python
@dataclass
class Annotation:
    kind:     str                    # "TEXT" | "MTEXT" | "DIMENSION" | ...
    position: Tuple[float, float]    # punto rappresentativo
    data:     dict                   # tutto il necessario per riscriverla

Niente source_ref — data contiene il testo, la posizione, tutto quello che serve per ricreare l'entità nel documento di output.

Passo 2 — forge.load_dxf()

python
def load_dxf(path: str) -> ForgeDocument:
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    edges       = DxfAdapter(msp).to_edges()
    annotations = DxfAnnotationExtractor(msp).extract()
    meta = {
        "$INSUNITS":   doc.header.get("$INSUNITS", 4),
        "$MEASUREMENT": doc.header.get("$MEASUREMENT", 1),
    }
    return ForgeDocument(edges=edges, annotations=annotations,
                         source_meta=meta, source_path=path)

Dopo questa funzione, ezdxf non viene mai più toccato fino a write().

Passo 3 — forge.heal() riceve ForgeDocument

python
def heal(doc: ForgeDocument) -> ForgeResult:
    # lavora su doc.edges — zero DXF
    ...

ForgeResult non cambia struttura — ma non porta più source_ref né _entities_in_loops_ids.

Passo 4 — elimina source_ref dal modello

Ora che heal() non vede più ezdxf, source_ref non ha motivo di esistere. Si elimina da:

Edge
ClosedShape, OpenShape
Feature e tutta la gerarchia
Hole, BendingLine, ForgeContour
ClassifiedEntity

Passo 5 — forge.write() riceve ForgeResult

python
def write(result: ForgeResult, source_doc: ForgeDocument = None) -> ezdxf.document:
    doc_out = ezdxf.new(dxfversion="R2010")
    if source_doc:
        doc_out.header["$INSUNITS"]    = source_doc.source_meta["$INSUNITS"]
        doc_out.header["$MEASUREMENT"] = source_doc.source_meta["$MEASUREMENT"]
    msp_out = doc_out.modelspace()
    _setup_layers(doc_out)

    for part in result.parts:
        write_segments(part.outer.segments, msp_out, LAYER_OUTER)
        for inner in part.inners:
            write_segments(inner.segments, msp_out, LAYER_INNER)
        for hole in part.holes:
            layer = _work_layer_for_hole(hole) or LAYER_HOLE
            write_segments(hole.segments, msp_out, layer)
        _write_bending_lines(msp_out, part)
        for eng in part.engrave_lines:
            write_segments(eng.segments, msp_out, LAYER_ENGRAVE)

    if source_doc and source_doc.annotations:
        _write_annotations(msp_out, result, source_doc.annotations)

    return doc_out

Passo 6 — forge.split() diventa banale

python
def split(result: ForgeResult, source_doc: ForgeDocument,
          output_folder: str, ...) -> list:
    for i, part in enumerate(result.parts):
        result_part = ForgeResult(parts=[part], ...)
        doc_out = write(result_part, source_doc)
        doc_out.saveas(path)

Passo 7 — aggiorna i test

I test di write smettono di controllare il msp originale — controllano il doc_out restituito. Questo è il passo che blocca tutto se non viene fatto prima di scrivere il codice.

Ordine di esecuzione
1. ForgeDocument          — model/document.py
2. DxfAnnotationExtractor — adapters/dxf/annotation_extractor.py
3. forge.load_dxf()       — forge/__init__.py o pipeline/load.py
4. forge.heal() aggiornato — pipeline/heal.py
5. elimina source_ref     — modello e bridge
6. forge.write() riscritto — pipeline/write.py
7. forge.split() riscritto — pipeline/write.py
7bis. write→to_dxf, split ritorna list[Drawing], I/O solo in split_to_files
8. aggiorna i test        — tutti i test di write/to_dxf e split
Cosa NON cambia
DxfAdapter.to_edges() — già produce Edge puri
hierarchy.py — già lavoro su ClosedShape puri
detect() — non tocca DXF
exporter.py — già lavora su segmenti puri
Il modello domain interno — fino al passo 5
Il futuro load_svg
python
def load_svg(path: str) -> ForgeDocument:
    edges       = SvgAdapter(path).to_edges()
    annotations = []   # SVG non ha annotazioni DXF
    meta        = {}
    return ForgeDocument(edges=edges, annotations=annotations,
                         source_meta=meta, source_path=path)

Stesso contratto — heal(), detect(), write() non cambiano una riga.

---

# STATO DEL REFACTOR — aggiornato 2026-08-27

Branch: `refactor/structure`. Modifiche **non committate** (i commit li fa Federico).

**Tutti i passi (1–8) completati** + fix regressione engrave `to_dxf()`.
Suite: **441 passed / 0 failed** (2 xfail preesistenti).

## Fatto e verificato

- **Passo 1** — `forge/model/document.py`: `ForgeDocument` (edges, annotations, source_meta, source_path) + `Annotation` (kind, position, data). Esportati da `forge/model/__init__.py` e `forge/__init__.py`.
- **Passo 2** — `forge/adapters/dxf/annotation_extractor.py`: `DxfAnnotationExtractor(msp).extract() -> List[Annotation]`.
- **Passo 3** — `forge/adapters/dxf/loader.py`: `load_dxf(...) -> ForgeDocument` (non più `(doc, msp)`). Aggiunto `document_from_msp(msp, ...)` per test / geometria generata a mano.
- **Passo 4** — `forge/pipeline/heal.py`: `HealStep(doc: ForgeDocument, ...)`, lavora su `doc.edges`, zero ezdxf. `forge.heal(doc)` valida il tipo e prende `tolerance` da `doc.source_meta`.
- **Passo 6** — `forge/pipeline/write.py`: `write(result, source_doc=None) -> doc_out` (documento ezdxf nuovo, mai il msp sorgente). `$INSUNITS`/`$MEASUREMENT` da `source_meta`. `_write_annotations()` filtra per part scritte.
- **Passo 7** — `write.py`: `split(result, source_doc=None, output_folder=..., ...)` — un `write()` per part. `forge/pipeline/__init__.py`: `heal()`, `split_to_files()` sul nuovo contratto.
- **Gap healing puro** — `forge/core/healing/gap_solver.py`: `free_endpoints_from_edges(edges, graph)` e `apply_gap_fixes(edges, fixes, node_decimals) -> List[Edge]` sostituiscono i metodi DXF-based dell'adapter. `compute_gap_fixes` invariato. Rimossi da `adapter.py`: `extract_free_endpoints`, `apply_gap_fixes`, `to_circular_arcs`, `load_entity_lists`, `_gap_meta_for`, `_GAP_KIND_MAP`.
- **Regressione bending risolta** — `Edge.closed_path: bool` (nuovo campo). `to_edges()` lo mette a True per i segmenti esplosi da LWPOLYLINE/POLYLINE chiuse; `BendingDetector` scarta questi edge dai candidati piega (era la guardia `_is_closed_polyline_ref(source_ref)` persa col Passo 4).
- Helper: `forge/core/geometry.py::node_decimals_for(tol)`, `forge/core/primitives/segments.py::segment_endpoints(seg)`.

Verifica: `tests/real/test_golden.py` **48/48**, `tests/real/test_golden_split.py` **51/51**.
Suite completa dopo il **Passo 8**: **440 passed / 0 failed / 0 errors** (2 xfail preesistenti).

## Passo 5 — source_ref: FATTO

Rimosso da: `Edge`, `ClosedShape`/`OpenShape`, `Feature` e gerarchia, `Hole`, `BendingLine`,
`ForgeContour`, `ClassifiedEntity`, `loop_finder.edges_to_open_shapes`.

Completato in questa sessione:
- `forge/adapters/pdf/graph_adapter.py` — rimosse le 3 costruzioni `Edge(source_ref=item)`
- `forge/io/text_utils.py` — `extract_forge_texts()` non passa più `source_ref=e`
- `forge/model/text.py` — rimosso il campo `source_ref` da `ForgeText` (import `Any`/`Optional` puliti)
- commenti/docstring stantii aggiornati: `loop_finder.py`, `feature.py` (+ import `Any` rimosso),
  `adapters/bridge/edge.py`

`grep -rn source_ref forge/` ora trova solo prosa che spiega l'assenza del campo
(`write.py`, `document.py`). Golden 48/48, split 51/51.

## Passo 7bis — `write`→`to_dxf` e `split` puro: FATTO

- **`write` → `to_dxf`** — `forge/pipeline/write.py`. Firma invariata:
  `to_dxf(result, source_doc=None, filter_part=None, include_annotations=True) -> Drawing`.
  Esportato da `forge/__init__.py` (`__all__`, docstring) e `forge/pipeline/__init__.py`.
- **`split` è puro** — ritorna `list[Drawing]` nell'ordine delle parti tenute.
  Niente più `os` / `output_folder` / `saveas` / `keep_trash`. Parametri rimasti:
  `namer`, `include_annotations`, `min_area`, `exclude_types`, `on_part`.
  `namer(i, part)` assegna `part.label` (così il nome file resta ricavabile a valle).
  `on_part` ora è `on_part(part, doc_out)` — niente più terzo arg `out_path`.
  Nuovo helper esportato: `part_passes_min_area(part, min_area) -> bool`.
- **`split_to_files`** (`forge/pipeline/__init__.py`) è l'unica funzione che tocca
  il disco: `heal → detect → split → saveas`. Nome file: `f"{part.label}.dxf"`.
  Perso il param `keep_trash`.
- Migrati: `tests/real/test_golden_split.py` (usa `split` + `saveas` manuale,
  importa `part_passes_min_area`/`DEFAULT_MIN_PART_AREA`),
  `tests/integration/test_helpers.py` (`forge.write` → `forge.to_dxf`).
- `tests/generate_golden_split.py` NON toccato: è ancora su vecchia API modello
  (`load_dxf` che ritorna `(_, msp)`, `heal(msp)`) → va fatto nel Passo 8 insieme
  agli script root.

Verifica dopo 7bis: golden 48/48, split 51/51. Suite completa invariata:
**217 passed / 208 failed / 16 errors** (nessuna regressione).

`split` resta API esposta di prima classe: è il seam giusto per il futuro
("isole" / disegno in tavola su più viste).

NON fare: `split` come flag booleano di `to_dxf` (`to_dxf(result, split=True)`).
Tipo di ritorno che cambia su un flag = API non tipizzabile.

## Passo 8 — migrazione test: FATTO

Traduzione meccanica vecchia API → nuova (nomi **post Passo 7bis**):
- `heal(msp, ...)` / `heal(msp, label_map=...)` → `heal(forge.document_from_msp(msp, label_map=...), ...)` oppure via `load_dxf`
- `doc, msp = load_dxf(...)` → `doc = load_dxf(...)`
- `detect(result, msp)` → `detect(result)` (non prende più il msp)
- `write(msp, result)` → `doc_out = to_dxf(result, doc)`
- `split(msp, result, folder)` → `docs = split(result, doc)` + `saveas`, oppure `split_to_files(doc, folder, ...)`
- test che ispezionano `msp` dopo il write → ispezionare `doc_out.modelspace()`
  o il modello (`result.trash_entities`, `part.engrave_lines`, ...)

Migrati (meccanica): `tests/unit/test_healer.py`, `tests/integration/test_gap.py`,
`tests/integration/test_injector.py`, `tests/integration/test_special_layers.py`,
`tests/integration/test_pipeline.py`, `tests/unit/test_detect.py`,
`tests/real/test_edge_cases.py`.

Migrati + riscritte le parti su comportamento sparito (scrittura nel msp
sorgente / layer "Trash" / `keep_trash`), ora verificano `to_dxf`/`split` o il
modello: `tests/integration/test_writeback.py` (riscritto intero),
`tests/integration/test_splitter.py` (helper `_split_files` locale: `split` puro
+ `saveas`), `tests/real/test_layers.py` (`_run_pipeline` → `(source_doc, doc_out,
result)`; `TestLineetteBastarde` off `bl.source_ref`).

Migrati per Passo 4/5 (`Edge` senza `source_ref`/`layer`/`geometry`, ora
`role`+`segment`+`closed_path`; `Feature.role` obbligatorio; `parse_loop` non
riparsare più l'entità): `tests/unit/test_models.py` (`TestEdge` riscritto),
`tests/unit/adapters/test_parsing_and_exporting.py` (`make_edge` costruisce la
primitiva reale via `DxfEntityDispatcher`), `tests/unit/core/test_hierarchy_builder.py`.

Script aggiornati: `01_run_healer_interpreter.py` (ora `doc_out = forge.to_dxf(result, doc)`
+ `doc_out.saveas(output_dxf)` — salva davvero il DXF), `tests/generate_golden.py`,
`tests/generate_golden_split.py`. (Gli script `02_*.py … 20_*.py` non esistono.)

### Regressione engrave in `to_dxf()` — RISOLTA

**Sintomo:** `to_dxf()` non materializzava le engrave line. `_handle_engrave_open`
/ `_handle_engrave_closed` creavano `EngravingOpen`/`EngravingClosed` con
`segments=[]`, e `to_dxf` fa `write_segments(eng.segments, ...)` → zero entità
sul layer Engrave del documento di output.

**Perché i golden non l'hanno preso:** `test_golden` / `test_golden_split`
verificano il *modello* (`part.engrave_lines`, `total_engrave_length`, `to_dict`)
e la geometria di outer/holes nei figli — mai una engrave line riletta da un DXF
materializzato. Il bug viveva solo nel path `to_dxf` (documento nuovo, introdotto
al Passo 6/7bis) che nessun golden riattraversa.

**Fix:**
- `OpenShape` ora ha un campo `segments` (come `ClosedShape`).
- `edges_to_open_shapes` lo popola con `[edge.segment]` — la primitiva nativa,
  non i punti discretizzati.
- `_handle_engrave_open` / `_handle_engrave_closed` passano `segments=` al
  costruttore di `EngravingOpen` / `EngravingClosed`.
- Nuova copertura: `test_writeback.TestWritebackSpecialLayers.test_003_engrave_geometry_materialized`
  e `test_special_layers.TestSpecialLayerNotTrash.test_002` rileggono il layer
  Engrave del `doc_out`.

**Comportamento voluto (non un limite):** un contorno chiuso su layer engrave
non viene trattato come loop strutturale (`_loop_is_structural` non include
`ENGRAVE`, giustamente). Il ruolo è deciso al load da `label_map` — a valle è
engrave e basta: viene materializzato come N segmenti sul layer Engrave e non
entra nei conteggi strutturali (fori, inner). Se serve una polilinea chiusa
unica invece di N segmenti è solo cosmesi di output, non correttezza.

### Engrave/marking fuori dalla topologia — FATTO

Gli Edge con `role` ENGRAVE o MARKING (deciso da `label_map` al load) non entrano
più nel grafo né nella ricerca loop: `HealStep._split_labeled()` li estrae da
`self.edges` prima di `_preprocess()`. Erano prima *walkati* da `LoopFinder` e poi
scartati da `_loop_is_structural()` — lavoro sprecato, e un loop misto
strutturale+engrave veniva buttato intero.

`HealStep._labeled_proxies()` li riconverte in proxy e li mette in
`result.trash_entities`:
- traccia aperta → `OpenShape(role=...)`
- traccia già degenere (CIRCLE, SPLINE chiusa, `edge.start == edge.end`) →
  `ClosedShape(role=...)` — **prima veniva persa in silenzio** dal guard
  `edge.start == edge.end` di `edges_to_open_shapes`.

`detect._detect_labeled()` fa l'unico calcolo che li riguarda, il contenimento:
- dentro un part → `part.engrave_lines` (`EngravingOpen`/`EngravingClosed`) o
  classified entity per marking;
- fuori da ogni part → **resta in `trash_entities`**, geometria orfana come
  qualsiasi entità non contenuta nell'outer (`_handle_engrave_open` ora ritorna
  `bool`; niente più warning + drop).

Nuovo: `_handle_engrave_closed_trash()`. Copertura:
`test_special_layers.TestEngraveDegenerateCircle`. Suite: 445 passed.

### `Engraving` unico + seam per l'inferenza — FATTO

`EngravingClosed` / `EngravingOpen` collassati in un solo `Engraving(OpenFeature)`
(`model/engraving.py`). Nessuno shim: aggiornati `model/__init__`, `model/part.py`
(`engrave_lines: List[Engraving]`), `detect.py`, docstring di `feature.py`.
- `Engraving` porta `segments` + `length` + `pts` + `geometry` + `polygon`
  opzionale (solo per traccia degenere). `closed` **non è un campo**: è una
  property = `polygon is not None`, così non può desincronizzarsi.
- Nuovi campi `source` / `confidence`, **stesso pattern di `Hole`**:
  `source="labeled"` (da label_map, confidence 1.0) vs `source="geometric"`
  (inferenza). `to_dict()` li espone (i golden confrontano solo `closed`/`length`
  /`role`, quindi non si rompono).
- Costruttori centralizzati: `_engraving_from_open()` / `_engraving_from_closed()`.

**Perché un tipo solo:** in produzione nessuno ramificava su `EngravingClosed`
vs `EngravingOpen` — `to_dxf` scrive `eng.segments` e `inject` somma `eng.length`
per entrambi. La distinzione viveva solo in `to_dict()["closed"]`.

**Seam per l'inferenza:** `detect._detect_engrave(result, engrave_tolerance)` —
placeholder no-op, già inserito nella pipeline `detect()` e già con il parametro
`engrave_tolerance`. Quando implementato: guarda `part.inners` con role UNKNOWN e
`result.trash_entities`, promuove a `Engraving(source="geometric")` i pattern
riconoscibili (es. inner = due polilinee ~parallele a distanza < tolerance →
incisione, non foro/inner). Le feature — engraving, bending, countersink,
threaded — condividono tutte il doppio binario label_map / inferenza; `Hole` è
l'implementazione di riferimento (`hole_type` + `geometric_hint` + `source` +
`confidence`), `Engraving` ora lo segue, `BendingLine` no (manca `source`).

## Fatto: già migrati (sessioni precedenti)

`tests/integration/test_helpers.py`, `tests/real/test_golden.py`, `tests/real/test_golden_split.py`.