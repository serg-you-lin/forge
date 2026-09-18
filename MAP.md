# MAP.md — decision log di dxf-forge

Questo file è la **memoria delle decisioni**: cosa è stato deciso, e soprattutto
*perché*. Non è documentazione (quella è in `docs/`) e non è un log di sessione
(quello è il git log).

Regola: una decisione chiusa **non si re-decide da capo**. Se va rimessa in
discussione si dice esplicitamente "stiamo riaprendo la decisione N".

- **Cos'è forge, come si usa** → `README.md`, `docs/API.md`
- **Com'è fatto dentro** → `docs/ARCHITECTURE.md`
- **Storia del refactor** → git log (branch `refactor/structure`)

---

## Il contratto dell'API pubblica

```python
doc    = forge.load_dxf("file.dxf")        # unico punto che tocca ezdxf in lettura
result = forge.heal(doc)                   # topologia — zero DXF
result = forge.detect(result, "all")       # semantica/feature — zero DXF
doc_out = forge.to_dxf(result, doc)        # documento nuovo — nessun source_ref
doc_out.saveas("output.dxf")

# multi-pezzo
forge.split_to_files(doc, "output/")       # unica funzione che scrive su disco

# futuro: stesso contratto, adapter diverso
doc = forge.load_svg("file.svg")
```

**Principio portante:** `load_*` produce un `ForgeDocument` di dati puri (edge +
annotation). Dopo il load, il documento `ezdxf` sorgente sparisce. `heal` /
`detect` non vedono mai un formato. `to_dxf` costruisce un documento **nuovo** dai
segmenti del modello — non copia entità dalla sorgente, non porta `source_ref`.
Il modello è il prodotto; il DXF è solo una delle sue rappresentazioni.

Dettaglio completo di ogni funzione in `docs/API.md`.

---

## Stato

Branch: `refactor/structure`. Fasi 1–4 concluse e committate. Suite: **555 passed
/ 0 failed** (+ 62 subtests), golden verdi.

Da fare, in ordine:
1. ✅ Riscrittura degli script numerati alla radice (`00_*.py … 12_*.py`), uno
   per area di `forge.__all__`, default su `tests/examples/` (D14).
2. ✅ `to_view_model` + `to_svg` / `save_svg` (D12).
3. `detect_engrave` (D13) — quando Federico decide.
4. `forge/io/text_utils.py`: da riordinare (2026-08-31). Oggi mischia
   *estrazione* da ezdxf (`extract_forge_texts`, quella vera che alimenta
   `inject()`; `extract_texts_from_msp` resta solo per debug/stampa) e
   *pulizia del contenuto testuale* (`clean_mtext`). Idea di Federico: un
   modulo di gestione testi accessibile anche a un agente esterno, che lavori
   su stringhe pure — zero import di ezdxf dentro. Da decidere: separare in
   (a) estrazione lato adapter DXF (resta vicino a ezdxf) e (b) un modulo
   pure-text a valle (matching/pulizia/riconoscimento materiale-spessore-
   codice) senza dipendenze dal formato. Non ancora iniziato.
5. Merge di `refactor/structure` in `main`.
6. Dashboard — **repo separata** (D16). Rendering nel browser (SVG/Canvas JS)
   da `to_view_model`; backend = server Python sottile attorno a
   `heal_and_detect`. `to_svg` resta comodità di libreria (export, thumbnail).

---

## DECISIONI CHIUSE

### D1 — Nome libreria: resta `forge` (per ora)
`heal` come nome package è stato valutato e scartato (`from heal import heal`
suona male). `dxf-forge` è fuorviante — troppo legato al formato, mentre il punto
è che il modello è format-agnostic — ma il rename si rimanda. Package importabile:
`forge`.

### D2 — `heal_and_detect(doc)` come funzione della via del 90%  ✅
Funzione top-level che fa `heal → detect` e ritorna il `ForgeResult`. Va nel
README. `heal()` e `detect()` restano separate e pubbliche: un renderer o un
nesting tool possono volere la sola topologia. Nome esplicito e un po' goffo di
proposito — scelta umana, non "process". `detect()` viene saltato se `heal()` non
produce parti valide.

### D3 — `detect()` / `inject()` ritornano il result  ✅
Non ritornano più `None`: ritornano il `ForgeResult` (lo stesso oggetto, mutato)
così la catena è esplicita: `result = forge.detect(result)`. Nessun test
dipendeva dal `None`.

### D4 — `OpenShape` / `ClosedShape` (bridge) eliminati  ✅
`heal` produce direttamente `OpenFeature` / `ClosedFeature`; `bridge/shape.py`
cancellato. `pts` / `length` / `shape_type` ora derivati dai segmenti nativi via
`core/geometry.py` (`track_points` / `track_length` / `track_shape_type`).
`OpenFeature` / `ClosedFeature` (`model/feature.py`) **tenuti**: la distinzione
"ha polygon / non ce l'ha" è onesta e dà `area` / `bbox` gratis. È stato il
cambiamento più invasivo della Fase 4 — fatto sub-step per sub-step con la suite
golden come rete.

### D5 — `source` / `confidence` sulle feature rilevate  ✅
`Hole`, `Engraving`, `BendingLine`, `ClassifiedEntity` restano tutte e quattro:
sono quattro intenti di fabbricazione con consumatori diversi. Ognuna porta
`source: str` e `confidence: float`, popolati in `detect.py`: lane geometrica →
`source="geometric"`, lane `label_map` → `source="labeled"` / `confidence=1.0`.
**Niente gerarchia con ereditarietà multipla** — è una convenzione, non una torre
di classi. `ClassifiedEntity` resta fuori dalla gerarchia `Feature` per scelta
(via di fuga dict-based). Invariante: dopo `detect()`, ogni feature ha `source` +
`confidence` sensati.

Struttura finale del modello:
```
Feature (role)
├── ClosedFeature (polygon, segments) → ForgeContour, Hole
└── OpenFeature   (segments)          → Engraving, BendingLine
ClassifiedEntity  → catch-all dict-based, fuori gerarchia per scelta
```

### D6 — `parse_loop` → `segments_from_loop`  ✅
Rinominata e spostata da `adapters/dxf/parser.py` a
`core/topology/loop_finder.py` (logica di dominio pura, non parsing DXF).
`_reverse_segment` rimosso: `LineSeg` / `ArcSeg` / `CircleSeg` hanno `.reversed()`
come `SplineSeg`.

### D7 — Un solo dispatcher entità→primitiva  ✅
`parser.py::DxfEntityDispatcher` e `adapter.py::entity_to_primitive` erano due
copie quasi identiche. Ora una sola (`DxfEntityDispatcher`), usata da produzione
**e** test. **Bug latente scoperto e corretto:** `ArcSeg.from_chord` sbagliava
gli archi maggiori (`|bulge| > 1`, sweep > 180°) — usava `sqrt(r² - half_chord²)`
(sempre positivo → sempre arco minore) invece di `r·cos(sweep/2)` (con segno).
Era mascherato perché la produzione usava il `_bulge_to_arc` corretto di
`adapter.py`. 5 golden roundtrip lo hanno preso appena unificato il dispatcher.

### D8 — `inject()` sgonfiato  ✅
I conteggi feature (fori per tipo, pieghe, incisioni, marking) sono ora
`ForgePart.summary`, property derivata dal modello — non più copiati in
`part.custom` da `inject()`. `inject()` resta solo per il `data_injector` esterno
(materiale / spessore / codice dai testi); senza `data_injector` non fa nulla.
Equivalenza provata prima di toccare i fixture (`part.summary ==
inject().part.custom` su tutte le 63 parti golden, 0 mismatch), poi rename
chirurgico `"custom"` → `"summary"` nei fixture.

### D9 — L'inspector diventa strumento a 3 livelli  ✅
`dxf_inspect.py` (morto, import rotti) → `forge/inspect.py`, esportato. Stampa
tre livelli: (1) entità DXF grezze — "cosa c'è nel file"; (2) primitive / edge /
grafo dopo `load_dxf` — "cosa ha capito l'adapter"; (3) il modello dopo
`heal` / `detect` — "cosa ha prodotto forge". Serve per lavorare su file reali
(es. quando si implementerà `detect_engrave`).

### D10 — `load_pdf` congelato  ✅
Ritorna `list[Edge]`, non un `ForgeDocument` → `forge.heal()` lo rifiuta. Tolto
da `__all__`, marcato sperimentale. Il codice **non si tocca**. Resta importabile
come `forge.load_pdf`. PDF si riprende più avanti (o mai).

### D11 — Versione: unico punto = `pyproject.toml`  ✅
`forge.__version__` la legge con `importlib.metadata.version("forge")`, fallback
`0.0.0+dev`. Non si aggiorna più niente a mano tranne il `pyproject`.

### D12 — SVG: solo in uscita, spline discretizzate  ✅
`to_svg(result)` è un renderer del modello; archi/cerchi/spline appiattiti a
polilinea (accettabile per visualizzare, non per il taglio). **Niente
`SvgAdapter` in ingresso** finché non arriva un file SVG reale.

Implementato in due pezzi (`forge/io/`):
- **`to_view_model(result)`** — `ForgeResult` → dict JSON con la geometria di
  *ogni* feature + ruolo + colore hex. È il vero contratto per un renderer
  esterno (dashboard JS).
- **`to_svg` / `save_svg`** — SVG "batterie incluse" costruito sopra il view
  model. Un colore per ruolo (palette semantica condivisa col DXF), Y ribaltata,
  una parte = un `<g data-part>`, fori come `<circle>` veri.
- `forge/rules/palette.py` esteso: `ROLE_TO_COLOR` completo + `ACI_TO_HEX` +
  `role_to_hex()` (nessuna dipendenza da ezdxf o dal formato).

### D13 — `detect_engrave`: rimandato
`_detect_engrave` resta placeholder no-op. Il seam nella pipeline `detect()` c'è
già (parametro `engrave_tolerance`, chiamata in `detect()`). Quando implementato:
guarda `part.inners` con role UNKNOWN e `result.trash_entities`, promuove a
`Engraving(source="geometric")` i pattern riconoscibili (es. due polilinee
~parallele a distanza < tolerance → incisione, non foro). Federico lo
implementerà dopo aver fatto ordine.

### D14 — Script numerati alla radice: restano, ma si riscrivono
Federico li usa come palestra per capire l'API. Decisione aggiornata (2026-08-29):
non solo si tengono, si **riscrivono e rinumerano** — idealmente uno script per
ogni funzione di `forge.__all__`, con un `INPUT` di default che punti a
`tests/examples/` così girano senza configurazione. `.gitignore` copre già i loro
output (`*_healed.dxf`, `*.png`, `pipeline_output/`, `_split_debug/`).
`13_ARC_splitter` è **fuori da questo lavoro**: è codice di produzione su file
cliente, va portato alla nuova API in una sessione dedicata e collaudato da
Federico con il suo overlay-check in SigmaNest.

### D15 — `detect()` parametrico + classificazione hole spostata lì  ✅
Principio: `HOLE_DIAMETER_THRESHOLD` (32.1 mm) è un **parametro di processo** —
la capacità di foratura della macchina/utensile — non una costante di dominio. I
parametri di processo appartengono alla chiamata di classificazione, non alla
topologia.

Forma finale:
- `heal` produce **solo** l'albero di contenimento:
  `ForgePart(outer, inners=[ForgeContour...])`, zero `Hole`.
- `detect()` è parametrico:
  - `detect(result)` nudo → default taglio laser: solo lane `label_map`
    (autoritativa) + pulizia topologia, zero `Hole`;
  - `detect(result, "holes" | "bending" | "engrave" | "all")` → lane geometriche
    opt-in;
  - `max_drill_diameter` (default 32.1) è argomento di `detect()`: Ø < soglia →
    `Hole`, Ø ≥ soglia → resta `ForgeContour` inner.
- `heal_and_detect(..., features="all")` è la via del 90%.
- `ClosedFeature.diameter` / `center` rimossi: la geometria circolare la ricava
  `core/geometry.circular_geometry`.

Prova di equivalenza su tutti i golden (`features="all"`): diff **solo** su 7
file, dove cerchi Ø ≥ 32.1 migrano da `Hole(role="inner")` a
`ForgeContour(role=INNER)` — che è il comportamento voluto. Golden rigenerati uno
per uno, diff verificato a mano.

Effetto collaterale: il vecchio bug `Hole(role="inner")` prodotto da `hierarchy`
sparisce da solo (nessun `Hole` da `hierarchy`).

Riferimento: memoria `hole-classification-belongs-in-detect`.

### D16 — Dashboard: repo separata, non branch
Una eventuale dashboard / interfaccia è un'**app** con dipendenze proprie (web
server o toolkit GUI), ciclo di release diverso, e non deve inquinare la repo
della libreria. Va in una repo a sé che fa `pip install forge` (o `-e` in
sviluppo), come già `snapmark`. I prototipi in `dev_tools/` (`dashboard.py`,
`dashboard_2.py`, `split_verify*.py`, `dxf_kernel*.py`) sono il punto di
partenza, si portano lì. Un branch andrebbe bene solo per un prototipo
usa-e-getta dentro questa stessa storia.

### D17 — La posizione XY del mondo è preservata (invariante, non decisione)
Registrato qui perché è una garanzia su cui si appoggia il flusso di produzione
(split → import in SigmaNest → overlay dell'originale per il registration check).
La pipeline **non trasla mai** la geometria: `load_dxf` sanifica l'OCS
(`normalize_ocs`: gira il vettore di estrusione senza alterare la geometria in
WCS) e appiattisce la Z; `heal` tocca solo gli endpoint per chiudere i gap;
`to_dxf` / `split` scrivono `center` / `pts` dei segmenti verbatim. Ogni parte
splittata atterra alla stessa coordinata XY assoluta della sorgente. **Unica
perdita voluta:** la Z viene appiattita a 0 (corretto per lamiera/laser).
`test_golden_split` blocca questo invariante — confronta l'`outer_wkt` con
coordinate assolute, un ricentraggio lo farebbe fallire.

### D18 — `to_nester_input`: fuori da `__all__`, sperimentale
dxf-forge **non fa nesting** (disporre i pezzi in tavola per minimizzare lo
sfrido) e non lo farà, salvo commessa pagata da un cliente. `to_nester_input`
era stato scritto all'inizio per un nester mai realizzato. Trattamento identico a
`load_pdf` (D10): il codice resta, importabile come `forge.to_nester_input`, ma
fuori da `__all__` e non documentato nel contratto. La serializzazione della
geometria per renderer/tool è `to_view_model` (D12).
Riferimento: memoria `nesting-out-of-scope`.

### D19 — `adapters/bridge/` eliminato, `Edge` spostato in `core/topology/edge.py`  ✅
Segnalato da Federico: `bridge/` era rimasta con un solo file (`edge.py`) dopo
l'eliminazione di `shape.py` (D4) — smell di cartella. Più a fondo: `Edge`
viveva sotto `adapters/` ma `core/topology/graph.py`, `loop_finder.py`,
`bending_detector.py`, `core/healing/gap_solver.py` e `core/adapter_base.py`
lo importavano tutti da lì — **`core` dipendeva da `adapters`**, il contrario
esatto della regola di dipendenza (`docs/ARCHITECTURE.md`). `Edge` non è una
primitiva (quelle sono math puro in `core/primitives/segments.py`): è un
wrapper topologico con ruolo/stile/provenienza attorno a una primitiva —
appartiene a `core/topology/`, dove vivono i suoi consumatori veri. Spostato
lì; adapter DXF/PDF ora lo importano da `core`, come da regola. Nessuna
modifica di comportamento — solo import aggiornati. Suite: 579 passed.

### D20 — Annotazioni: modello tipato + fase `interpret` separata  ✅
Segnalato da Federico: le annotazioni erano un casino. Due modelli paralleli non
tipati per la stessa cosa — `Annotation(kind, position, data=dict)` in
`model/document.py`, prodotto da `annotation_extractor.py` e consumato da
`write()`, e `ForgeText(content, position: shapely.Point)` in `model/text.py`,
prodotto da `io/text_utils.extract_forge_texts` e consumato da `inject()` — che
leggevano la stessa entità DXF due volte. In più `io/text_utils.py` (codice DXF
puro, ma sotto `io/`) e `annotation_extractor.py` si importavano a vicenda.

Decisione, in linea con `annotations-are-first-class-interpreted-content`:

- **Un solo modello tipato** in `model/annotation.py`: `Annotation` base +
  `Note` / `Dimension` / `Leader`, più `RenderedGeometry` / `RenderedText` per
  l'immagine appiattita di quote e direttrici. Niente `data` dict, niente
  `shapely` nei campi (posizione = tupla). `Annotation(data=dict)` e `ForgeText`
  eliminati.
- **Adapter = solo formato.** `annotation_extractor` legge DXF → oggetti tipati;
  `write` fa l'inverso, fedele. Gli helper stringa MTEXT stanno in
  `adapters/dxf/mtext.py` (`clean_mtext` riesportata da `forge`).
- **Interpretazione in una fase a sé**, `forge.interpret_annotations(result)`,
  **non** dentro `detect()` (che fa già troppo — vedi
  `keep-detect-focused-prefer-separate-stages`). Oggi popola solo
  `Annotation.part_ref` (indice della parte contenitrice); `references` /
  `target` verso le feature sono predisposti ma non ancora calcolati.
- `inject()` non prende più `texts=` né un `msp`: filtra `result.annotations`
  per contenimento. `io/text_utils.py`, `extract_texts_from_msp` e
  `extract_forge_texts` rimossi (nessun chiamante reale, clean break).

Regressione trovata e risolta lungo la strada (`b5b2503`): i MULTILEADER
solo-testo senza anchor/vertici/geometria (Solid Edge) venivano scartati.
Fixture `6200013103_P1NoLineaPiega` aggiunta a `golden/` e `golden_multipli/`;
nuovo golden `golden/annotations/` con `generate_golden_annotations.py`. Due bug
noti pre-esistenti su quella fixture documentati in `file_test_status.md` (BL
sotto-rilevate sul pezzo _1; cartiglio rilevato come parte). Suite: 610 passed.

### D21 — `ForgePart` → `ForgeCluster`  ✅

`heal()` produce **cluster**: gruppi di geometria separati spazialmente. Un
cluster *può* essere un pezzo lavorabile, ma anche una vista, una sezione, un
particolare o il cartiglio — la "part-ness" è interpretazione del consumatore,
non una cosa che forge decide (vedi `INTERPRETER.md` e la memoria
`forge-clusters-not-parts`). Il nome `ForgePart` prometteva una semantica che
forge non fornisce.

Rename meccanico, zero logica cambiata: `ForgePart` → `ForgeCluster`,
`result.parts` → `result.clusters`, `part_count` → `cluster_count`,
`Annotation.part_ref` → `cluster_ref`, `*.part_label` → `cluster_label`,
`filter_part`/`on_part`/`namer(i, part)` → `cluster`, `DEFAULT_MIN_PART_AREA`
→ `DEFAULT_MIN_CLUSTER_AREA`, file `model/part.py` → `model/cluster.py`. Chiavi
di output rinominate (`to_dict`, `save_json`, `save_xml` `<clusters><cluster>`,
`to_view_model`, `data-cluster` in SVG, schema `source="cluster"`). Golden
rigenerati sulle **sole chiavi** — diff verificato: nessun valore geometrico
toccato. Suite: 610 passed.

Breaking: le chiavi JSON/XML cambiano nome. Nessun consumatore reale le legge
ancora. Branch `refactor/clusters`, merge ff, `main` a 0.6.3.

### D22 — `pipeline/` sciolto: `heal`→core, `tools/`, renderer in `io/`  ✅

Segnalato da Federico: `pipeline/` non era "una cosa", mescolava tre tipi
diversi di modulo, e il nome implicava una sequenza fissa che la libreria non
impone ("non una pipeline fissa ma oggetti puliti su cui costruire").

- **`heal.py` (`HealStep` + `heal()`) → `forge/core/heal.py`.** È l'atto del
  motore: `ForgeDocument` → `ForgeResult`, orchestra tutto `core/topology` +
  `core/healing`. Non è opzionale — ogni altro passo lavora sul suo output.
  `core/` già dipendeva da `rules/` (`hole_detector` → `rules.thresholds`;
  `rules/validator` → `core.topology`), quindi `heal` che usa
  `rules.validator` non è una violazione nuova. Tolte 3 righe di import morti
  (`LAYER_OUTER`/`LAYER_INNER`/`COLOR_OUTER`/`COLOR_INNER` + `LoopFinder`
  module-level, già re-importato in `_find_loops`).
- **`detect.py` / `interpret.py` / `inject.py` → `forge/tools/`.** Stadi
  opzionali e componibili su un `ForgeResult`: ognuno lo arricchisce in-place e
  lo ritorna, il caller sceglie quali e in che ordine. È il pattern che un
  interprete di disegno (progetto separato) generalizza — vedi `INTERPRETER.md`.
- **`write.py` (`to_dxf` / `split`) → `forge/io/dxf.py`.** Sono renderer del
  modello, esattamente come `to_svg` / `to_json` / `to_view_model` — che erano
  già in `io/`. `ARCHITECTURE.md` li descriveva come renderer mentre il codice
  li teneva altrove.
- **`heal_and_detect` / `split_to_files` → `forge/recipes.py`.** Le scorciatoie
  della "via del 90%": nessuna logica nuova, solo l'ordine comodo.
- Cancellate `forge/pipeline/` e `forge/workflow/` (quest'ultima vuota da
  sempre).

Nessun cambiamento di comportamento — solo file spostati e import aggiornati.
`forge.__all__` invariato. Suite: 610 passed. Branch `refactor/module-layout`,
`main` a 0.6.4.

Il frame (`core/classification/frame_detector.py`,
`adapters/dxf/frame_adapter_dxf.py`) è concettualmente roba dell'interprete ma
resta in forge finché quel repo non esiste. → superato da D24: rimosso, era
codice morto.

### D23 — Script numerati in `scripts/` + `_paths.py` che fa `chdir`  ✅

Aggiorna la parte "alla radice" di D14 (il resto di D14 resta: si tengono, uno
per funzione, default su `tests/examples/`).

Federico lavora copiando un file dove capita e scrivendo `INPUT = r"..."` a
mano. Il punto dolente non era *dove* stanno gli script ma che il percorso
relativo dipende dalla cartella di lavoro: `python scripts/03_detect.py`, il
pulsante Run di VS Code e un terminale aperto dentro `scripts/` davano CWD
diversi, quindi `r"tests/examples/x.dxf"` funzionava in un caso e falliva
nell'altro (stesso problema che ha in snapmark con i DXF di prova).

Forma finale, **un solo modo**:

- gli script stanno in `scripts/` (radice del repo più pulita su GitHub);
- prima riga di ogni script: `import _paths` — `scripts/_paths.py` fa
  `os.chdir()` alla radice del repo (`Path(__file__).parent.parent`);
- nel `CONFIG` si scrive il path grezzo: relativo (parte dal repo) o assoluto
  (usato com'è). Niente `EXAMPLES / "..."`, nessun pattern da ricordare.

L'output relativo (`pipeline_output/`) finisce comunque sotto la radice del
repo grazie al `chdir`. `13_ARC_splitter` si sposta in `scripts/` per coerenza
ma resta fuori serie (path assoluti propri, API pre-refactor, non versionato).

### D24 — Frame detector rimosso da forge (era codice morto)  ✅

Supera la nota in coda a D22 ("resta in forge finché quel repo non esiste").

`core/classification/frame_detector.py` e `adapters/dxf/frame_adapter_dxf.py`
erano già morti: nessun test o script li chiamava, l'adapter importava da
`...core.classify.frame_detector` (path inesistente — la cartella è
`classification`), e `detect_frame()` aveva un `print("DEBUG …")` piantato
dentro. Il rilevamento cornice/cartiglio è per decisione roba dell'interprete
(memoria `forge-neutral-substrate-agent-layer-above`): gira *prima* di `heal`
su geometria grezza, cosa che forge non fa. Tenerlo "solo annotato" significava
tenere in `core/` un modulo rotto che prometteva una capacità che forge non
espone.

Entrambi i file cancellati — sono in git history. L'algoritmo (rettangoli con
ratio ISO √2 ±5% + containment ≥ 80%, conservativo) resta documentato in
`INTERPRETER.md` come specifica di `frame.py`, da implementare lì quando il repo
esiste. Il ruolo `ContourRole.FRAME` resta in forge: è solo un'etichetta (un
importer del layer sopra può assegnarla, `rules/palette` e `adapters/dxf/layers`
le danno un layer di destinazione), non logica di rilevamento.

Branch `refactor/kill-frame-deadcode`.

### D25 — `core/classification/` sciolta: `hole_detector` → `tools/`  ✅

Rimasto un solo file dopo D24 (`hole_detector.py`), più un appunto
(`possibili_altri.md`). Segnalato da Federico: la cartella sembrava un progetto
a sé dentro `core/`, fuori posto.

`is_threaded_hole` / `is_countersink_outer` sono euristiche di *riconoscimento*
usate solo da `tools/detect.py`, non geometria di base riusabile (quella è
`core/geometry.py` / `core/primitives/`). Per la linea di
`keep-detect-focused-prefer-separate-stages` le preoccupazioni di riconoscimento
stanno sotto `tools/` accanto al loro consumatore. Spostato a
`forge/tools/hole_detector.py`; `detect.py` importa `from .hole_detector`.
`core/` ora è solo il motore geometrico deterministico: `primitives`,
`topology`, `healing`, `geometry.py`, `heal.py`, `adapter_base.py`.

`possibili_altri.md` cancellato — l'idea (nuovi classificatori = un modulo
opt-in per volta sotto `tools/`, `detect` diventa package se cresce) è già in
`keep-detect-focused-prefer-separate-stages` e in TODO.md.

Tolta anche `forge/adapters/bridge/`, cartella vuota rimasta dopo D19 (non
tracciata da git, solo sul filesystem).

Nessun cambiamento di comportamento. Suite: 610 passed. Branch
`refactor/hole-detector-to-tools`.

### D26 — `model/` riordinato: `ForgeContour` in un file proprio  ✅

Segnalato da Federico: `cluster.py` definiva sia il contenitore (`ForgeCluster`)
sia uno dei suoi elementi (`ForgeContour`), incoerente con `hole.py` /
`engraving.py` / `bending_line.py` che stanno ognuno per conto suo.

- `ForgeContour` → `model/contour.py`, sorella di `Hole` / `Engraving`.
  `cluster.py` la importa per i type hint di `outer` / `inners`.
- `BaseInterpreter` (ABC in `classified.py`) cancellato: nessun implementatore,
  e la firma citava `msp` (modelspace ezdxf, concetto pre-refactor).
- `ClassifiedEntity` **resta in `model/`**: `ForgeResult.classified_entities`
  la contiene, spostarla in `tools/` farebbe dipendere `model/` da `tools/`.
  Aggiunto un docstring che lo spiega.

Import diretti aggiornati (`core/healing/hierarchy.py`, 2 test). `forge.__all__`
e `forge.model.__all__` invariati salvo `BaseInterpreter` rimosso. Suite: 610
passed.

### D27 — `ContourRole` vocabolario aperto  ✅

Sintesi della discussione "ContourRole question" (parere di ChatGPT, condiviso
da Federico): forge non definisce il mondo, fornisce un linguaggio geometrico +
ruoli noti su cui altri costruiscono la loro semantica. Un `ContourRole` chiuso
che rifiuta l'ignoto è contro la direzione "substrato neutro"
(`forge-neutral-substrate-agent-layer-above`).

Regola:

- **A — enum non autoritativo, mai reverse-lookup da input esterno.**
  `ContourRole` resta la raccolta dei ruoli noti (costanti comode). Forge fa
  solo test di appartenenza (`role == ContourRole.OUTER`, `role in
  STRUCTURAL_ROLES`). Vietati `ContourRole[x]`, `getattr(ContourRole, x)`,
  `ContourRole(x)` su dati del chiamante, e l'API funzionale `Enum(...)`:
  sollevano o raggiungono attributi di classe. La mappa stringa→ruolo passa
  sempre per un `dict.get`.
- **B — un solo punto di normalizzazione, al load.** `model/role.normalize_role`:
  `str` o `"unknown"`; minuscole; charset `[a-z0-9_-]` (il resto collassato in
  `_` — neutralizza i payload di injection); ≤ 64 char; noto → costante,
  ignoto-valido → slug conservato. `layer_to_role` / `_style_role` (dxf) /
  `_role_from` (geometry) ci passano invece di schiacciare a `UNKNOWN`.
- **C — difesa anche ai sink.** `role_to_dxf_layer` / `ROLE_TO_LAYER.get` →
  ignoto su `TRASH_LAYER` (già così); `role_to_hex` → `COLOR_TRASH`; SVG
  `html.escape` su qualsiasi ruolo in un attributo. Ridondante rispetto a B,
  voluto.
- **D — `role_str(role)`** al posto di `.role.value`, che esplode su una `str`.

Type hint `role: ContourRole` → `role: str` in `model/feature.py`,
`core/topology/edge.py`, `adapters/geometry/loader.py`. `VALID_WORK_TYPES`
(era in `rules/thresholds.py`, morto) rimosso. Un ruolo custom (`title_block`)
sopravvive `load → heal`: geometria in `trash_entities`, ruolo intatto, nessun
warning. Suite: 619 passed (9 nuovi in `test_role.py`).

Branch `refactor/open-roles` (parte da `refactor/model-tidy`), merge unico →
`main` 0.6.7.

### D28 — `BendingDetector` → `NonContourEdgeDetector` (nome neutro)  ✅

Segnalato da Federico: dentro `HealStep` c'era `_find_bending_candidates()` /
`BendingDetector`, che sembrava logica di `detect` finita in `heal`.

Verificato: il modulo **non classifica niente come piega**. Per topologia trova
gli edge con entrambi gli endpoint su nodi di branching e centroide interno al
convex hull, e li **esclude dal grafo prima della ricerca dei loop** — altrimenti
una linea che attraversa il pezzo da parte a parte rompe la chiusura dei
contorni. `non_contour_edge_ids` è stato interno di `HealStep`: non finisce mai
sul `ForgeResult`. La semantica vera ("questa linea è una piega") resta in
`tools/detect._detect_bending`, che ripesca queste linee dalla trash — opt-in.

Quindi il lavoro è legittimamente di `heal`; solo il nome prendeva in prestito
il vocabolario di `detect`. Rinominato, non spostato:

- `core/topology/bending_detector.py` → `non_contour_edges.py`
- `class BendingDetector` → `NonContourEdgeDetector`
- `HealStep.candidate_bending_ids` → `non_contour_edge_ids`
- `_find_bending_candidates()` → `_find_non_contour_edges()`
- `_reintegrate_bending()` (era un `pass`) → cancellato

Nessun cambiamento di comportamento. Branch `refactor/rename-non-contour-edges`,
merge → `main` 0.6.8.

### D29 — Rilevamento cornice / cartiglio: modulo `Framer`, fuori da forge  → `FRAMER.md`

Il riconoscimento di cornice e cartiglio diventa un **modulo a sé**, `Framer`,
consumatore di forge e componente dell'interprete (sorella dell'unfolder). Non
entra in forge: gira *prima* di `heal` sulla geometria grezza, marca gli edge
con `role="frame"` / `role="title_block"` e li riporta giù a forge — coerente con
`forge-neutral-substrate-agent-layer-above` e con la rimozione del
`frame_detector` in D24. Serve anche da primo banco di prova reale
dell'interfaccia forge ↔ consumatore (come un modulo esterno inietta decisioni
geometriche prima di `heal`).

Design completo, algoritmo, e le tre opzioni per l'aggancio a `heal` (A: Framer
rimuove gli edge; B: forge estende il filtro non-strutturale a `frame`; C: hook
`role_resolver`) in `FRAMER.md`. Prima cosa da chiudere: quale delle tre.

Nessun codice ancora — solo il documento di progetto.

### D30 — Predicato strutturale unico + `detect()` non tocca i ruoli che non conosce  ✅

Preparazione dell'aggancio di `Framer` (D29): scelta l'**opzione B**. Nessuna
API nuova su forge, solo consolidamento perché l'aggancio "un consumatore marca
`edge.role` su `doc.edges` prima di `heal`" fosse un contratto e non una
coincidenza.

Il concetto "questo ruolo è topologia di contorno di pezzo" era ridefinito a
mano in quattro punti che **non concordavano** (`thresholds.STRUCTURAL_ROLES` =
`{OUTER, INNER, HOLE}`; `heal._loop_is_structural` = quei tre più
`COUNTERSINK, THREADED_HOLE`; `heal._split_labeled` = esclude solo
`{ENGRAVE, MARKING}`; `hierarchy._collect_trash` = ridefinisce `{OUTER, INNER,
HOLE}` in locale). Un ruolo custom passava indenne solo perché tutte e quattro,
per motivi diversi, lo lasciavano fuori.

- **`model/role.STRUCTURAL_ROLES` + `is_structural_role(role)`** — punto unico.
  `STRUCTURAL_ROLES = {OUTER, INNER, HOLE, COUNTERSINK, THREADED_HOLE}` (l'unione
  semanticamente corretta). Spostato da `rules/thresholds.py` (era tassonomia di
  ruoli, non una soglia). I quattro punti sopra ora chiamano `is_structural_role`.
- **`heal._split_labeled` generalizzato**: estrae dalla topologia **ogni** edge
  con ruolo deciso e non strutturale (prima solo `ENGRAVE`/`MARKING`; ora anche
  `frame`, `bending` label-mappato, slug di un consumatore). Quegli edge saltano
  gap solving, riparazione angoli e detection dei non-contorno — non ci passano
  più "per fortuna". Finiscono in `trash_entities` col ruolo intatto.
- **`detect()` non inventa feature da un ruolo che non conosce** (bug: la D27
  era applicata solo a `heal`). `_detect_labeled` classificava *qualsiasi* proxy
  in trash con ruolo ≠ UNKNOWN, ne faceva un `ClassifiedEntity` scollegato che
  `to_dxf` non riscrive → **geometria persa** (verificato su `6200013103` con il
  cartiglio taggato: 86 entità in output dopo `heal`, 79 dopo `heal + detect`).
  Ora `detect()` tocca solo `_DETECT_KNOWN_ROLES` = `{HOLE, COUNTERSINK,
  THREADED_HOLE, ENGRAVE, BEND, MARKING}`; ogni altro ruolo resta in trash.
- **`forge.normalize_role` / `forge.is_structural_role` in `__all__`** — un
  consumatore normalizza lo slug e sa se il ruolo è contorno o arredo senza
  entrare in `forge.model`.

`_loop_is_structural(loop, label_map)` → `_loop_is_structural(loop)` (il
`label_map` non era usato).

Suite: 625 passed (era 619; +6 in `test_role.py`). Branch
`refactor/consolidate-structural-role`, merge → `main` 0.6.9.

### D31 — `frame` fuori da forge; i ruoli di consumatore vanno su un layer loro  ✅

Verificato su un disegno reale con la cornice (`framer` che tagga `role="frame"`):
la geometria di cornice usciva in output **tutta sul layer `Trash`**, insieme
alla spazzatura vera. `io/dxf._write_trash` scriveva ogni entità su `TRASH_LAYER`
hardcoded, ignorando il `role`. D30 aveva fatto sopravvivere il ruolo fino a
`trash_entities`, ma il writer lo buttava via.

Federico: *"tutto ciò che è framer, ruolo compreso, anche nell'adapter, deve
uscire da forge ed essere assegnato in framer."* Quindi:

- **`ContourRole.FRAME` rimosso.** `frame` non è più una costante di forge né
  una chiave di `WORK_TYPE_TO_ROLE`: è uno slug di consumatore come
  `title_block` / `section`. `normalize_role("frame")` ora ritorna la stringa
  `"frame"`, non una costante.
- **`ROLE_TO_LAYER[FRAME]` e `ROLE_TO_COLOR[FRAME]` rimossi** (erano
  `LAYER_OUTER` / `COLOR_OUTER`, entrambi placeholder sbagliati — la cornice non
  è un contorno di taglio).
- **`_write_trash` instrada per ruolo.** `role_to_dxf_layer(role)`: ruolo noto →
  il suo layer; slug di consumatore (già sanificato) → **un layer col nome
  dello slug**; `unknown` → `Trash`. Il layer si crea al volo con
  `COLOR_CONSUMER` (grigio scuro, ACI 8) — non è spazzatura, non è di taglio.
  `role_to_color` / `role_to_hex` fanno lo stesso per SVG.

Risultato sul disegno reale: `frame` esce su un layer `frame` (11 entità), la
spazzatura vera resta su `Trash` (388). Nota separata: su quel disegno i pezzi
veri non si chiudono in `heal` (archi + linee di costruzione) — è un altro
problema, non D31.

Suite: 626 passed (+1 in `test_role.py`, `test_role.py:77` aggiornato per la
rimozione di `FRAME`). Nessun golden toccato. Branch
`refactor/consumer-roles-out-of-forge`, merge → `main` 0.6.10.

### D32 — `load_geometry` pubblico  ✅

Era sperimentale (fuori da `forge.__all__`) in attesa di un caso reale.
Verificato: `bendly` (l'ex `unfold_generator`) lo usa già in produzione in
`io/dxf.py` per portare gli sviluppi che genera a `ForgeDocument` senza passare
da un file — il caso reale c'era da tempo, la nota non era mai stata aggiornata.
Federico, guardando avanti a Smoother (che lo userà per i contorni ricostruiti
da immagine): *"lo pubblichiamo, perché lo useranno di sicuro."*

Nessun cambio di comportamento: `load_geometry` entra in `forge.__all__`,
`docs/API.md` guadagna una sezione (schema `line`/`arc`/`circle`/`polyline`,
`role` opzionale), tolti i commenti "SPERIMENTALE" da `__init__.py` e dal
docstring del modulo.

### D33 — `simplify_points`: ricostruzione punti→primitive spostata in forge  ✅

Analisi di una sessione precedente (vedi sezione più sopra in questo file):
`classifica_punti()`/`scrivi_contorno()` di `smoother_5.py` non hanno nulla di
specifico alle immagini — prendono una sequenza di punti ordinata e chiusa,
rilevano gli spigoli per angolo e rifittano ogni tratto in linea o spline.
Federico ha confermato di chiudere l'analisi e ha posto una condizione precisa:
*"devono essere parametri gestibili dal chiamante"* — le due soglie
dell'originale (angolo di spigolo, cardinalità minima per una spline) erano
costanti hardcoded nello script.

`forge/tools/simplify_points.py`: `detect_corners()` (spigoli da soglia
angolare, parametro del chiamante) + `fit_primitives()` (spezza sui corner,
rifitta ogni tratto in `LineSeg` o `SplineSeg` di `core/primitives/segments.py`
via `ezdxf.math.BSpline.from_fit_points`, grado e soglia-punti-minimi
parametri) + `simplify_points()` che le incatena. Stesso trattamento
sperimentale di `load_geometry`/`load_pdf` prima di D32: importabile come
`forge.simplify_points`, fuori da `__all__` e non documentato finché non è
provato da un caso reale (Smoother).

Suite: 636 passed (+10 in `tests/unit/test_simplify_points.py`). Branch
`refactor/load-geometry-simplify-points`.

### D34 — `ForgeContour.depth` / `.parent`: l'albero di contenimento non si perde più  ✅

Sezione "NIPOTI STACCATI" più sopra in questo file: per piazzare le linguette
sui contorni annidati in profondità, uno strumento a valle (Smoother) deve
sapere non solo "sei annidato" ma "dentro quale contorno esattamente" — col
solo conteggio di profondità non si distinguono due fori fratelli con
un'isola ciascuno. Federico ha ragionato anche sul caso in cui si aggiunge
un contenitore esterno dopo (es. la lamiera attorno a un ingranaggio già
tracciato): non serve un'operazione di "reparent" — `_build_tree` ricalcola
il contenimento da zero per geometria a ogni `heal()`, quindi basta includere
il nuovo contorno esterno nello stesso batch di `load_geometry()` e outer/
figlio/nipote si aggiustano da soli. La disciplina che ne segue (non taggare
`role="outer"` su un contorno finché non sai se resterà la radice) è
responsabilità di chi chiama, non di forge.

`hierarchy.py` costruiva già l'albero vero (`_build_tree`/`_place`, padre →
figli → nipoti) e lo appiattiva deliberatamente in `_collect_inners()`,
perdendo chi-contiene-chi. Ora ogni `ForgeContour` porta `depth: int` (0
outer, 1 figlio, 2 nipote, ...) e `parent: Optional[ForgeContour]` (il
contorno che lo contiene direttamente), passati giù durante la stessa
ricorsione che già visitava l'albero — nessun ricalcolo. Additivo: `role`
resta con la stessa logica di ereditarietà di prima (D15), `cluster.inners`
resta piatto, nessun consumer esistente (`detect`, `io/dxf`, l'exporter
JSON/XML) tocca i due campi nuovi.

Suite: 639 passed (+3 in `tests/unit/core/test_hierarchy_builder.py`,
`TestNestingDepthAndParent` sulla stessa gerarchia a tre livelli di
`TestNestingFlattened`). Nessun golden toccato. Branch
`refactor/load-geometry-simplify-points`.

### D35 — `load_geometry` accetta anche `"spline"`  ✅

Migrando `smoother_5.py` nel nuovo repo `smoother`, il varco si è visto subito:
`forge.simplify_points()` produce anche `SplineSeg`, ma `GeometryAdapter`
sapeva tradurre in `Edge` solo `line`/`arc`/`circle`/`polyline` — una
`SplineSeg` non aveva modo di entrare in un `ForgeDocument`. Federico, a
domanda diretta, ha fissato il principio generale: *"tutti i loader alla fine
si devono assomigliare nelle entità. anche un load_pdf o un load_step, tutti
devono avere le entità necessarie per ottenere output compatibili nei formati
richiesti."* — ogni loader/adapter deve coprire l'intero vocabolario di
segmenti che `Edge` già supporta, non solo il sottoinsieme comodo per il suo
caso d'uso immediato.

`GeometryAdapter._spline_edge` — nuovo tipo `"spline"`:
`{"control_points", "knots", "degree", "weights"?, "fit_points"?, "closed"?,
"role"?}`, ricalcato 1:1 sui campi di `SplineSeg` così chi ha in mano l'output
di `simplify_points()` lo passa quasi senza toccarlo. Gli estremi vengono da
`segment_endpoints()` (già sapeva gestire `SplineSeg` via
`approx_points`/`fit_points`/`control_points` — nessun cambiamento lì).

Suite: 642 passed (+3 in `tests/unit/adapters/test_geometry_loader.py`, un
caso end-to-end che parte da un poligono a 16 lati, lo passa per
`simplify_points()` — nessuno spigolo rilevato, un'unica `SplineSeg` — e
verifica che `heal_and_detect` + `to_dxf` la riemettano come `SPLINE` nativa,
non discretizzata). Branch `refactor/load-geometry-spline`.

### D36 — `fit_primitives` accetta anche arco/cerchio (`arc_fit_tolerance`)  ✅

Completa il terzo caso già previsto in TODO.md fin dall'analisi che ha portato
a D33 ("ricostruzione di primitive pulite: linea/**arco**/spline") ma mai
implementato. Nato dal lavoro su `smoother`: un tratto curvo a raggio
~costante (un raccordo, un foro tracciato a mano) diventava sempre una
`SplineSeg`, anche quando un `ArcSeg` sarebbe più corretto — taglia meglio al
laser ed è banale da spezzare in due per una linguetta, a differenza di una
curva NURBS. Confermato che è lavoro di forge, non di smoother
(`smoother/MAP.md` D6): stessa ricostruzione geometrica generica di
`simplify_points`, non una decisione di processo/CAM.

`fit_primitives()`/`simplify_points()` guadagnano `arc_fit_tolerance:
Optional[float] = None`. **Default `None` = disattivato**, nessun cambio di
comportamento per chi non lo passa (i test esistenti, incluso quello di D35
sul poligono a 16 lati, restano verdi invariati). Quando impostato, ogni
tratto candidato-spline prova prima un fit a cerchio ai minimi quadrati
(metodo algebrico di Kasa, via `numpy.linalg.lstsq` — `numpy` era già
dipendenza di forge): se lo scostamento massimo dei punti dal cerchio fittato
è entro la tolleranza, il tratto diventa `CircleSeg` (se si richiude su se
stesso — il caso "contorno chiuso senza spigoli") o `ArcSeg` (tratto aperto
fra due corner veri, con gli angoli calcolati "srotolando" la sequenza reale
dei punti attorno al centro, non solo guardando primo/ultimo punto — altrimenti
un arco sopra i 180° si confonde con uno più corto nel verso sbagliato).
Altrimenti, fallback alla spline di sempre.

Suite: 646 passed (+4 in `tests/unit/test_simplify_points.py`: un cerchio
chiuso → `CircleSeg`, un quarto di cerchio aperto → `ArcSeg` con centro/
raggio/angoli corretti, una sinusoide non circolare → resta `SplineSeg` anche
con tolleranza impostata, e senza `arc_fit_tolerance` lo stesso cerchio resta
`SplineSeg` come prima). Branch `refactor/simplify-points-arc-fit`.

### D37 — `RoleStyle`: override esplicito colore/linetype/lineweight per ruolo  ✅

Nato da un caso concreto in `framer`: la cornice (ruolo consumatore `frame`,
D31) usciva sempre grigia (`COLOR_CONSUMER`, hardcoded in `rules/palette.py`)
e l'unico modo per renderla nera era manipolare l'entità DXF direttamente
dopo `to_dxf()` — un hack fuori dal modello, esattamente quello che forge
vuole evitare (`output-must-be-visually-faithful-to-source` e il principio
generale "il modello è il prodotto").

Il ruolo era già estendibile da un consumatore (`normalize_role`, `edge.role`
pre-`heal`); la palette no — `role_to_color()` ha un solo fallback fisso per
qualunque slug sconosciuto. Discusso con Federico: il ruolo va tenuto
estendibile allo stesso modo su TUTTI gli assi di stile (colore, linetype,
spessore), non solo il colore, e non solo per DXF — anche se oggi solo l'
adapter DXF li applica davvero.

Soluzione: `RoleStyle` (dataclass frozen in `rules/palette.py`, esportata in
`__all__`) — `color: Optional[RGB]`, `linetype: Optional[str]`,
`lineweight: Optional[float]` (mm), tutti opzionali. Il chiamante ne
assembla `Dict[str, RoleStyle]` una volta e lo passa a `to_dxf`/`split` via
`role_styles=` — stesso idioma di `label_map`/`linetype_map`, nessuno stato
globale mutabile. Deliberatamente **non** un oggetto "consumabile" con
metodi propri: in tutta l'API di forge non c'è un builder/registry stateful,
e non c'era motivo di introdurne uno qui.

Estendibilità per costruzione, esplicitamente per non ripetere il problema
che l'ha originato: aggiungere un futuro campo (fill, trasparenza, ...) non
tocca la firma di `to_dxf`/`split` né rompe chi già passa un `RoleStyle` con
meno campi — ogni adapter interpreta solo i campi che sa gestire.

Lato DXF (`io/dxf.py::_apply_role_styles`): l'override va sul **layer**, non
sull'entità — tutto ciò che forge scrive è BYLAYER, quindi si propaga a ogni
entità di quel ruolo. `color` → `layer.rgb` (true color, per un nero vero:
l'ACI a 256 colori non ne ha uno puro); `linetype` → registrato al volo da
`ezdxf.tools.standards` se è un nome standard, poi assegnato al layer;
`lineweight` → `layer.dxf.lineweight` in centesimi di mm. Un ruolo senza
layer ancora creato (uno slug di consumatore non ancora comparso) viene
creato al volo, stesso meccanismo di `_ensure_layer` già usato dal trash.

Rimane volutamente **fuori scope**: applicarlo a `to_svg`/un futuro `to_pdf`
(oggi solo `to_dxf`/`split` lo consumano; `RoleStyle` è già format-neutro,
un adapter in più legge lo stesso dizionario quando esisterà).

Suite: 656 passed (+10 in `tests/integration/test_role_style.py`). Branch
`refactor/role-style`.

### Questione aperta — dove vive la tassonomia hole/countersink/threaded/engrave/marking

Sollevata insieme a D37, non ancora decisa. `ContourRole.HOLE`,
`COUNTERSINK`, `THREADED_HOLE`, `ENGRAVE`, `MARKING` vivono in `model/role.py`
ma sono concettualmente il vocabolario che classifica `detect` (un tool), non
geometria neutra. Spostarli fuori da `model/` non è però un refactor
meccanico: `core/heal.py` e `core/healing/hierarchy.py` leggono
`STRUCTURAL_ROLES`/`is_structural_role` — che include proprio `HOLE`,
`COUNTERSINK`, `THREADED_HOLE` — per decidere la topologia, e `core` non può
dipendere da `tools/` (regola di dipendenza). Serve probabilmente un livello
di indirizione (es. un flag `structural: bool` sul ruolo stesso, non un
elenco fisso di costanti importato da `core`) prima di poter spostare quei
membri — un vero redesign, non da fare "a caldo" mentre si aggiunge altro
sopra. Federico: prevede che servirà comunque in futuro (un consumatore
avrà bisogno di questa separazione), ma non è la priorità di questo giro.

### D38 — Matematica di sequenze di punti spostata in `core/geometry.py`

`interior_angle_deg`, `detect_corners`, `drop_duplicate_points`,
`fit_circle_kasa`, `arc_angles` erano dentro `tools/simplify_points.py` (D33,
D36) — pura matematica su una sequenza di punti (x, y), zero dipendenza da
primitive forge o da come il chiamante la userà. Spostate in `core/geometry.py`
(che già ospita l'equivalente per segmenti/tracce: `track_points`,
`circular_geometry`, `are_collinear`). `tools/simplify_points.py` resta
l'orchestratore: importa queste funzioni da `core.geometry` e mantiene solo
ciò che è specifico della sua ricostruzione (`_split_into_stretches`,
`_try_fit_arc`, `_fit_spline`). `detect_corners` resta importabile da
`forge.tools.simplify_points` (re-export), zero rotture per chi già lo usa.
Nessun cambiamento di comportamento: 656 → stessa suite, verde.

**Correzione**: la motivazione originale di questa voce diceva che il secondo
consumatore che ha reso necessario lo spostamento fosse `tools/tabs.py`
(D39) — verificato dopo il fatto (Federico ha chiesto conferma), è falso:
`cut_tabs()` usa solo `_distance` (che era già in `core/geometry.py` **da
prima** di questa sessione, non fra le funzioni spostate qui) per sommare
distanze cumulate — non ha bisogno di `detect_corners`/`fit_circle_kasa`/
`arc_angles`. Lo spostamento resta comunque giustificato di per sé (stessa
famiglia di `track_points`/`circular_geometry`, non più annidato dentro un
solo tool), ma non era "provato" da un secondo consumatore reale come
scritto qui inizialmente — è preparatorio, non retroattivamente confermato.
Branch `refactor/point-sequence-math`.

### D39 — `forge.tools.tabs.cut_tabs`: taglio linguette come tool di forge (bozza)

Nato da un caso concreto: uno smoother-successor deve tagliare linguette
(ponticelli) su un contorno prima di fittarlo, così un anello concentrico
resta attaccato al resto della lamiera. Discusso a fondo con Federico se
dovesse vivere in un consumatore (smoother) o in forge:

- **Non deterministico come "ricostruire cosa c'è nel disegno"** — a
  differenza di `heal`/`detect`, crea un gap che nel disegno sorgente non
  c'era. Ma `heal` già modifica geometria (chiude micro-gap), e `tools/` esiste
  apposta per operazioni opzionali, deterministiche dato i parametri, che il
  chiamante compone — non fanno parte della ricostruzione fedele obbligatoria
  di `core`. La meccanica (taglia un gap di larghezza nota a una posizione
  nota) è deterministica data i parametri, esattamente come le soglie di
  `detect()`; il *dove/quante* resta una decisione di processo del chiamante,
  mai di forge.
- **Argomento decisivo, di packaging**: smoother dipende da opencv (extra
  `raster`, non nel core `pyproject.toml` di forge). Chi vuole *solo* le
  linguette su un DXF già pulito non deve installare una libreria di
  elaborazione immagini che non gli serve. forge ha zero dipendenza da
  opencv — vive lì.
- **Non nel contratto pubblico flat `forge.*`**: un utente che si aspetta
  `forge.*` sempre puramente ricostruttivo non deve incappare per caso in
  qualcosa che aggiunge geometria nuova. Stessa policy già in uso per
  `detect_corners`/`fit_primitives` prima di `simplify_points` (D33): resta
  raggiungibile solo come `forge.tools.tabs.cut_tabs`, mai flattato in cima,
  finché non è provato da un caso reale.

`cut_tabs(points, closed, tab_positions, tab_width)`: `tab_positions` sono
**indici** in `points` (non una lunghezza d'arco o una frazione 0-1) — scelta
di prima bozza, **non ancora una decisione definitiva**: se in futuro serve
una rappresentazione diversa, si cambia senza remore (nessuno usa ancora
questa funzione in produzione). `tab_width` è invece già una distanza reale
(lunghezza cumulata lungo il perimetro), non un numero di punti, perché la
densità dei punti non è affidabile. Ritorna gli stretch aperti risultanti,
pronti per `detect_corners(..., closed=False)` + `fit_primitives` (o
`simplify_points(..., closed=False, arc_fit_tolerance=...)`).

Verificato con uno script (`scripts/15_cut_tabs.py`): anello di 200 punti, 4
linguette da 2mm → 4 stretch aperti, ognuno rifittato a un `ArcSeg` pulito
(non una spline) grazie a `arc_fit_tolerance` — il caso reale per cui serviva.

Suite: 670 passed (+7 in `tests/unit/test_tabs.py`). Branch
`refactor/point-sequence-math` (stesso branch di D38: la matematica condivisa
e il suo primo consumatore vanno verificati insieme).

### D40 — `cut_tabs` cancellato, sostituito da `bridge_tabs`  ✅

`cut_tabs` (D39) tagliava un gap dentro UN contorno solo — nato dal caso
reale sbagliato: lo script 15/16 lo applicava all'anello r=9 legato al
rettangolo esterno, ma il bisogno vero su quel fixture
(`cerchi_concentrici_detect_is_counter_tabs_join.dxf`) è tenere il nipote
(cerchio interno r≈4.12) attaccato al suo genitore diretto (anello r=9) — un
ponte fra DUE contorni distinti, non un gap in uno solo. Verificato che
`cut_tabs` non risolve questo: cancellati `cut_tabs`, `tests/unit/test_tabs.py`,
`scripts/15_cut_tabs.py`, `scripts/16_cut_tabs_on_fixture.py` — nessun
compat shim, la funzione non aveva un secondo uso reale indipendente.

Disegno di `bridge_tabs` (da implementare):

- **Generalizza a profondità arbitraria, a coppie**: ogni isola (profondità
  pari — nipote, pro-pronipote, ...) si lega al vuoto immediatamente sopra di
  lei nella gerarchia (il suo genitore diretto — figlio, pronipote, ...), mai
  a un livello saltato. Serve `ForgeContour.depth`/`.parent` (D34) — un
  wrapper cammina la gerarchia e chiama `bridge_tabs` per ogni coppia
  isola↔genitore-diretto trovata, a qualunque profondità.
- **Costruzione geometrica**: linea ideale fra un punto sul figlio e il punto
  corrispondente sul genitore → offset di `±tab_width/2` (perpendicolare) →
  due linee reali, i fianchi della linguetta → intersezione di ciascuna con
  ENTRAMBI i contorni (genitore e figlio) → due nuovi `LineSeg` (dall'incrocio
  sul figlio a quello sul genitore) + rimozione del tratto/arco che cade in
  mezzo su entrambi i contorni. `tab_width` è quindi una distanza reale
  (offset perpendicolare), non una lunghezza d'arco come in `cut_tabs` —
  necessario perché genitore e figlio hanno raggi/geometrie diverse, la
  stessa larghezza fisica dà lunghezze d'arco diverse sui due.
- **Math di core riusata, non duplicata**: l'intersezione retta-cerchio è già
  `_circle_line_intersections` in `core/geometry.py`, la stessa usata da
  `core/healing/gap_solver.py`. Nessuna nuova math per il caso cerchio-cerchio.
- **Scope**: genitore/figlio possono essere linea, arco, polilinea o cerchio —
  **non spline**, per ora (nessuna intersezione retta-spline in core).
  Generalizzare oltre richiede una nuova funzione di core, rimandata finché
  non serve davvero.
- **Nome**: modulo `forge/tools/tabs.py` invariato (tiene il dominio
  "linguette"); funzione `bridge_tabs` (verbo+dominio, stesso pattern di
  `cut_tabs`) — non `bridge()` da solo, troppo generico per una funzione
  pubblica di tool.

**Implementato.** `bridge_tabs(parent_points, child_points, anchor_parent,
anchor_child, tab_width)` — una coppia, una posizione, ritorna i 2 fianchi
(`LineSeg`) e i 4 punti di taglio (con indice di lato, per chi deve spezzare
il contorno). `bridge_nested_tabs(cluster, tab_width, tab_count, ...)` cammina
`cluster.inners` (che porta `depth`/`parent`, D34), trova ogni profondità pari
>= 2, e per ciascuna piazza `tab_count` linguette equispaziate (raggio dal
centroide dell'isola, intersecato coi due contorni via la nuova
`core.geometry.polyline_line_intersections` — generalizza
`_circle_line_intersections` a qualunque punto già discretizzato, non solo
cerchi analitici). Split multi-linguetta sullo stesso contorno: tutti i tagli
di tutte le linguette della coppia si calcolano prima sul contorno originale
intatto, poi UN solo passo li ordina per posizione cumulata e tiene solo gli
archi fra linguette diverse (quello sotto la stessa linguetta si scarta) —
evita il problema di ritagliare uno stretch già aperto linguetta per linguetta.

**Trovato facendo il lavoro, corregge il disegno sopra**: l'override
`forced_corners` in `detect_corners` non serve — `fit_primitives(points,
is_corner, ...)` prende `is_corner` già come parametro esterno, quindi un
domani un chiamante che vuole forzare uno spigolo può calcolare
`detect_corners()` e mettere `True` a mano sugli indici che vuole, senza
nessuna modifica a `core/geometry.py`. E nell'architettura scelta qui il
problema non si presenta nemmeno: ogni stretch rifittato (`child_stretches`/
`parent_stretches`) contiene SOLO punti del contorno originale, mai i punti
dei fianchi — i fianchi sono `LineSeg` già tipizzati, mai passati per
`simplify_points`. Verificato sul fixture reale: le 8 arcate (4+4) rifittano
tutte pulite a `ArcSeg`, zero `SplineSeg` spuri, senza bisogno di forzare nulla.

**Limite noto, non risolto**: due contorni fratelli con lo stesso genitore
diretto (es. due isole distinte dentro lo stesso vuoto) verrebbero tagliati
indipendentemente sullo stesso `parent_points`, senza sapere l'uno dell'altro
— i tagli si sovrapporrebbero. Non è il caso del fixture attuale (una sola
catena lineare); da risolvere se/quando serve davvero.

Test: `tests/unit/test_tabs.py` (5 test — `bridge_tabs` sintetico a due
cerchi, `bridge_nested_tabs` sul fixture reale e su una catena sintetica a 4
livelli che verifica l'accoppiamento nipote↔figlio / pro-pronipote↔pronipote,
mai un livello saltato). Script `scripts/16_bridge_tabs_on_fixture.py`
(stesso numero del vecchio `cut_tabs`, libero dopo la cancellazione) — DXF
prodotto ispezionato visivamente (renderizzato a PNG): 4 archi esterni + 4
archi interni + 8 fianchi radiali, esattamente la "girandola a 4 razze"
attesa. Suite: 668 passed. Branch `refactor/point-sequence-math`.

### D41 — `_fit_spline`: mai `fit_points`, `closed=True` quando il tratto è l'intero loop  ✅

Scoperto da Smoother (`smoother/MAP.md` D15): una SPLINE scritta da
`to_dxf()` per un contorno chiuso senza spigoli non veniva letta da alcuni
software CAM a valle (letto: SigmaNest — non un caso isolato, era già
capitato prima con lo stesso software su un altro progetto). Confrontati due
DXF con `forge.inspect_dxf()` — uno prodotto da un vecchio script locale
(letto correttamente da SigmaNest), uno dalla pipeline attuale (non letto):
la differenza non era la geometria ma due campi del gruppo SPLINE:

- `flags` — sempre `0` (aperta) nel file non letto, anche per contorni
  interamente chiusi senza un solo spigolo; `1` (chiusa) in quello che
  funziona.
- `fit_points` — sempre presenti (stesso conteggio dei control points) nel
  file non letto; assenti (`0`) in quello che funziona.

Entrambe risalivano a `_fit_spline()`: non passava mai `closed=` al
`SplineSeg` che costruiva, e scriveva sempre `fit_points=pts_3d` insieme a
control points + nodi. Per spec DXF le due definizioni (control
points/nodi, oppure fit points) sono alternative, non cumulative — con
entrambe presenti alcuni lettori provano a ricostruire la curva dai fit
points con una logica propria invece di usare quella già data, e quella
logica evidentemente non regge sempre.

**Fix**: `_fit_spline()` non scrive più `fit_points` (control points + nodi
bastano a definire la curva per intero — non è una perdita di precisione,
solo di un metadato opzionale per un editor che volesse mostrare "maniglie"
sui punti originali). Guadagna un parametro `closed`, passato da
`fit_primitives()`: vale `True` solo quando l'intero contorno chiuso è
diventato un solo tratto (`closed and len(stretches) == 1` — l'unico caso in
cui, per costruzione di `_split_into_stretches`, quel singolo tratto *è*
il loop intero, non un arco fra due spigoli).

Verificato end-to-end, non solo sull'unità: ricostruita a mano la stessa
struttura (`closed=True`, niente `fit_points`) su una spline della pipeline
prima del fix — il DXF risultante aveva `flags=1`/`fit_points=0`, identico
al file che SigmaNest legge. Dopo il fix applicato a monte, la pipeline
reale (Smoother, immagine con ~140 contorni) produce lo stesso pattern su
ogni spline, senza alcun intervento manuale. Suite: 668 passed, nessuna
regressione.

---

### D42 — `SplineSeg.discretize()` valutava il poligono di controllo, non la curva  ✅

Scoperto da Smoother: l'anteprima SVG (e l'export a polilinea, D15, che usa
lo stesso `.discretize()`) di una spline con pochi punti di controllo per
tratto lungo (sottocampionamento alto o soglia spigolo bassa, MAP.md D19)
appariva visibilmente "a facce"/seghettata anche quando la spline nel DXF
era corretta e morbida. Causa: `discretize()` era un placeholder mai
finito (commento esplicito nel codice, "FASE 3: implementare valutazione
BSpline corretta con controllo della tolleranza. Per ora usiamo
interpolazione lineare tra i punti di controllo come approssimazione") —
non valutava mai la curva vera, solo il segmento dritto fra un punto di
controllo e il successivo. Con pochi punti di controllo su un tratto molto
curvo, quei segmenti dritti si vedevano.

**Fix**: `discretize()` ora valuta la curva vera con l'algoritmo di de Boor
(`_evaluate()`, "The NURBS Book" Algoritmo A5.1, razionale se `weights` è
impostato) e suddivide adattivamente ogni intervallo di parametro finché il
punto medio resta entro `tolerance` dalla corda (`_refine()`), con un tetto
sul totale dei punti (`MAX_SEGMENTS_SPLINE * 4`) per non esplodere su un
tratto rumoroso che non converge. Sola matematica (solo `math`, nessuna
libreria di formato): `core/` deve funzionare anche senza `ezdxf`
installato, non è negoziabile — un primo tentativo che riusava
`ezdxf.math.BSpline` per la valutazione è stato scartato per questo,
non per motivi tecnici.

Verificato numericamente, non solo a occhio: una spline con soli 8 punti di
controllo su un semicerchio raggio 10 — la vecchia logica (poligono di
controllo) devia dalla curva vera fino a 0.79 unità (quasi l'8% del
raggio); la nuova, con `tolerance=0.05`, devia al massimo 0.011 unità.
Suite: 668 passed, nessuna regressione.

---

### D43 — `interpret_annotations` → `anchor_annotations`  ✅

Rinominata (`forge/tools/interpret.py` → `forge/tools/anchor.py`, e nell'API
pubblica `forge.interpret_annotations` → `forge.anchor_annotations`). Nata da
una sessione di confronto con Federico (con ChatGPT/Gemini/Deepseek come
pareri esterni, `PARERI_VARI.md`) su determinismo e confini di forge: la
parola "interpret" era già usata per tre cose diverse — questa funzione
(solo geometria: `cluster_ref` per contenimento), il futuro progetto
interprete (`INTERPRETER.md`), e il concetto generico di interpretazione
discusso a proposito di D39-D42 — e Federico l'ha segnalato come fonte reale
di confusione, non solo fastidio estetico.

**Resta in forge**: non è un problema di "dove vive", solo di nome. La
funzione è pura ricostruzione geometrica (un punto dentro un poligono, con
uno snap opzionale) — zero giudizio su cosa significhi un'annotazione per il
disegno, quindi non ha nulla del lavoro che sta spostandosi verso framer
(cornice/cartiglio/viste/callout, vedi discussione in `INTERPRETER.md`, da
riscrivere). Il nome nuovo riusa la parola già in uso nella documentazione
per descriverla ("annotazioni tipate e **ancorate**",
`forge-neutral-substrate-agent-layer-above`) invece di introdurne una terza.

Nessun compat shim (`refactor-clean-break-over-compat-shims`): rinominata
ovunque — modulo, test (`tests/unit/test_interpret_annotations.py` →
`test_anchor_annotations.py`), golden generator, `docs/API.md`,
`docs/ARCHITECTURE.md`. Non toccata la voce storica sopra (era
`interpret_annotations` quando fu decisa, resta così nel log).

---

## QUESTIONI CHIUSE (storico)

- **Q1 — classificazione hole: topologia o detection?** → risolta da D15
  (detection, `detect()` parametrico). L'ipotesi scartata era tenerla in
  `heal` / `hierarchy`: avrebbe impegnato `heal` sulla semantica hole/inner,
  rendendolo non più saltabile, contro
  `laser-cutting-default-cam-enrichment-optional`.
- **Q2 — valore di `HOLE_DIAMETER_THRESHOLD`** → risolta da D15. `32.1` mm è ora
  il **default** di `detect(max_drill_diameter=...)`, non una costante di
  dominio. Federico: lascia `32.1` per ora ("ragiono sui fori che magari hanno
  tolleranza e devono essere ripassati"). La costante resta in
  `rules/thresholds.py` come sorgente del default; il chiamante la può override
  per macchina/utensile.



* Appunti Federico
** API
inspect_file: se non gli passo il dxf, ma un altro fiel in entrata?? ce ne freghaimo ora, dal momento che non abbiamo altri input?

> **Risposta:** sì, ce ne freghiamo per ora, ed è già coerente col resto del
> codice, non solo pigrizia. `inspect_file`/`inspect_dxf` (livello 1) sono
> hardcoded su DXF (`ezdxf.readfile`, `load_dxf`) — oggi l'unico adapter di
> formato che forge ha davvero. `inspect_document` (livello 2) invece prende
> già un `ForgeDocument` generico, quindi funziona anche per geometria
> arrivata da `load_geometry()` (il percorso che usa bendly, zero DXF) — basta
> non passargli un path DXF ma il documento già costruito. Solo il livello 1 e
> l'orchestratore restano da generalizzare, e solo quando esisterà un secondo
> adapter di formato vero (SVG/PDF, vedi sotto in TODO.md) — non prima.

in ispect_dxf, sarebbe meglio avere l'opzione di non printare entità, ome avevamo prima. voglio dire, se hno boisogno solo dela spline o della polilinea, mi devo beccare anche tutto il resto?

> **Risposta:** hai ragione, oggi manca. `inspect_dxf(path, entities=True,
> limit=40)` ha solo un interruttore tutto/niente (`entities=False` toglie
> il dettaglio entità del tutto) — nessun modo di dire "solo SPLINE" o "solo
> LWPOLYLINE". Piccola aggiunta pulita: un parametro tipo `types:
> Optional[set[str]] = None` che filtra il loop di stampa
> (`if types and t not in types: continue`), stesso pattern di `limit`. Non
> l'ho fatta senza dirtelo — dimmi se la vuoi ora o la metto in coda in
> TODO.md.

load_dxf: se non faccio poi detection all, la tracciatura dei layer non serve a niente, vero?

> **Risposta: no, non è vero — verificato nel codice, non è un'impressione.**
> `label_map`/`linetype_map`/`color_map` scrivono `edge.role` **al momento del
> load**, prima che `heal()` esista anche solo come chiamata. `heal()` stesso
> (non `detect()`) usa quei ruoli in `_split_labeled()`
> (`core/heal.py`): ogni edge con un ruolo noto e non strutturale
> (`is_structural_role`) viene tirato fuori dal grafo di topologia prima di
> cercare i loop — è così che linguette/incisioni/cornice non spezzano la
> ricerca di outer/inner. Quindi la tracciatura dei layer conta già dentro
> `heal()` da solo, senza mai chiamare `detect()`: cambia la topologia
> risultante (quali edge finiscono nel grafo strutturale) e dove finisce la
> geometria in output (`to_dxf` instrada per ruolo). `detect()` aggiunge sopra
> solo la seconda lane — classificazione *geometrica* (senza layer) di quello
> che il label_map non ha già deciso.




** MODULI
