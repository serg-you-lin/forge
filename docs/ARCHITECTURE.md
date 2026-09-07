# forge — architettura

Questo documento spiega *come è fatto dentro* e *perché*. Per l'uso pratico
dell'API vedi [`API.md`](API.md).

---

## L'idea in una frase

`forge` non è una libreria DXF. È un **motore di ricostruzione topologica** con
un adapter DXF davanti. Prende geometria 2D rumorosa e produce un modello di
fabbricazione consistente: contorni chiusi, gerarchia, feature.

Il DXF è solo il primo formato di ingresso implementato. Il core non sa cosa sia
un DXF, né cosa sia un arco o una spline in quanto entità di CAD — lavora su
primitive geometriche pure.

---

## Il principio: il prodotto è il modello

```
                    ┌─────────────────┐
   DXF / DWG  ──────►                 ├──────►  DXF (to_dxf, split)
   PDF (sperim.) ───►   ForgeResult   ├──────►  JSON / XML (save_json, save_xml)
   SVG (futuro) ─────►   il modello   ├──────►  view model JSON (to_view_model)
                    │                 ├──────►  SVG (to_svg, save_svg)
                    └─────────────────┘
```

Il `ForgeResult` è **il prodotto**. Tutti i `to_*` sono renderer del modello.
`to_dxf` **non rilegge mai il file sorgente** — disegna dal modello. Questo è il
motivo per cui `to_svg` produce la stessa identica immagine senza una riga di
codice nuova nel core.

Conseguenza pratica: **niente si perde**. Si importa tutto — quote, centerline, spazzatura. 
Perché `forge` non perda
niente, il modello è abbastanza ricco da tenere anche ciò che non ha classificato:

- geometria di taglio classificata → parti / fori / feature
- geometria non classificata → `result.trash_entities` (segmenti puri,
  formato-indipendenti — ogni loader li alimenta, ogni renderer sceglie se
  disegnarli)
- testi e quote → `result.annotations` (oggetti di dominio, con sia il valore
  semantico sia la forma renderizzata come primitive)

I tipi di entità che `forge` non modella (`HATCH`, `IMAGE`, `TABLE`, `3DFACE`,
`XLINE`…) restano fuori, ma `load_dxf` emette un warning che li elenca — nessuna
perdita silenziosa.

---

## La struttura

```
forge/
├── adapters/     TRADUZIONE formato → primitive       (conosce ezdxf)
│   ├── dxf/          load_dxf, DxfAdapter, exporter, annotation_extractor, layers
│   ├── pdf/          load_pdf — sperimentale, congelato
│   └── geometry/     load_geometry — sperimentale (geometria pura, non un file)
│
├── core/         MOTORE geometrico puro               (zero ezdxf, zero formato)
│   ├── primitives/   LineSeg, ArcSeg, SplineSeg, CircleSeg + discretizzazione
│   ├── topology/     edge.py, grafo dei nodi, ricerca loop, detection pieghe
│   ├── healing/      chiusura gap, normalizzazione, gerarchia
│   ├── classification/  classificazione fori (filettati, svasature)
│   └── heal.py       HealStep + heal() — l'atto del motore: file → modello
│
├── model/        IL DOMINIO forge                     (dataclass pure + shapely)
│   ├── document.py   ForgeDocument
│   ├── result.py     ForgeResult
│   ├── cluster.py    ForgeCluster, ForgeContour
│   ├── feature.py    Feature → ClosedFeature / OpenFeature
│   ├── hole.py / engraving.py / bending_line.py / classified.py
│   └── annotation.py Annotation → Note / Dimension / Leader
│
├── tools/        STADI opzionali su un ForgeResult    (il caller sceglie quali e in che ordine)
│   ├── detect.py     detect()                — classifica le feature nei cluster
│   ├── interpret.py  interpret_annotations() — àncora le annotazioni ai cluster
│   └── inject.py     inject()                — testi del cluster → data_injector esterno
│
├── io/           RENDERER del modello + serializzazione
│   ├── dxf.py        to_dxf(), split()       (ex pipeline/write.py)
│   ├── svg.py        to_svg(), save_svg()
│   ├── view_model.py to_view_model()
│   └── exporter.py   save_json / save_xml / XDATA
│
├── rules/        REGOLE di dominio                     (soglie, palette, schema, validazione)
├── recipes.py    heal_and_detect(), split_to_files()  — la via del 90%
└── inspect.py    strumento di ispezione a 3 livelli
```

`pipeline/` non esiste più (MAP.md D22): metteva insieme tre cose diverse —
`heal` (l'atto del motore, ora in `core/`), gli stadi opzionali (`tools/`) e i
renderer (`to_dxf`/`split`, ora in `io/` accanto a `to_svg`/`to_json`).

**Regola di dipendenza:** `core` e `model` non importano mai `adapters`. Gli
`adapters`, `tools` e `io` importano `core` / `model` / `rules`. `recipes`
mette in fila `core.heal` + `tools` + `io`. Il core non sa da dove viene la
geometria.

---

## Il flusso, passo per passo

### 1. `load_dxf` → `ForgeDocument`

Unico punto che legge `ezdxf`. In ordine:

1. se `.dwg` → conversione via ODA File Converter
2. `readfile`
3. `audit` (le annotazioni vengono estratte **prima**: l'auditor di ezdxf
   cancella le quote che referenziano un blocco geometria mancante)
4. upgrade a R2010 se il file è legacy (R12/R13/R14)
5. explode degli `INSERT` (default `True` — un blocco non esploso fa sparire la
   sua geometria)
6. sanitize: normalizzazione OCS, appiattimento Z ≠ 0, deduplica
7. traduzione: ogni entità → uno o più `Edge`; ogni testo/quota → un `Annotation`

Dopo questa funzione l'oggetto `ezdxf` sorgente **sparisce**. Tutto il resto
lavora sul `ForgeDocument`.

### 2. `heal` → `ForgeResult` (topologia)

Il passo difficile. Lavora su `doc.edges`, zero `ezdxf`. In ordine:

1. **estrae** gli `Edge` con ruolo non strutturale (`engrave`, `marking`, decisi
   da `label_map`): non entrano nel grafo, sono geometria di marcatura, non
   contorno
2. **preprocess**: costruisce il grafo dei nodi, trova gli endpoint liberi entro
   `tolerance`, chiude i gap prolungando i segmenti alla loro intersezione reale
3. **detection pieghe candidate**: gli `Edge` con entrambi gli endpoint su nodi di
   branching (grado > 2) sono candidati piega — escono dal grafo per non rompere
   la ricerca dei loop
4. **ricerca loop**, con una scala di strategie sempre meno esatte:
   - grafo esatto (uguaglianza delle tuple arrotondate)
   - se fallisce: clustering degli endpoint entro `tolerance` per trovare gli
     angoli "quasi chiusi", poi chiusura vera all'intersezione
   - se fallisce: loop sul grafo clusterizzato tollerante (con warning: la
     discrepanza sopravvive nell'output)
   - ultima spiaggia: `shapely.polygonize` sui segmenti discretizzati
5. **costruzione gerarchia**: quale loop contiene quale → albero di contenimento
   `outer` / `inner`. `heal` si ferma qui: **non** decide hole vs inner (D15) —
   ogni loop contenuto è un `ForgeContour` in `cluster.inners`.

Se non si forma **nessun** contorno esterno chiuso, il risultato è dichiarato
**non valido** (`is_valid = False`) — come il modelspace vuoto. `to_dxf` si
rifiuterà di generare un file di sola spazzatura.

`validate_result` viene chiamata automaticamente alla fine.

### 3. `detect` (semantica)

Classifica le feature dentro le parti. **Muta il `result` in-place e lo ritorna.**
`heal_and_detect(doc)` fa il passo 2 e il passo 3 insieme (con `features="all"`);
restano separati perché un renderer o un nesting tool possono volere la sola
topologia.

`detect(result)` nudo fa solo la lane `label_map` + pulizia topologia. Le lane
geometriche sono opt-in: `detect(result, "holes" | "bending" | "engrave" | "all")`.

- **fori** (`features="holes"`) → un contorno interno circolare con Ø `<
  max_drill_diameter` (parametro di processo, default 32.1 mm) viene promosso a
  `Hole`; sopra soglia resta `ForgeContour`. Tipo: `plain` / `countersink`
  (cerchio piccolo concentrico dentro cerchio grande) / `threaded` (arco a ~270°
  concentrico, raggio di poco maggiore, rapporto ≤ 1.6).
- **pieghe** → una traccia da bordo a bordo dell'outer, con il punto medio dentro
  il poligono, è una `BendingLine` con il suo angolo.
- **incisioni** → le tracce con ruolo `engrave` finiscono in `cluster.engrave_lines`
  se contenute in una parte, altrimenti restano in trash.

### 4. render — `to_dxf` / `split`

Costruiscono un documento `ezdxf` **nuovo** (mai il sorgente) e ci scrivono i
segmenti puri del modello, ognuno sul suo layer forge (vedi tabella in
[`API.md`](API.md#output-dxf-layers) e nel README). Regole di fedeltà:

- **le spline** si riemettono come `SPLINE` native, ricostruite da control points
  / knots / weights / degree / tangenti — **mai discretizzate a polilinea**
- **le incisioni** si emettono come N entità native (`LINE`/`ARC`/`SPLINE`/
  `CIRCLE`), **mai come `LWPOLYLINE`** — un'incisione è N segmenti separati
- **il trash** si materializza sempre sul layer `Trash`
- **le annotazioni** si riscrivono tutte; in `split` ognuna va nel file della
  parte che la contiene (o della più vicina)

### 5. export / inject

`save_json` / `save_xml` scrivono i metadati per parte secondo lo schema
(`rules/metadata_schema.py`). I conteggi delle feature (fori per tipo, pieghe,
incisioni) vengono da `cluster.summary` — una property derivata dal modello.
`inject` serve solo a passare i testi dentro l'outer a un `data_injector`
esterno che restituisce codice / materiale / spessore, e a metterli in
`cluster.custom`.

---

## Due concetti che tornano ovunque

### La tolleranza

`tolerance` (default 0.05, i golden usano 0.5) è la distanza sotto la quale due
punti sono "lo stesso nodo". Serve in due modi:

1. **arrotondamento**: ogni endpoint viene quantizzato su una griglia di lato
   `tolerance` prima di entrare nel grafo
2. **chiusura gap**: due endpoint liberi entro `tolerance` vengono congiunti
   prolungando i segmenti

Un gap 4× la tolleranza **non** viene chiuso — è una scelta, non un bug: se il
file ha buchi grossi, o sono voluti o l'unità di misura è sbagliata. Workaround:
alza `tolerance`.

### Il doppio binario delle feature (label_map / inferenza)

Ogni feature manifatturiera è raggiungibile per **due strade**:

- **`label_map`**: l'utente dice "il layer `Piega` sono pieghe". Il ruolo è
  assegnato al load, è **autoritativo**, a valle non si rimette in discussione
  (`source="labeled"`, `confidence=1.0`). Stessa autorità, stesso load, per
  `linetype_map`/`color_map` (`{"DASHED": "bending"}`, `{"cyan": "engrave"}`,
  Cluster E): quando il disegno porta l'intenzione nello stile della linea
  invece che nel layer, sono la stessa lane con un altro segnale in ingresso —
  si applicano solo dove `label_map` non ha già deciso dal layer. Il linetype
  e il colore confrontati sono quelli **effettivi**: un'entità `ByLayer`
  eredita lo stile dal layer che la contiene, e `DxfAdapter` lo risolve prima
  del confronto — altrimenti ogni entità che eredita lo stile dal layer (il
  caso comune) sfuggirebbe silenziosamente a entrambe le lane.
- **inferenza geometrica**: `forge` riconosce la feature dalla forma
  (`source="geometric"`, `confidence < 1.0`).

`Hole` è l'implementazione di riferimento (ha `hole_type` + `geometric_hint` +
`source` + `confidence`). `Engraving` lo segue. Il design resta aperto al binario
dell'inferenza anche dove non è ancora implementato — es. `detect._detect_engrave`
è un placeholder con già il parametro `engrave_tolerance` e il posto in
`detect()`.

---

## Cosa NON è (ancora) pulito

Onestà sullo stato — dettagli e decisioni prese in `MAP.md` (sezione "Decisioni
chiuse"):

- **`load_pdf`** ritorna `list[Edge]` invece di un `ForgeDocument` → non si
  aggancia a `heal()`. Congelato (D10).
- **`detect._detect_engrave`** è ancora un placeholder no-op (D13).

Già risolto in Fase 4: `bridge/shape.py` (`OpenShape`/`ClosedShape`) eliminato,
`heal` produce direttamente `OpenFeature`/`ClosedFeature` (D4); traduttore
entità→primitiva ora unico (`DxfEntityDispatcher`, D7); `parse_loop` →
`segments_from_loop` in `core/topology/` (D6); `source`/`confidence` su
`BendingLine` (D5); conteggi feature spostati da `inject`→`cluster.custom` a
`cluster.summary` derivato (D8); classificazione hole/inner e soglia
`max_drill_diameter` spostate da `hierarchy` a `detect()` parametrico (D15) —
`heal` ora emette solo l'albero di contenimento.

**D19 — `adapters/bridge/` eliminato, `Edge` spostato in `core/topology/edge.py`:**
`bridge/` era rimasta con un solo file dopo l'eliminazione di `shape.py` (D4) —
smell segnalato da Federico. Più a fondo: `Edge` viveva sotto `adapters/` ma
`core/topology/graph.py`, `loop_finder.py`, `bending_detector.py`,
`core/healing/gap_solver.py` e `core/adapter_base.py` lo importavano tutti da
lì — **`core` dipendeva da `adapters`**, il contrario esatto della regola di
dipendenza sopra. `Edge` non è una primitiva (quelle sono math puro in
`core/primitives/segments.py`): è un wrapper topologico con ruolo/stile/
provenienza attorno a una primitiva — appartiene a `core/topology/`, dove
vivono i suoi consumatori veri. Spostato lì; gli adapter (DXF, PDF) ora lo
importano da `core`, come da regola.
