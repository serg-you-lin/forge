# forge — architettura

Questo documento spiega *come è fatto dentro* e *perché*. Per l'uso pratico
dell'API vedi [`API.md`](API.md).

---

## L'idea in una frase

`forge` non è una libreria DXF. È un **motore di ricostruzione topologica** con
un adapter DXF davanti. Prende geometria 2D rumorosa e produce un modello
geometrico consistente e senza perdite: contorni chiusi, gerarchia di
contenimento, annotazioni, e un overlay aperto per le feature rilevate. Non sa
cosa sia la lamiera né alcun processo: leggere un contorno come "foro" o una linea
come "piega" è un'interpretazione, e sta nei consumatori (`snapbend` per fori,
pieghe e incisioni; `snapdraw` per la notazione del disegno — MAP.md D88).

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
                    │                 ├──────►  testo per un agente AI (to_text, sperim.)
                    └─────────────────┘
```

Il `ForgeResult` è **il prodotto**. Tutti i `to_*` sono renderer del modello.
`to_dxf` **non rilegge mai il file sorgente** — disegna dal modello. Questo è il
motivo per cui `to_svg` produce la stessa identica immagine senza una riga di
codice nuova nel core.

Conseguenza pratica: **niente si perde**. Si importa tutto — quote, centerline, spazzatura. 
Perché `forge` non perda
niente, il modello è abbastanza ricco da tenere anche ciò che non ha classificato:

- geometria chiusa ricostruita → parti / contorni interni / feature (se una lettura le aggiunge)
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
│   ├── primitives/   LineSeg, ArcSeg, SplineSeg, CircleSeg, EllipseSeg + discretizzazione;
│   │                 fitting.py: primitive da una sequenza di punti (simplify_points)
│   ├── topology/     edge.py, grafo dei nodi, ricerca loop, detection pieghe;
│   │                 noding.py (rete piana), outer_face.py (faccia esterna)
│   ├── healing/      chiusura gap, normalizzazione (+ tassellature), gerarchia,
│   │                 islands.py (isole per vicinanza), steps.py (i passi di heal)
│   ├── heal.py       heal()             — lettura dall'interno: file → modello
│   └── island.py     island()           — lettura per isole, dall'esterno
│
├── model/        IL DOMINIO forge                     (dataclass pure + shapely)
│   ├── document.py   ForgeDocument
│   ├── result.py     ForgeResult
│   ├── cluster.py    ForgeCluster — il contenitore, `detected` è l'overlay
│   │                 di un consumatore (vocabolario aperto per nome — D44)
│   ├── detected.py   DetectedFeatures — il contenitore dell'overlay (D44, D90)
│   ├── feature.py    Feature → ClosedFeature / OpenFeature
│   ├── contour.py
│   ├── annotation.py Annotation → Note / Dimension / Leader
│   └── role.py       ContourRole = solo UNKNOWN/OUTER/INNER — il minimo
│                      che il motore usa. Nessun ruolo manifatturiero qui
│                      (D47, "roles out of core")
│
├── tools/        STADI opzionali su un ForgeDocument/ForgeResult (il caller sceglie quali e in che ordine)
│   ├── anchor.py         anchor_annotations()   — àncora le annotazioni ai cluster
│   ├── inject.py         inject()                — testi del cluster → data_injector esterno
│   ├── non_contour.py    non_contour_candidates() — stesso criterio non-contorno
│   │                     di heal() (D49), esposto per decidere `edge.role`
│   │                     PRIMA di heal() (D55) — lavora su ForgeDocument
│   ├── rotate.py         rotate_*() (sperimentale, D46)
│   └── tabs.py           bridge_tabs() (D40)
│
├── io/           RENDERER del modello + serializzazione
│   ├── dxf.py        to_dxf(), split()       (ex pipeline/write.py)
│   ├── svg.py        to_svg(), save_svg()
│   ├── view_model.py to_view_model()
│   ├── text.py       to_text(), save_text()  (sperimentale, D84)
│   └── exporter.py   save_json / save_xml / XDATA
│
├── rules/        REGOLE di dominio                     (palette, schema, validazione)
├── recipes.py    split_to_files()  — heal + split + salvataggio
└── inspect.py    strumento di ispezione a 3 livelli
```

`pipeline/` non esiste più (MAP.md D22): metteva insieme tre cose diverse —
`heal` (ora in `core/`), gli stadi opzionali (`tools/`) e i renderer
(`to_dxf`/`split`, ora in `io/` accanto a `to_svg`/`to_json`). D22 diceva anche
che `heal` è "l'atto unico del motore": non è più vero (D58) — il motore ha due
letture, `heal()` e `island()`, che compongono gli stessi ingredienti del core
in modo diverso e riempiono lo stesso modello. Il prodotto è il modello, non
una delle due ricette.

**Regola di dipendenza:** `core` e `model` non importano mai `adapters` **né
`tools`** (D44 — stesso principio, `tools` è un pacchetto pari-grado di
`adapters`/`io`, mai sotto `model`). `adapters`, `tools` e `io` importano
`core` / `model` / `rules`. Quando `model/` deve comunque annotare un tipo che
vive in `tools/` (es. `ForgeCluster.detected`), lo fa solo sotto
`TYPE_CHECKING` — zero import a runtime, `from __future__ import annotations`
rende l'annotazione una stringa pigra. `recipes` mette in fila `core.heal` +
`tools` + `io`. Il core non sa da dove viene la geometria.

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

Il passo difficile. Lavora su `doc.edges`, zero `ezdxf`. `heal()` è una
ricetta: ogni passo è una funzione pubblica in `core/healing/steps.py` (D62),
`heal()` le compone in quest'ordine e scrive i warning che le raccontano. Un
consumatore (snapdraw) compone gli stessi passi come gli serve.

1. **normalizza** (`merge_collinear_overlaps`, `merge_cocircular_overlaps`,
   `weld_degenerate_linesegs`): rette e archi tracciati a spezzoni fusi,
   `LineSeg` sotto 0.05 mm saldati in un nodo (D50, D52, D56)
2. **estrae** (`split_labeled`) gli `Edge` con ruolo deciso e non strutturale
   (`engrave`, `marking`, `bending` da `role_rules`, o uno slug di un
   consumatore come `frame` / `title_block`): non entrano nel grafo — sono
   marcatura o arredo del disegno, non contorno. Il predicato è
   `model/role.is_structural_role` (D30); è il punto d'aggancio per un
   consumatore che marca la geometria prima di `heal` (snapdraw) —
   `forge.non_contour_candidates(doc)` (D55) espone lo stesso criterio del
   passo 4 sotto, per decidere QUALI edge marcare qui
3. **chiude i gap** (`close_free_gaps`): estremi liberi entro `tolerance`
   portati alla loro intersezione reale
4. **detection non-contorno** (`find_non_contour_edges`): gli `Edge` con
   entrambi gli endpoint su nodi di branching (grado > 2) e il centroide fuori
   dal convex hull della loro componente sono candidati a non essere contorno
   (D49) — escono dal grafo per non rompere la ricerca dei loop. `heal` non
   decide cosa siano: resta a un consumatore (snapbend li interpreta come
   piega; snapdraw può decidere da sé)
5. **ricerca loop** (`find_loops` → `LoopSearch`, che dice quale gradino ha
   chiuso), con una scala di strategie sempre meno esatte:
   - grafo esatto (uguaglianza delle tuple arrotondate)
   - se restano estremi liberi (D57): clustering degli endpoint entro
     `tolerance` per trovare gli angoli "quasi chiusi", poi chiusura vera
     all'intersezione (`repair_merged_corners`)
   - se non chiude ancora: loop sul grafo clusterizzato tollerante (con
     warning: la discrepanza sopravvive nell'output)
   - se nessun gradino chiude, `heal()` passa all'ultima spiaggia:
     `polygonize_edges` sui segmenti discretizzati, che dà già i contorni
     (`polygons_to_features`, geometria nativa persa)
6. **loop → feature** (`structural_loops`, `loops_to_features`): un loop con un
   edge di ruolo non strutturale non è contorno
7. **costruzione gerarchia** (`build_hierarchy`): quale loop contiene quale →
   albero di contenimento `outer` / `inner`. `heal` si ferma qui: **non** decide
   hole vs inner (D15) — ogni loop contenuto è un `ForgeContour` in
   `cluster.inners`.

Se non si forma **nessun** contorno esterno chiuso, il risultato è dichiarato
**non valido** (`is_valid = False`) — come il modelspace vuoto. `to_dxf` e
`to_svg` lo disegnano lo stesso (tutto in trash) per farti vedere cosa ha capito
forge; rifiutarlo è scelta del chiamante che consegna a una macchina
(`allow_invalid=False`, D83).

`validate_result` viene chiamata automaticamente alla fine.

### 2b. `island` → `ForgeResult` (lettura per isole)

L'alternativa a `heal` per un disegno di **viste** (più viste su un foglio,
isometriche, 3D proiettato). `heal` cerca il pezzo dall'interno, per
connettività: su una vista proiettata più spigoli quasi coincidenti convergono
sugli stessi nodi e non c'è nessun segnale locale per scegliere quale prosegue
come contorno. `island` parte da un fatto globale, cosa sta fuori:

1. **estrae** gli `Edge` con ruolo deciso e non strutturale, come `heal` (D30):
   è così che un consumatore toglie cornice, cartiglio, cerchi di ingrandimento
2. **isole** per vicinanza vera fra segmenti (`spatial_islands`): nessuna nozione
   di chiusura, quindi nessuna ambiguità di grafo
3. per ogni isola **normalizza** sulla griglia fine della rete: nodi dagli
   estremi reali, catene tassellate rifittate come archi/spline, merge/weld di
   `heal`, gap fino a `max_gap` senza mai spostare un estremo più di così
4. **rete piana** (`split_at_crossings`): ogni incrocio diventa un nodo
5. **faccia esterna** (`outer_face`): si parte dal punto più a sinistra della
   geometria, a ogni nodo si gira il meno possibile in senso antiorario; un
   edge percorso andata e ritorno è una sporgenza (asse, segno)
6. **interno**: giri chiusi → `inners`, il resto in `trash_entities`. Un'isola
   il cui contorno sta dentro quello di un'altra non è un cluster: diventa
   interno della più esterna che la contiene

Stesso contratto di `heal`: un `ForgeResult`, un `ForgeCluster` per isola, e
`to_dxf` / `split` non sanno quale lettura l'ha prodotto. Cosa sia
un'isola (vista, pezzo, cornice) lo decide chi chiama (D21). `island` non
chiama mai `heal`.

### 3. la lettura di un consumatore (fuori da forge)

Fori, pieghe, incisioni sono una lettura di processo: le fa snapbend
(`snapbend.flat.detect_flat`, MAP.md D88) sopra il `ForgeResult`, e le attacca
a `cluster.detected` (D44) — non a campi fissi del cluster. forge non conosce
nessun nome dell'overlay: `cluster.features(name)` legge una collezione per
nome, `[]` se `detected` è `None` o quel nome non è stato scritto. I renderer
disegnano ogni elemento dal suo `role` e dalla sua geometria (D90), e l'area
netta toglie gli elementi che si dichiarano vuoti del pezzo (`is_void`).

### 4. render — `to_dxf` / `split`

Costruiscono un documento `ezdxf` **nuovo** (mai il sorgente) e ci scrivono i
segmenti puri del modello, ognuno sul suo layer forge (vedi tabella in
[`API.md`](API.md#output-dxf-layers) e nel README). Regole di fedeltà:

- **le spline** si riemettono come `SPLINE` native, ricostruite da control points
  / knots / weights / degree / tangenti — **mai discretizzate a polilinea**
- **l'overlay**: un contorno con `polygon` si scrive chiuso, uno senza come N
  entità native (`LINE`/`ARC`/`SPLINE`/`CIRCLE`), **mai come `LWPOLYLINE`**
  (D90) — così esce un'incisione di snapbend
- **il trash** si materializza sempre sul layer `Trash`
- **le annotazioni** si riscrivono tutte; in `split` ognuna va nel file della
  parte che la contiene (o della più vicina)

### 5. export / inject

`save_json` / `save_xml` scrivono i metadati per parte secondo lo schema
(`rules/metadata_schema.py`), fondendo tre livelli (D44): `cluster.summary`
(conteggio grezzo, generico, sempre disponibile — `{nome}_count` per ogni
collezione attaccata a `cluster.detected`), `cluster.custom`, ed
`extra`/`extra_metadata` — un
dizionario o una callback esplicita del chiamante (stesso idioma di
`data_injector`) per una detection propria che forge non può conoscere.
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

### Il doppio binario delle feature (role_rules / inferenza)

Ogni feature di un consumatore è raggiungibile per **due strade** (oggi la
seconda è di snapbend, D88):

- **`role_rules`**: il chiamante dice "le linee chiamate `Piega` sono pieghe",
  o "le tratteggiate con `constr` nel nome sono costruzione". Il ruolo è
  assegnato al load, è **autoritativo**, a valle non si rimette in discussione
  (`source="labeled"`, `confidence=1.0`). Il vocabolario dei ruoli è aperto —
  passa per `normalize_role` e non è un errore che forge (cioè il motore)
  non lo conosca. Cosa succede in `heal` dipende da `is_structural=...`
  (D47): senza, qualunque work_type — manifatturiero incluso — resta fuori
  dal grafo, come `frame`/`title_block`; con il predicato di snapbend
  (`snapbend.flat.is_structural`), `hole`/`countersink`/`threaded_hole`
  restano DENTRO il grafo (sono vera topologia di pezzo), solo
  `bending`/`engrave`/`marking` e i ruoli di altri consumatori restano fuori.
  L'output lo scrive su un layer DXF col nome dello slug (non
  `Trash` — non è spazzatura), geometria intatta (D27, D30, D31, D47).
  Una regola combina segnali neutri — nome del gruppo sorgente, tratteggio,
  colore — tutti veri insieme; le regole sono in ordine e vince la prima
  (D63). forge dà il meccanismo, il contenuto lo scrive il chiamante: nessun
  vocabolario di nomi vive in forge. Il nome resta nell'adapter, l'`Edge`
  riceve solo il ruolo. Tratteggio e colore sono quelli **effettivi**: un'entità
  `ByLayer` eredita lo stile dal layer che la contiene, e `DxfAdapter` lo
  risolve prima del confronto. "Tratteggiata" vuol dire che il pattern ha
  almeno un vuoto — un fatto del pattern, non del nome del linetype.
- **inferenza geometrica**: il consumatore riconosce la feature dalla forma
  (`source="geometric"`, `confidence < 1.0`) — per fori e pieghe, snapbend.

---

## Cosa NON è (ancora) pulito

Onestà sullo stato — dettagli e motivazioni sono in `MAP.md` (sezione
"Closed decisions"), non ripetuti qui:

- **`load_pdf`** ritorna `list[Edge]` invece di un `ForgeDocument` → non si
  aggancia a `heal()`. Congelato (MAP.md D10).
- **`detect._detect_engrave`** è ancora un placeholder no-op (MAP.md D13).
- **`heal()` con solo edge etichettati** (tutti con ruolo non strutturale):
  errore "Nessuna geometria chiusa trovata" e `trash_entities` **vuota** — gli
  etichettati non ci arrivano, a differenza di ogni altro caso invalido.
  Comportamento di sempre, conservato tale e quale nella fase B (D62).

Tutta la storia dei refactor già chiusi (bridge/shape eliminato, dispatcher
entità→primitiva unificato, `Edge` spostato da `adapters/` a
`core/topology/`, ecc.) è nel log decisioni — vedi `MAP.md`.
