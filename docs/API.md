# forge — riferimento API

Tutto quello che serve è in `import forge`. I moduli interni non si importano
direttamente. Questo documento copre ogni nome esportato in `forge.__all__`.

Convenzioni di questo documento:

- **firma** — parametri e default reali
- **prende / ritorna** — i tipi
- **muta** — se modifica qualcosa in-place (importante: diversi stadi di
  elaborazione lavorano per effetto collaterale)
- **solleva** — le eccezioni che il chiamante deve prevedere

I tipi di dominio (`ForgeDocument`, `ForgeResult`, `ForgeCluster`, …) sono descritti
in fondo.

---

## Indice

1. [Apertura file](#1-apertura-file) — `load_dxf`, `document_from_msp`, `load_geometry`
2. [Validazione](#2-validazione) — `validate`, `validate_result`
3. [Elaborazione e render](#3-elaborazione-e-render) — `heal` / `island` e i suoi mattoni (core), `anchor_annotations` / `inject` (tools), `to_dxf` / `split` (io), `split_to_files` (recipes)
4. [Export](#4-export) — `save_json`, `to_json`, `save_xml`, `to_view_model`, `to_svg`, `save_svg`
5. [Metadati XDATA](#5-metadati-xdata) — `write_metadata_to_dxf`, `read_metadata_from_dxf`, `set_schema`
6. [Ispezione / debug](#6-ispezione--debug) — `inspect_dxf`, `inspect_document`, `inspect_result`, `inspect_file`
7. [Tipi di dominio](#7-tipi-di-dominio)
8. [Il flusso completo, in ordine](#8-il-flusso-completo-in-ordine)

---

## 1. Apertura file

### `load_dxf`

```python
forge.load_dxf(
    path,
    upgrade=False,
    explode_inserts=True,
    flatten_z_flag=True,
    verbose=False,
    tolerance=0.05,
    role_rules=(),
    ignore_layers=None,
) -> ForgeDocument
```

Unico punto in cui `ezdxf` viene usato per **leggere**. Apre un `.dxf` o `.dwg`,
lo audita, lo porta a R2010 se legacy, esplode gli `INSERT`, sanifica (OCS, Z≠0),
traduce le entità in `Edge` puri e le annotazioni in `Annotation`. Dopo questa
funzione il documento `ezdxf` sorgente sparisce.

| parametro | significato |
|---|---|
| `path` | percorso `.dxf` o `.dwg`. Per il `.dwg` vedi la sezione **DWG** qui sotto. |
| `upgrade` | forza l'upgrade a R2010 anche se non necessario. |
| `explode_inserts` | `True` (default): esplode i blocchi in primitive. **Metti `False` solo se vuoi ignorare i blocchi di proposito** — un `INSERT` non esploso viene scartato e la sua geometria sparisce. |
| `flatten_z_flag` | riporta sul piano le entità con Z ≠ 0. |
| `tolerance` | tolleranza di arrotondamento dei nodi topologici. Viene salvata in `source_meta` e riletta da `heal()` se non gliela ripassi. |
| `role_rules` | lista di `RoleRule` — assegnano il **ruolo** agli `Edge` già in fase di traduzione. Valutate in ordine, vince la prima che matcha, nessuna → `unknown`. Il nome valutato da `name`/`name_contains` è il layer; `dashed` e `color` guardano l'aspetto **effettivo** (un'entità `ByLayer` viene risolta al linetype/colore del suo layer). Il layer non esce dall'adapter: l'`Edge` porta solo il ruolo (MAP.md D63). Vedi **`RoleRule`** sotto. |
| `ignore_layers` | lista di layer da escludere dalla geometria. |

**Ritorna** un `ForgeDocument`. La diagnostica sul file grezzo (audit, INSERT non
esplosi, Z≠0, duplicati rimossi, tipi non ri-materializzabili in output) finisce
in `doc.warnings`; `forge.validate(doc)` la rilancia.

**Solleva** `FileNotFoundError`, `EnvironmentError` (DWG senza `ODA_PATH`),
`RuntimeError` (conversione DWG fallita), o le eccezioni di lettura di `ezdxf`.

```python
doc = forge.load_dxf("pezzo.dxf", tolerance=0.5,
                     role_rules=forge.name_rules({"Piega": "bending", "MARK": "engrave"}))
for w in doc.warnings:
    print("loader:", w)
```

Quando l'intenzione sta nello stile della linea, o in una combinazione di
nome e stile:

```python
doc = forge.load_dxf("pezzo.dxf", role_rules=[
    forge.RoleRule("construction", name_contains="constr", dashed=True),
    forge.RoleRule("bending", dashed=True),
    forge.RoleRule("engrave", color="cyan"),
])
```

Vedi `14_style_classification.py` per un esempio completo (una regola per
step, su un file reale in `tests/examples/`).

### `RoleRule`

```python
forge.RoleRule(role, name=None, name_contains=None, dashed=None, dash=None, color=None)
```

Una regola: se **tutte** le condizioni date sono vere, la linea prende `role`.
forge fornisce il meccanismo; il contenuto (quali nomi, quali stili, quale
ruolo) lo scrive il chiamante (MAP.md D63).

| campo | significato |
|---|---|
| `role` | ruolo assegnato, ripulito da `normalize_role`. Vocabolario aperto: forge conosce solo `outer`, `inner`, `unknown`; `hole`, `bending`, `engrave`, … sono di snapbend (MAP.md D88); qualunque altro slug (`frame`, `title_block`, …) è conservato, trattato come non strutturale e scritto in output su un layer col suo nome (MAP.md D27 / D31). |
| `name` | nome del gruppo sorgente, uguale (maiuscole ignorate). |
| `name_contains` | sottostringa del nome del gruppo (maiuscole ignorate). |
| `dashed` | `True` solo tratteggiate, `False` solo continue. Tratteggiata = il pattern del linetype ha almeno un vuoto (`EdgeStyle.is_dashed`), non il nome del linetype. Vale anche per le catene. |
| `dash` | forma del tratto (`EdgeStyle.dash_kind`), letta dai segni del pattern: `"continuous"` nessun vuoto; `"uniform"` un solo segno ripetuto (tratti tutti uguali, o solo punti); `"chain"` segni diversi alternati (tratto lungo + tratto corto o punto). Due segni sono diversi se differiscono più del 5% della lunghezza del pattern. Valore sconosciuto → `ValueError`. |
| `color` | colore ACI: intero, stringa numerica (`"4"`) o nome standard (`red`, `yellow`, `green`, `cyan`, `blue`, `magenta`, `white`/`black`, `gray`/`grey`, `lightgray`/`lightgrey`, `pink`). |

Metodo `matches(name, style) -> bool`. Condizioni lasciate a `None` non
contano.

**Solleva** `ValueError` se non c'è nessuna condizione (matcherebbe tutto), se
il nome del colore non è riconosciuto o se `dash` non è una delle tre forme.

```python
rules = [
    forge.RoleRule("bending", name="Piega"),         # una piega a catena resta piega
    forge.RoleRule("construction", dash="chain"),    # assi e linee di costruzione
]
```

### `name_rules`

```python
forge.name_rules(mapping: dict[str, str]) -> list[RoleRule]
```

Scorciatoia: `{nome: ruolo}` → una `RoleRule(role, name=nome)` per voce, nello
stesso ordine.

```python
rules = forge.name_rules({"Piega": "bending", "MARK": "engrave"})
rules.append(forge.RoleRule("bending", dashed=True))   # dopo i nomi
```

#### DWG

**`forge` non legge il DWG da solo, e nemmeno `ezdxf`.** Il DWG è un formato
chiuso: il "supporto DWG" di `ezdxf` è l'addon `odafc`, che è un wrapper attorno
a **ODA File Converter** — converte il `.dwg` in un `.dxf` temporaneo e `ezdxf`
rilegge quello. `forge` usa esattamente questo (`adapters/dxf/loader.py`).

Per aprire un `.dwg` serve quindi:

1. **ODA File Converter** installato — download gratuito:
   <https://www.opendesign.com/guestfiles/oda_file_converter>
2. `forge` deve trovare l'eseguibile. Due modi:
   - variabile d'ambiente **`ODA_PATH`** = *full path dell'eseguibile*
     (non la cartella — se ODA è in `ODAFileConverter X.Y.Z\`, il path deve
     includere `\ODAFileConverter.exe`);
   - oppure `ODAFileConverter` raggiungibile dal `PATH` di sistema.

Impostare `ODA_PATH`:

| SO | comando |
|---|---|
| Windows, permanente | `setx ODA_PATH "C:\Program Files\ODA\ODAFileConverter X.Y.Z\ODAFileConverter.exe"` — poi **riapri il terminale** |
| Windows, solo sessione (PowerShell) | `$env:ODA_PATH = "C:\...\ODAFileConverter.exe"` |
| Windows, GUI | Impostazioni → *Modifica le variabili di ambiente relative al sistema* → *Variabili d'ambiente…* → *Nuova* |
| Linux / macOS, permanente | `export ODA_PATH="/opt/ODAFileConverter/ODAFileConverter"` in `~/.bashrc` o `~/.zshrc`, poi riapri la shell |
| Linux / macOS, solo sessione | `export ODA_PATH="/opt/ODAFileConverter/ODAFileConverter"` |

Guide di riferimento per le variabili d'ambiente:
[Windows](https://learn.microsoft.com/windows/win32/procthread/environment-variables) ·
[Linux/macOS (`export`)](https://www.gnu.org/software/bash/manual/bash.html#Environment).

Se manca tutto, `load_dxf` su un `.dwg` solleva `EnvironmentError` con il link e
questa stessa guida nel messaggio.

---

### `document_from_msp`

```python
forge.document_from_msp(
    msp,
    tolerance=0.05,
    role_rules=(),
    ignore_layers=None,
    source_path="",
) -> ForgeDocument
```

Costruisce un `ForgeDocument` da un `modelspace` `ezdxf` **già aperto**. Utile per
i test o per geometria generata a mano. **Non** fa audit / upgrade / sanitize: si
assume che il `msp` sia già pronto. `role_rules` funziona come in `load_dxf()`
— vedi sopra.

```python
import ezdxf
doc_ez = ezdxf.new("R2010"); msp = doc_ez.modelspace()
msp.add_line((0, 0), (100, 0)); msp.add_line((100, 0), (100, 50))
# ...
document = forge.document_from_msp(msp, tolerance=0.5)
```

### `load_geometry`

```python
forge.load_geometry(
    entities,
    tolerance=0.05,
    source_path="",
) -> ForgeDocument
```

Costruisce un `ForgeDocument` da geometria pura — dict Python, non un file.
Stesso contratto di ritorno di `load_dxf`/`document_from_msp`, ma la sorgente è
chi chiama: un generatore parametrico (uno sviluppo cono/cilindro calcolato
altrove) o un ricostruttore di contorni da punti (una traccia vettorializzata da
computer vision). Chi chiama non importa nessun tipo interno di forge.

| parametro | significato |
|---|---|
| `entities` | lista di dict, uno per entità geometrica. `type` supportati: `line` (`start`, `end`), `arc` (`center`, `radius`, `start_angle`/`end_angle` **in gradi**, `ccw`), `circle` (`center`, `radius`), `polyline` (`points`, `closed`), `spline` (`control_points`, `knots`, `degree`, più `weights`/`fit_points`/`closed` opzionali — stessi campi di `SplineSeg`), `ellipse` (`center`, `major_axis` come **vettore** dal centro, più `ratio`/`start_param`/`end_param`/`ccw` opzionali — stessi campi di `EllipseSeg`, stessa parametrizzazione del gruppo DXF ELLIPSE; default = ellisse piena). `role` è opzionale su ogni entità — stesso vocabolario di `RoleRule.role` (`outer`, `hole`, `bending`, …); un valore diverso è conservato come slug di consumatore, non un errore. |
| `tolerance` | tolleranza di arrotondamento dei nodi topologici — stesso significato di `load_dxf(tolerance=...)`. |
| `source_path` | etichetta libera per `ForgeDocument.source_path`; non è un file, serve solo per diagnostica. |

```python
doc = forge.load_geometry([
    {"type": "arc",  "center": (0, 0), "radius": 50,
     "start_angle": -30, "end_angle": 30, "role": "outer"},
    {"type": "line", "start": (43.3, -25.0), "end": (34.6, -20.0), "role": "outer"},
    {"type": "arc",  "center": (0, 0), "radius": 40,
     "start_angle": -30, "end_angle": 30, "role": "outer"},
    {"type": "line", "start": (34.6, 20.0), "end": (43.3, 25.0), "role": "outer"},
])
result = forge.heal(doc, label="sviluppo_cono")
forge.to_dxf(result)
```

```python
# entità "spline" — i campi sono quelli di SplineSeg, presi 1:1
segments = forge.simplify_points(points, closed=True)
doc = forge.load_geometry([
    {
        "type": "spline",
        "control_points": seg.control_points,
        "knots": seg.knots,
        "degree": seg.degree,
        "fit_points": seg.fit_points,
        "closed": seg.closed,
        "role": "outer",
    }
    for seg in segments
])
```

Provato da un caso reale (`snapbend`, ex bendly, che lo usa per portare gli sviluppi che
genera a `ForgeDocument` senza passare da un file — vedi MAP.md D32; il tipo
`spline` viene da `smoother`, che vi passa l'output di `simplify_points()` —
vedi MAP.md D35). Il tipo `ellipse` (MAP.md D45) esiste perché `EllipseSeg`
è una primitiva di forge come le altre — non serve un caso reale a parte,
segue lo stesso schema di `spline`/`circle`.

---

## 2. Validazione

### `validate`

```python
forge.validate(doc: ForgeDocument) -> ForgeResult
```

Valida l'**input** prima di `heal()`. Non modifica niente. Ritorna un
`ForgeResult` con solo `warnings` / `errors` / `is_valid` (`clusters` vuoto).

- **`is_valid = False`** — il file non è lavorabile: nessuna geometria, coordinate
  NaN/inf, tutti i segmenti degeneri.
- **warning** — lavorabile ma da tenere d'occhio: `LINE`/`ARC` ancora fuori da un
  contorno chiuso, endpoint che non si toccano nemmeno alla tolleranza dichiarata,
  segmenti di lunghezza nulla. Include anche le `doc.warnings` del loader.

**Solleva** `TypeError` se non gli passi un `ForgeDocument`.

```python
check = forge.validate(doc)
if not check.is_valid:
    raise SystemExit(check.errors)
for w in check.warnings:
    print("warn:", w)
```

### `validate_result`

```python
forge.validate_result(result: ForgeResult) -> ForgeResult
```

Valida l'**output** dopo `heal()`. **Muta** il `result` passato: aggiunge
`warnings` / `errors` e può mettere `is_valid = False`. Controlla, per ogni cluster:
poligono outer valido e non vuoto, area > 0, ogni inner contenuto nell'outer.

Viene **già chiamata automaticamente da `heal()`** — la usi a mano solo se
costruisci un `ForgeResult` per altre vie.

---

## 3. Elaborazione e render

`heal` e `island` sono le due letture del motore (`forge/core/`), una
dall'interno e una dall'esterno — il chiamante sceglie quella adatta al
disegno; `anchor_annotations` / `inject` sono stadi opzionali su un
`ForgeResult` (`forge/tools/`, il caller sceglie quali e in che ordine);
`to_dxf` / `split` sono renderer del modello (`forge/io/`); `split_to_files` è
la scorciatoia multi-pezzo (`forge/recipes.py`). Fori, pieghe, incisioni sono
una lettura di processo, in snapbend (`snapbend.flat`, MAP.md D88). Tutto resta accessibile come `forge.<nome>`.

### `heal`

```python
forge.heal(doc: ForgeDocument, tolerance=None, label="", source_file="",
           is_structural=None) -> ForgeResult
```

Il passo difficile: ricostruzione della topologia. Lavora su `doc.edges`, zero
`ezdxf`. Chiude i gap, esclude dal grafo gli edge che non chiudono un contorno
(candidati a "qualcos'altro" — `non_contour_candidates()` espone lo stesso
criterio a un consumatore, vedi sezione 8), trova i loop chiusi, costruisce
l'albero di contenimento outer / inner.

`heal()` **non classifica i fori** (D15): consegna solo `ForgeCluster(outer,
inners=[ForgeContour...])`. Chiamare foro un cerchio è una lettura di processo (snapbend, MAP.md D88).

| parametro | significato |
|---|---|
| `tolerance` | se `None`, ripresa da `doc.source_meta["tolerance"]` (quella passata a `load_dxf`). |
| `label` | etichetta del pezzo, finisce in `cluster.label` e nei metadati. |
| `source_file` | nome file sorgente, finisce nei metadati. |
| `is_structural` | `Callable[[str], bool] \| None` — "questo ruolo è topologia di contorno di pezzo?", usato per decidere quali `Edge` già etichettati (da `role_rules`) restano nel grafo prima della ricerca loop. `heal()` da solo conosce solo `outer`/`inner`; senza questo parametro un ruolo di consumatore (`"hole"`, ...) è trattato come non strutturale ed **esce** dal grafo (heal lo segnala con un warning). Il consumatore passa il suo (snapbend: `snapbend.flat.is_structural`). |

`role_rules` **non è un parametro di `heal`** — va passato a `load_dxf()`, che
assegna i ruoli agli `Edge`.

**Ritorna** un `ForgeResult`. Se non si forma nessun contorno esterno chiuso,
`result.is_valid` è `False` e `result.errors` è popolato (la `trash_entities`
resta piena per la diagnostica).

**Solleva** `TypeError` se non gli passi un `ForgeDocument`.

```python
result = forge.heal(doc, tolerance=0.5, label="P-1024")
```

#### I passi di `heal()`

`heal()` è una ricetta: compone questi passi, nell'ordine sotto, e scrive i
warning che li raccontano. Esposti per chi compone la sua (snapdraw: per esempio
fermarsi prima di `build_hierarchy`, finché non ha deciso da sé cosa significa
un contorno dentro un altro — D62). Stessi pezzi di `heal()`, nessun criterio
duplicato.

```python
forge.merge_collinear_overlaps(edges) -> list[Edge]
forge.merge_cocircular_overlaps(edges) -> list[Edge]
forge.weld_degenerate_linesegs(edges) -> list[Edge]
forge.split_labeled(edges, is_structural=None) -> tuple[list[Edge], list[Edge]]
forge.close_free_gaps(edges, tolerance) -> list[Edge]
forge.dangling_splines(edges) -> list[Edge]
forge.find_non_contour_edges(edges, tolerance) -> set[int]
forge.find_loops(edges, non_contour_ids, tolerance) -> LoopSearch
forge.repair_merged_corners(edges, tolerance, exclude_ids=frozenset()) -> tuple[list[Edge], int, list]
forge.structural_loops(loops, is_structural=None) -> list[loop]
forge.loops_to_features(loops) -> list[ClosedFeature]
forge.polygonize_edges(edges, tolerance) -> list[Polygon]
forge.polygons_to_features(polygons) -> list[ClosedFeature]
forge.edges_to_open_features(edges, exclude_ids) -> list[OpenFeature | ClosedFeature]
forge.labeled_features(edges) -> list[OpenFeature | ClosedFeature]
forge.build_hierarchy(features, label="", source_file="", is_structural=None)
    -> tuple[list[ForgeCluster], list]
```

| passo | prende → ritorna | cosa fa |
|---|---|---|
| `merge_collinear_overlaps` | `list[Edge]` → `list[Edge]` | fonde le rette tracciate a spezzoni sovrapposti (D50). |
| `merge_cocircular_overlaps` | `list[Edge]` → `list[Edge]` | lo stesso sugli archi co-circolari (D52). |
| `weld_degenerate_linesegs` | `list[Edge]` → `list[Edge]` | salda i `LineSeg` sotto 0.05 mm in un nodo solo (D56). |
| `split_labeled` | `list[Edge]` → `(restano, etichettati)` | mette da parte gli edge con un ruolo già deciso e non strutturale (D30). Senza `is_structural`, solo `outer`/`inner` sono strutturali. |
| `close_free_gaps` | `list[Edge]` → `list[Edge]` | chiude i gap fra estremi liberi entro `tolerance` (estensione all'intersezione reale o linea di congiunzione). |
| `dangling_splines` | `list[Edge]` → `list[Edge]` | le `SplineSeg` aperte con un estremo non collegato — solo diagnostica. |
| `find_non_contour_edges` | `list[Edge]` → `set[id(Edge)]` | edge che non chiudono un contorno (D49), da tenere fuori dal grafo. `non_contour_candidates(doc)` è la stessa cosa su un documento. |
| `find_loops` | `list[Edge]` → `LoopSearch` | la scala: grafo esatto → riparazione angoli se restano estremi liberi (D57) → grafo tollerante. |
| `repair_merged_corners` | `list[Edge]` → `(edge, n_riparati, cluster_saltati)` | il secondo gradino da solo: angoli fusi dal clustering portati all'intersezione reale; cluster di 3+ estremi saltati. |
| `structural_loops` | loop → loop | tiene i loop senza edge di ruolo non strutturale. |
| `loops_to_features` | loop → `list[ClosedFeature]` | un `ClosedFeature` per loop, geometria nativa. |
| `polygonize_edges` | `list[Edge]` → `list[Polygon]` | ultima spiaggia quando `find_loops` non chiude: le facce dell'intero disegno discretizzato. |
| `polygons_to_features` | `list[Polygon]` → `list[ClosedFeature]` | OUTER dal bordo, INNER dai buchi, a `LineSeg` (la geometria nativa è persa). |
| `edges_to_open_features` | `list[Edge]` → feature | gli edge non assorbiti da un loop (`exclude_ids`) come feature aperte. |
| `labeled_features` | `list[Edge]` → feature | gli etichettati di `split_labeled`, col ruolo intatto. |
| `build_hierarchy` | feature → `(cluster, trash)` | albero di contenimento: ogni radice un `ForgeCluster`, i discendenti `inners` con `depth`/`parent`. |

Nessuno **muta** l'input: ritornano liste/oggetti nuovi.

`LoopSearch` — come `find_loops` ha chiuso (o non chiuso) i giri:

| campo | tipo | significato |
|---|---|---|
| `edges` | `list[Edge]` | gli edge dopo l'eventuale riparazione degli angoli — da usare a valle al posto di quelli in ingresso |
| `loops` | `list[loop]` | loop `[(Edge, reversed)]`, vuota se nessun gradino chiude |
| `method` | `str` | `"exact"`, `"corner_repair"`, `"tolerant"` o `"none"` |
| `repaired` | `int` | angoli chiusi all'intersezione reale |
| `skipped_corners` | `list` | cluster non riparati (3+ estremi) |
| `unrepaired_corners` | `list` | con `"tolerant"`: angoli fusi solo nel grafo, la discrepanza resta nell'output |
| `open_nodes` | `list` | con `"none"`: gli estremi liberi |

```python
# la ricetta di heal() fino ai contorni chiusi, senza gerarchia
edges, labeled = forge.split_labeled(doc.edges, is_structural)
edges = forge.close_free_gaps(edges, 0.1)
search = forge.find_loops(edges, forge.find_non_contour_edges(edges, 0.1), 0.1)
print(search.method, len(search.loops))
closed = forge.loops_to_features(forge.structural_loops(search.loops, is_structural))
```

---

### `island`

```python
forge.island(doc: ForgeDocument, tolerance=None, island_gap=10.0,
             max_gap=0.5, is_structural=None) -> ForgeResult
```

La seconda lettura di un documento, accanto a `heal()`: **per isole**.
`heal()` ricostruisce la topologia dall'interno (chi tocca chi, quali giri si
chiudono, chi sta dentro chi) e trova il pezzo per contenimento. `island()`
legge il disegno dall'esterno:

1. separa le **isole** per vicinanza vera fra segmenti (`spatial_islands`);
2. per ogni isola normalizza (tassellature rifittate come archi/spline,
   merge/weld di `heal`, gap fino a `max_gap`) e rende la rete **piana**
   (`split_at_crossings`);
3. il **contorno esterno** è il bordo della faccia esterna della rete
   (`outer_face`) — gli edge percorsi andata e ritorno (assi, segni che
   sporgono) non sono contorno;
4. dentro: i giri chiusi diventano `inners`, il resto va in `trash_entities`
   col ruolo che aveva (`unknown` se nessuno l'ha deciso).

**Quando usarla invece di `heal()`**: disegni di viste — più viste su un
foglio, viste isometriche/3D proiettate, sagome con linee quasi coincidenti
dove il grafo di `heal()` è ambiguo. Per un disegno di sagome piane (uno o più
pezzi separati, geometria esatta da cucire) resta `heal()`.

Un'isola il cui contorno sta **dentro** quello di un'altra non è un cluster:
diventa interno (`inners`) dell'isola più esterna che la contiene. Con la
cornice nel disegno, quindi, l'unico cluster è la cornice: toglierla (o dare un
ruolo a cornice, cartiglio, cerchi di ingrandimento) è compito del chiamante.
Cosa sia un cluster — vista, pezzo — lo decide chi lo usa (D21).

| parametro | significato |
|---|---|
| `tolerance` | se `None`, ripresa da `doc.source_meta["tolerance"]` — come `heal()`. |
| `island_gap` | distanza massima (mm) fra due edge della stessa isola. Dipende da come è impaginato il disegno, non dalla geometria. |
| `max_gap` | gap (mm) chiusi fra estremi liberi, mai spostando un estremo più di così. |
| `is_structural` | come in `heal()` (D30): un `Edge` con un ruolo già deciso e non strutturale (`frame`, `title_block`, ...) resta **fuori** dalla lettura e va in `trash_entities` col suo ruolo. È così che un consumatore toglie cornice e cartiglio prima di leggere le viste. Senza, solo `outer`/`inner` sono strutturali. |

**Ritorna** un `ForgeResult` con un `ForgeCluster` per isola non annidata,
ordinati per area del contorno esterno. Nessun giro chiuso in nessuna isola →
`is_valid=False`, `errors` popolato.

**Solleva** `TypeError` se non gli passi un `ForgeDocument`.

```python
doc = forge.load_dxf("tavola.dxf")
result = forge.island(doc, island_gap=10.0)
for cluster in result.clusters:          # una vista / un pezzo per cluster
    print(cluster.outer.polygon.area, len(cluster.inners))
```

#### I mattoni di `island()`

Esposti per chi compone la sua ricetta (snapdraw: togliere cornice e cartiglio
per ruolo, poi leggere le viste) — stessi pezzi, nessun criterio duplicato.

```python
forge.read_islands(edges, tolerance, island_gap=10.0, max_gap=0.5) -> list[IslandReading]
forge.read_island(edges, tolerance, max_gap=0.5) -> IslandReading
forge.spatial_islands(edges, gap_tolerance) -> list[Island]
forge.split_at_crossings(edges, tolerance, decimals=3) -> NodedEdges
forge.outer_face(edges, epsilon=0.0) -> OuterFace | None
forge.refit_tessellations(edges, max_segment=0.1, min_run=10,
                          arc_fit_tolerance=0.02, node_decimals=3) -> list[Edge]
```

| funzione | prende → ritorna | cosa fa |
|---|---|---|
| `read_islands` | `list[Edge]` → `list[IslandReading]` | isole + `read_island` per ognuna + annidamento (`nested_in`). È `island()` prima di diventare `ForgeResult`. |
| `read_island` | `list[Edge]` → `IslandReading` | un'isola: normalizza, rete piana, faccia esterna, classificazione dell'interno. |
| `spatial_islands` | `list[Edge]` → `list[Island]` | union-find sulle coppie di edge a distanza vera `<= gap_tolerance` (STRtree). Nessuna nozione di chiusura. |
| `split_at_crossings` | `list[Edge]` → `NodedEdges` | spezza `LineSeg`/`ArcSeg`/`CircleSeg` dove incrociano o toccano a T un altro edge; `NodedEdges.parent_of(pezzo)` dà l'`Edge` originale. `SplineSeg`/`EllipseSeg` restano interi. |
| `outer_face` | `list[Edge]` (rete piana) → `OuterFace \| None` | bordo della faccia esterna, per componente, quella di area massima; `spurs` = edge percorsi andata e ritorno. |
| `refit_tessellations` | `list[Edge]` → `list[Edge]` | catene di `LineSeg` corti (curva scritta a punti) rifittate come arco/cerchio/spline; estremi della catena sui nodi originali. |

Nessuna **muta** l'input: ritornano liste/oggetti nuovi.

`IslandReading` — cosa è stato deciso su un'isola, pezzo per pezzo:

| campo | tipo | significato |
|---|---|---|
| `edges` | `list[Edge]` | gli edge dell'isola, come arrivano |
| `outer` | `OuterFace \| None` | contorno esterno (`polygon`, `segments`, `edges`, `spurs`) |
| `inner_loops` | `list[loop]` | giri chiusi dentro, come dal `LoopFinder` |
| `spurs` | `list[Edge]` | percorsi andata e ritorno dal contorno |
| `outside` | `list[Edge]` | pezzi dell'isola rimasti fuori dal contorno (rete staccata) |
| `non_contour` | `list[Edge]` | candidati non-contorno, stesso criterio di `heal()` (D49) |
| `unclassified` | `list[Edge]` | il resto |
| `nested_in` | `int \| None` | indice dell'isola più esterna che la contiene |

---

### `contour_shape`

```python
forge.contour_shape(item, tolerance=0.01, angle_tolerance=1.0) -> ContourShape | None
```

La forma di un contorno chiuso (`ForgeContour`, un oggetto con `.segments`
o la lista dei segmenti): `circle`, `stadium` (stadio: due semicerchi uguali
e due rette parallele — nome geometrico, non "asola"), `rectangle`, `polygon` (solo rette), `other`. Fatto
geometrico, non feature: `circle` non vuol dire foro, lo decide chi legge il
disegno o il processo. Vale uguale su `heal` e su `island`. I segmenti
consecutivi sulla stessa retta o circonferenza sono ricomposti prima.
`tolerance` è una frazione della dimensione del contorno.

`ContourShape`: `kind`, `center`, `length` (maggiore; cerchio: diametro;
stadio: fuori tutto), `width` (minore; stadio: 2 × raggio), `angle` (gradi
[0, 180) dell'asse lungo, `None` per il cerchio), `sides` (segmenti dopo la
ricomposizione), `diameter` (solo cerchio), `.to_dict()`.

**Non muta** niente.

---

### `concentric_groups`

```python
forge.concentric_groups(items, tolerance=0.1) -> list[ConcentricGroup]
```

I contorni circolari di `items` (come per `contour_shape`) raggruppati per
centro: ogni cerchio sta in un solo gruppo, anche da solo; i non circolari non
compaiono. `tolerance` è la distanza massima fra i centri, in unità del
disegno. Fatto geometrico: due cerchi concentrici non sono una svasatura,
come accoppiarli lo decide il consumatore (D91).

`ConcentricGroup`: `center` (del cerchio più piccolo), `items` e `shapes`
(`ContourShape`) dal raggio minore al maggiore, `diameters`.

**Non muta** niente.

---

### `arcs_around`

```python
forge.arcs_around(center, radius, arcs, tolerance=0.1) -> list[ArcAround]
```

Gli `ArcSeg` di `arcs` concentrici al cerchio (`center`, `radius`) entro
`tolerance` e più grandi di lui, dal più vicino al più lontano. Nessuna soglia
sull'angolo: "~270°, poco più grande" è come si disegna una cresta di filetto,
lo applica il consumatore (D91).

`ArcAround`: `arc`, `sweep` (gradi, nel verso dell'arco), `radius_ratio`
(raggio dell'arco / `radius`).

**Non muta** niente.

---

### `splits_polygon`

```python
forge.splits_polygon(polygon, start, end, reach=0.0) -> bool
```

La corda `start`-`end`, prolungata di `reach` ai due capi, divide il poligono
(shapely) in due o più parti. Fatto geometrico: che quella corda sia una piega
lo decide il consumatore (snapbend la prolunga di 1 mm, D93).

**Non muta** niente.

---

### `bridged_runs`

```python
forge.bridged_runs(segments, bridges, tolerance=0.1, angle_tolerance=1e-6) -> list[CollinearRun]
```

File di due o più tratti sulla stessa retta in cui lo spazio fra un tratto e il
successivo sta tutto dentro uno dei poligoni di `bridges` (per esempio i vuoti
di un pezzo). Un tratto è una `LineString` o una coppia `(start, end)`;
`tolerance` è la distanza massima dalla retta, `angle_tolerance` la differenza
di direzione in radianti. I tratti rimasti da soli non compaiono.

`CollinearRun`: `start`, `end` (i capi esterni della fila), `members` (indici in
`segments`, nell'ordine lungo la retta).

**Non muta** niente.

---


### `to_dxf`

```python
forge.to_dxf(
    result: ForgeResult,
    source_doc: ForgeDocument = None,
    filter_cluster=None,
    include_annotations=True,
    include_trash=True,
    annotation_layer="Annotation",
    role_styles: dict[str, RoleStyle] = None,
    allow_invalid: bool = True,
) -> ezdxf.document.Drawing
```

Materializza il modello in un **documento DXF nuovo** (R2010). Non rilegge mai
entità dalla sorgente: `source_doc` serve solo a riportare gli header
(`$INSUNITS`, `$MEASUREMENT`). Testi e quote arrivano da `result.annotations`.

| parametro | significato |
|---|---|
| `filter_cluster` | `callable(ForgeCluster) -> bool` — scrive solo le parti che passano. |
| `include_trash` | `True` (default): la geometria non classificata va sul layer `Trash`. Chi apre il file deve poter vedere ogni entità del disegno di partenza. |
| `allow_invalid` | `True` (default): un `result` non valido viene scritto lo stesso (trash e annotazioni), come fa `to_svg`. `False` → `ValueError`: per il chiamante che consegna il file a una macchina (D83). |
| `annotation_layer` | `"Annotation"` → layer forge dedicato; `"Trash"` o altro nome → quel layer; `None` → layer originale della sorgente. Nessuna annotazione viene mai scartata. |
| `role_styles` | override esplicito, per ruolo, di colore/linetype/lineweight (vedi `RoleStyle` sotto). Agisce sul layer — tutto ciò che forge scrive è BYLAYER. `None` (default) = nessun cambiamento rispetto alla palette di `rules/palette.py`. |

```python
# la cornice (ruolo "frame", assegnato da un consumatore come snapdraw) in nero
forge.to_dxf(result, doc, role_styles={"frame": forge.RoleStyle(color=(0, 0, 0))})
```

**L'overlay** (D70, D90): scrive ogni collezione di `cluster.detected`,
senza conoscerne nessuna per nome. Di un elemento legge solo `role` e
geometria: `item.contours` se c'è (ognuno con `segments`/`styles`/`polygon`
ed eventualmente un suo `role`), altrimenti l'elemento stesso. Un contorno
con `polygon` si scrive chiuso (LWPOLYLINE/CIRCLE), uno senza come una entità
per primitiva (LINE/ARC/SPLINE). Il `role` di un contorno vince su quello
dell'elemento solo se non è un ruolo del motore (`outer`/`inner`/`unknown`).
Senza ruolo o senza geometria si salta.

**Ritorna** un `Drawing` `ezdxf`. Sta a te fare `doc_out.saveas(...)`.

**Solleva `ValueError`** solo con `allow_invalid=False` e `result.is_valid`
`False`. Il rifiuto non è del formato, è di chi consegna il file a una macchina:
quel chiamante lo chiede esplicitamente.

```python
forge.to_dxf(result, doc).saveas("guarda.dxf")                         # sempre
forge.to_dxf(result, doc, allow_invalid=False).saveas("macchina.dxf")  # solo se valido
```

---

### `split`

```python
forge.split(
    result: ForgeResult,
    source_doc: ForgeDocument = None,
    namer=None,
    include_annotations=True,
    min_area=50.0,
    exclude_types=None,
    on_part=None,
    annotation_layer="Annotation",
    role_styles: dict[str, RoleStyle] = None,
) -> list[ezdxf.document.Drawing]
```

Come `to_dxf` ma produce **un `Drawing` per parte**. Funzione **pura**: non tocca
il disco. Le parti sotto `min_area` (mm²) vengono scartate (con warning nel
`result`).

| parametro | significato |
|---|---|
| `namer` | `callable(i, cluster) -> str` — assegna `cluster.label`, così il nome file resta `f"{cluster.label}.dxf"` a valle. |
| `exclude_types` | set di `dxftype` da rimuovere dal documento di ogni parte (es. `{"TEXT"}`). |
| `on_part` | `callable(cluster, doc_out)` — hook per parte, prima che il `Drawing` entri nella lista. |

**Ritorna** la lista dei `Drawing` nell'ordine delle parti tenute.
**Solleva `ValueError`** se `result.is_valid` è `False`.

```python
docs = forge.split(result, doc, min_area=100.0)
for d, cluster in zip(docs, [p for p in result.clusters if p.outer.polygon.area >= 100]):
    d.saveas(f"{cluster.label}.dxf")
```

---

### `RoleStyle`

```python
@dataclass(frozen=True)
class RoleStyle:
    color:      tuple[int, int, int] | None = None   # RGB 0-255, canonico
    linetype:   str | None = None                     # nome standard ezdxf, es. "DASHED"; ignoto → ValueError (D85)
    lineweight: float | None = None                   # mm
    layer_name: str | None = None                     # nome layer/gruppo di output
```

Override, indipendente dal formato, dell'aspetto visivo di un ruolo in
output — noto al motore (`"outer"`, `"inner"`) o assegnato da chiunque
altro — snapbend (`"hole"`, ...), snapdraw (`"frame"`, `"title_block"`,
...) — nessuno è privilegiato. Ogni
campo lasciato `None` resta il default di forge per quel ruolo. Passato a
`to_dxf`/`split` come `role_styles={ruolo: RoleStyle(...)}` — dizionario
esplicito del chiamante, stesso idioma di `role_rules`, riusabile su più
chiamate/formati; vince sempre su un eventuale stile registrato (sotto).

Pensato per crescere per aggiunta: un futuro campo si aggiunge alla
dataclass senza toccare la firma di `to_dxf`/`split` né rompere chi già
passa un `RoleStyle` con meno campi.

```python
forge.to_dxf(result, doc, role_styles={
    "frame":   forge.RoleStyle(color=(0, 0, 0)),          # cornice: nero
    "unknown": forge.RoleStyle(lineweight=0.05),          # trash: linea sottilissima
})
```

### `register_role_style`

```python
forge.register_role_style(role, style: RoleStyle) -> None
```

Registra uno `RoleStyle` per `role` **una volta sola**, valido per ogni
`to_dxf`/`split` successivo senza doverlo ripassare — stesso idioma di
`forge.set_schema()` per i metadati. Un consumatore lo chiama una volta al
proprio setup invece di ricostruire `role_styles=` a ogni chiamata —
`snapbend.flat` lo fa per i suoi colori (`hole` magenta, `bending` rosa, ...).
`role_styles=` passato a una singola chiamata resta possibile e
vince comunque su quanto registrato qui.

```python
forge.register_role_style("frame", forge.RoleStyle(color=(0, 0, 0)))
# ogni to_dxf/split successivo applica il nero al layer "frame" da solo
```

---

### `split_to_files`

```python
forge.split_to_files(
    doc: ForgeDocument,
    output_folder,
    label="",
    source_file="",
    tolerance=None,
    namer=None,
    include_annotations=True,
    min_area=50.0,
    exclude_types=None,
    annotation_layer="Annotation",
    is_structural=None,
) -> ForgeResult
```

Flusso multi-pezzo + salvataggio su disco: `heal → split → .saveas()` per
cluster (`is_structural` passa a `heal`). Una lettura di processo (fori,
pieghe) si fa sul result con `heal` + la detection + `split`, non qui. **È l'unica funzione di forge che scrive su disco.**
Il nome file è `f"{cluster.label}.dxf"`, dove `cluster.label` è quello che assegna
`namer(i, cluster)`; senza `namer` diventa `f"{label}_P{i+1}"` (es. `batch_P1.dxf`).

**Ritorna** il `ForgeResult` (per poterci fare `save_json` dopo). Se il risultato
non è valido, ritorna il result senza scrivere niente.

```python
result = forge.split_to_files(doc, "output/", label="batch")
forge.save_json(result, "batch.json")
```

---

### `anchor_annotations`

```python
forge.anchor_annotations(result: ForgeResult, snap_distance=0.0,
                         leader_distance=0.5) -> ForgeResult
```

Collega le annotazioni alla geometria. Per ogni annotazione `cluster_ref` =
indice del cluster il cui contorno esterno ne contiene la posizione (con
`snap_distance` > 0, anche il più vicino entro quella distanza). Per ogni
`Leader` con vertici anche `target` — vedi `leader_target`; per ogni
`Dimension` `references` — vedi `dimension_references`.

**Muta** le annotazioni di `result` in-place. **Ritorna** lo stesso `result`.

### `leader_target`

```python
forge.leader_target(result: ForgeResult, leader: Leader,
                    distance=0.5) -> str | None
```

L'elemento su cui cade la punta (`vertices[0]`) di `leader`, come percorso in
`result`: `"clusters[0].outer"`, `"clusters[0].inners[3]"`,
`"clusters[1].holes[2]"` — qualunque collezione di `cluster.detected`, quindi
vale dopo la lettura di un consumatore come dopo `island`.

Regola: il bordo più vicino alla punta, se entro `distance` (a parità, vince
l'elemento più piccolo); altrimenti il più piccolo elemento chiuso, non il
contorno esterno, che contiene la punta (freccia che finisce dentro un foro);
altrimenti `None` (freccia di sezione, fuori dal pezzo). Non legge il testo.

**Non muta** niente.

### `dimension_references`

```python
forge.dimension_references(result: ForgeResult, dimension: Dimension,
                           distance=0.5) -> list[str]
```

Gli elementi fra cui la quota misura, come percorsi in `result` (stesso
formato di `Leader.target`): per ogni punto di `measured_points` l'elemento
il cui bordo passa entro `distance` (a parità il più piccolo). Senza doppioni,
nell'ordine dei punti: un diametro dà il cerchio, una lineare uno o due
elementi. Non legge il testo.

**Non muta** niente.

### `resolve_target`

```python
forge.resolve_target(result: ForgeResult, target: str | None) -> Any
```

Il passo inverso: il contorno o la feature a cui punta un `target`, o `None`
se il percorso non esiste più in `result` (per esempio dopo una detection che ha
spostato i fori da `inners` a `holes`: ancorare dopo aver scelto le feature).

---

### `inject`

```python
forge.inject(
    result: ForgeResult,
    data_injector=None,
    snap_distance: float = 0.0,
) -> ForgeResult
```

Arricchimento **opzionale** dai testi. **Muta** `result.clusters[i].custom` in-place e
ritorna il `result`. Fa **una cosa**: se passi `data_injector` —
`callable(cluster, list[str]) -> dict` — gli passa i testi di
`result.annotations` che ricadono dentro l'outer di ogni parte e mette il dict
restituito in `cluster.custom` (codice pezzo, materiale, spessore, …). Senza
`data_injector`, `inject()` non fa nulla.

`snap_distance` > 0: un testo fuori da ogni parte va alla parte **più vicina**
(una sola) se dista al massimo `snap_distance` dal suo contorno esterno — il
callout scritto appena fuori dal pezzo. Stessa regola di `anchor_annotations`
(MAP.md D82). Un testo contenuto non viene mai spostato dallo snap.

I **conteggi delle feature** NON si fanno qui: `cluster.summary` dà il
conteggio grezzo per nome dell'overlay (sempre disponibile), il dettaglio per
tipo è del consumatore che le ha lette (MAP.md D44, D88). Per metterlo
nell'export passa `extra_metadata` (vedi sotto).

```python
def leggi_cartiglio(cluster, testi):
    return {"material": next((t for t in testi if t.startswith("S")), "S275JR")}

forge.inject(result, data_injector=leggi_cartiglio, snap_distance=5.0)
```

---

## 4. Export

Tutti leggono lo schema da `forge/rules/metadata_schema.py` — **una sola fonte**
per i nomi dei campi. Cambia quel file (o usa `set_schema`) per adattarti al tuo
CAM.

### `save_json` / `to_json`

```python
forge.save_json(
    result: ForgeResult, path, indent=2,
    extra_metadata: Callable[[ForgeCluster], dict] = None,
) -> None   # scrive su file
forge.to_json(
    result: ForgeResult, indent=2,
    extra_metadata: Callable[[ForgeCluster], dict] = None,
) -> str    # ritorna la stringa
```

Metadati per parte secondo schema — **niente coordinate**. `extra_metadata`
(D44), se passata, viene chiamata una volta per cluster e i campi che
ritorna finiscono nell'output **fuori dallo schema** — passarla è già la
scelta esplicita del chiamante, stesso idioma di `data_injector`. Serve per
una detection tua (fori per tipo, una `FlangeViewHint`) che forge non può
conoscere. Struttura:

```json
{
  "source_file": "batch.dxf",
  "is_valid": true,
  "cluster_count": 3,
  "warnings": [], "errors": [],
  "clusters": [
    {
      "label": "P-1", "source_file": "batch.dxf",
      "quantity": 1, "material": "S275JR", "thickness_mm": 0.0,
      "area_mm2": 12345.67, "inner_contours_count": 1,
      "outer_perimeter_mm": 480.0, "inner_perimeter_mm": 60.0,
      "total_perimeter_mm": 540.0,
      "bbox": {"minx": 0, "miny": 0, "maxx": 200, "maxy": 100}
    }
  ]
}
```

### `save_xml`

```python
forge.save_xml(
    result: ForgeResult, path,
    extra_metadata: Callable[[ForgeCluster], dict] = None,
) -> None
```

Stessi campi di `save_json` (`extra_metadata` incluso), in XML
(`<forge><clusters><cluster>…`).

### `to_view_model`

```python
forge.to_view_model(
    result: ForgeResult,
    tolerance=0.05,
    include_trash=True,
    include_annotations=True,
) -> dict
```

`ForgeResult` → dizionario JSON **orientato al rendering**: le coordinate di
*ogni* feature + ruolo + colore hex. È il pendant geometrico di `to_json` (che dà
solo metadati). Lo consuma `to_svg` e lo consumerebbe un front-end esterno
(dashboard JS che disegna con SVG/Canvas).

> `to_text(result) -> str` / `save_text(result, path)` — la lettura per un
> modello linguistico (`<nome>.forge.md`) — è **sperimentale**, fuori da
> `__all__` finché non ha un chiamante vero (MAP.md D84). Firma e sezioni in
> `docs/LLM.md`, insieme a una tabella di cosa dà ogni uscita.

> `to_nester_input(result) -> list[dict]` esiste ancora (`label`, `bbox`,
> `outer_coords`, `holes_coords` per parte) ma è **sperimentale**, fuori da
> `__all__` — scritto per un nester mai realizzato (MAP.md D18). Per serializzare
> la geometria usa `to_view_model`.

Tutta la geometria è **discretizzata a polilinee** (`points: [[x, y], …]`):
archi, cerchi, spline appiattiti. L'overlay sta sotto `features`, per nome
(D90): una voce per contorno, con ruolo, colore, punti, `closed` e i campi
scalari del `to_dict()` dell'elemento — chi porta `center` + `diameter` si può
disegnare come cerchio vero. Coordinate nel sistema del sorgente (Y in alto).

```python
vm = forge.to_view_model(result)
vm["clusters"][0]["outer"]        # {"role": "outer", "color": "#00ff00", "points": [...], "closed": true}
vm["clusters"][0]["features"]     # {"holes": [{"role": "hole", "points": [...], "diameter": ..., ...}], ...}
vm["palette"]                  # {"outer": "#00ff00", ...} + i ruoli registrati
```

Non muta `result`, non solleva su `result` non valido (torna il dict con
`is_valid=False`).

### `to_svg` / `save_svg`

```python
forge.to_svg(
    result: ForgeResult,
    tolerance=0.05,
    include_trash=True,
    include_annotations=True,
    padding=0.03,
    background="#1e1e1e",     # None = trasparente
    true_circles=True,        # una voce con center + diameter → <circle>
    stroke_width=None,        # None = auto (diagonale bbox / 400)
    size=None,                # None = niente width/height → scala al contenitore
    units=None,               # "mm" = SVG in scala reale, 1 unità = 1 mm
    allow_invalid=True,       # False → ValueError su un result non valido
) -> str
forge.save_svg(result, path, **kwargs) -> None
```

Renderer SVG del modello (MAP.md D12) — per visualizzazione (UI/report/
anteprima) o per una macchina che importa SVG. Un colore per ruolo (stessa palette semantica del DXF di output). La
Y viene ribaltata (modello Y-su → SVG Y-giù). Una parte = un `<g data-cluster="…">`.
Costruito sopra `to_view_model`.

`size=None` (default) **non** scrive `width`/`height` sull'`<svg>`: l'immagine è
vettoriale e scala a riempire il contenitore (o la finestra del browser) — la
zoomi quanto vuoi. Passa `size="800"` per fissare la larghezza in px.

`units="mm"` produce un SVG **in scala reale** (`width="…mm"`, padding e sfondo a
zero) per chi importa SVG in un software che vuole 1 unità = 1 mm.
**Attenzione:** archi, cerchi e spline restano discretizzati a polilinea — quando
conta la curva esatta (cerchi lisci, quote a tolleranza) usa `to_dxf`, non l'SVG.

Un `result` non valido viene disegnato lo stesso. `allow_invalid=False` →
`ValueError`, stesso contratto di `to_dxf` (D83).

```python
forge.save_svg(result, "pezzo.svg")
```

---

## 5. Metadati XDATA

### `write_metadata_to_dxf` / `read_metadata_from_dxf`

```python
forge.write_metadata_to_dxf(doc, cluster: ForgeCluster, extra: dict = None) -> None
forge.read_metadata_from_dxf(doc) -> dict
```

Scrive / rilegge i metadati (stessi campi di `save_json`, `extra` incluso —
un dict diretto qui, non una callback, perché opera già su un singolo
cluster) come XDATA `FORGE` sull'entità del layer `OuterContour`. `doc` è un
`Drawing` `ezdxf` (tipicamente quello restituito da `to_dxf`). `read_`
ritorna `{}` se non trova niente.

```python
doc_out = forge.to_dxf(result, doc)
forge.write_metadata_to_dxf(doc_out, result.clusters[0])
doc_out.saveas("out.dxf")
# più tardi:
meta = forge.read_metadata_from_dxf(ezdxf.readfile("out.dxf"))
```

### `set_schema`

```python
forge.set_schema(schema: dict) -> None
```

Sostituisce lo schema metadati attivo a runtime. Da usare quando `forge` è
installato con pip e non puoi editare `metadata_schema.py`. Struttura:
`{chiave_interna: (nome_output, default, sorgente)}` con `sorgente` ∈
`{"cluster", "custom", "calculated"}`.

---

## 6. Ispezione / debug

Tre livelli, in ordine di elaborazione. Tutti stampano su stdout.

```python
forge.inspect_dxf(path, entities=True, limit=40) -> None
```
**Livello 1** — entità DXF grezze: versione, header, conteggio per tipo e per
layer, dettaglio di ogni entità. Non tocca `forge`.

```python
forge.inspect_document(doc, graph=True, limit=60) -> None
```
**Livello 2** — un `ForgeDocument` (o un path): `source_meta`, warning del loader,
gli `Edge` (ruolo, primitiva, endpoint), le annotazioni, e il
grafo dei nodi (nodi totali, loop degeneri, nodi di branching, estremi liberi).
"Cosa ha capito l'adapter."

```python
forge.inspect_result(result, coords=False) -> None
```
**Livello 3** — un `ForgeResult`: validità, warning/errori, e per ogni parte
outer/inner, le collezioni di `cluster.detected` (quello che un consumatore ha
attaccato), custom, più `trash_entities`,
`classified_entities`, annotazioni. "Cosa ha prodotto forge."

```python
forge.inspect_file(path, tolerance=0.05, role_rules=(),
                   run_heal=True, entities=True, coords=False) -> None
```
Orchestratore: apre il file e stampa i tre livelli in fila. `run_heal=False` per
fermarti al `ForgeDocument`. `role_rules` come in
`load_dxf()`.

```python
forge.inspect_file("pezzo.dxf", role_rules=forge.name_rules({"Piega": "bending"}))
forge.inspect_file("pezzo.dxf", role_rules=[forge.RoleRule("bending", dashed=True)])
```

---

## 7. Tipi di dominio

### `ForgeDocument`

Prodotto da `load_dxf` / `document_from_msp`. È il contratto tra l'adapter e il
core: dopo di lui, `ezdxf` non si tocca più.

| campo | tipo | contenuto |
|---|---|---|
| `edges` | `list[Edge]` | geometria tradotta in primitive pure — input di `heal()` |
| `annotations` | `list[Annotation]` | testi e quote della sorgente |
| `source_meta` | `dict` | `$INSUNITS`, `$MEASUREMENT`, `tolerance`, `ignore_layers` |
| `source_path` | `str` | percorso del file |
| `warnings` | `list[str]` | diagnostica del loader sul file grezzo |

`node_tolerance(override=None) -> float`: la distanza sotto cui due estremi
sono lo stesso nodo — `override` se dato, altrimenti `source_meta["tolerance"]`,
altrimenti `DEFAULT_NODE_TOLERANCE` (0.05, `model/document.py`). È la lettura
che usano `heal`, `island` e `validate` quando `tolerance` non è passata (D86).

### `Annotation`

`Note` / `Dimension` / `Leader`. Comuni: `kind` (`"TEXT"` | `"MTEXT"` |
`"DIMENSION"` | `"LEADER"` | `"MULTILEADER"`), `position` `(x, y)`,
`cluster_ref`, `display_text`.

- `Note`: `text`, `height`, `rotation`.
- `Dimension`: `measured_value`, `dim_type`, `text_override` (testo
  dell'autore, `<>` = la misura), `rendered`, `measured_points` (i punti
  sulla geometria fra cui misura), `references` (percorsi degli elementi
  quotati, da `anchor_annotations`). `display_text` = override con `<>`
  sostituito dalla misura come è scritta nel disegno.
- `Leader`: `text`, `vertices` (`[0]` = punta), `target`.

### `ForgeResult`

Prodotto da `heal()`, arricchito da un consumatore / `inject()`.

| campo | tipo | contenuto |
|---|---|---|
| `clusters` | `list[ForgeCluster]` | un elemento per contorno esterno chiuso |
| `is_valid` | `bool` | **controllalo prima di `to_dxf` / `split`** |
| `warnings` / `errors` | `list[str]` | diagnostica |
| `trash_entities` | `list` | geometria non classificata (proxy con `segments`, formato-indipendenti) |
| `annotations` | `list[Annotation]` | copiate da `heal()` dal `ForgeDocument` |
| `classified_entities` | `list` | di un consumatore (snapbend: marking, work_type custom) |
| `all_arcs` | `list[ArcSeg]` | tutti gli archi del disegno (snapbend li usa per i fori filettati) |
| `cluster_count` | property | `len(clusters)` |

Metodo `to_dict()` → dizionario JSON-ready (usato internamente dagli export).

### `ForgeCluster`

| campo | tipo | contenuto |
|---|---|---|
| `outer` | `ForgeContour` | profilo esterno (ha `polygon`, `segments`, `role`, `area`, `bbox`) |
| `inners` | `list[ForgeContour]` | contorni chiusi dentro l'outer, senza lettura (un cerchio non è un foro, D15) |
| `label` | `str` | etichetta, base del nome file |
| `custom` | `dict` | dati aggiunti da un `data_injector` esterno (materiale, spessore, codice) |
| `detected` | `Optional[DetectedFeatures]` | overlay di un consumatore — `None` finché nessuno ci ha scritto (D44, D90) |
| `features(name)` | metodo | collezione `name` da `detected` — `[]` se `detected` è `None` o `name` non è stato scritto |
| `summary` | property | conteggio **grezzo**, sempre disponibile: `{nome}_count: len(items)` per ogni collezione in `detected` — `{}` se `detected` è `None` |
| `overlay_voids` | property | gli elementi dell'overlay con `is_void = True` e un `polygon`: vuoti del pezzo letti da un consumatore (D90) |
| `area` | property | outer − vuoti dell'overlay − inner a depth dispari + inner a depth pari (D89, D90) |
| `bbox` | property | `(minx, miny, maxx, maxy)` |

Un consumatore attacca la sua detection così (`forge.DetectedFeatures`):
`cluster.detected = cluster.detected or DetectedFeatures();
cluster.detected.attach("flange_view_hint", [...])`, poi la legge con
`cluster.features("flange_view_hint")`. Nessun nome è privilegiato (D44) — `DetectedFeature` (`typing.Protocol`, `source`/`confidence`)
è il contratto minimo, non imposto a runtime.

### `ForgeContour`

`role` (`ContourRole`), `polygon` (shapely), `segments` (primitive native),
proprietà `area` e `bbox`.

### `ContourRole` (ruoli del motore — vocabolario aperto)

Il motore conosce solo tre ruoli: `unknown`, `outer`, `inner` (MAP.md D47,
"roles out of core"; i ruoli di processo sono di snapbend, D88).
**Non è un universo chiuso**: chiunque può assegnare un ruolo che il motore non conosce (`hole`,
`frame`, `title_block`, `section`, …). Passa per `normalize_role()` — ripulito
in uno slug `[a-z0-9_-]` ≤ 64 char — e forge lo conserva senza sollevare; in
output lo scrive su un layer DXF **col nome dello slug** (o quello registrato
con `register_role_style`), colore grigio salvo override (`unknown` →
`Trash`, rosso). `role_str(role)` dà il valore stringa che il ruolo sia una
costante o uno slug (MAP.md D27 / D31).

**`forge.normalize_role(value) -> str`** e **`forge.is_structural_role(role) ->
bool`** sono pubbliche (MAP.md D30). `is_structural_role` (il predicato del
motore, solo `outer`/`inner`) è quello che `heal()` usa di default se non gli
passi `is_structural=...` — vedi `heal()` sopra. Un consumatore che marca la geometria **prima
di `heal`**: tiene i riferimenti agli `Edge` di `doc.edges`, imposta
`edge.role = forge.normalize_role("frame")` — resta fuori dal grafo per
default (nessun predicato lo riconosce strutturale), la geometria marcata
finisce in `trash_entities` col ruolo intatto e l'output la scrive sul layer
`frame`. È l'aggancio usato da `snapdraw` per cornice e cartiglio
(`SNAPDRAW.md`).

### `non_contour_candidates`

```python
forge.non_contour_candidates(doc: ForgeDocument, tolerance=None) -> list[Edge]
```

Edge di `doc.edges` che il criterio topologico di `heal()` escluderebbe dal
grafo dei contorni (branching + centroide fuori dal convex hull della sua
componente connessa, MAP.md D49) — **senza dire cosa siano**. `heal()` da solo
non assegna un significato a questi edge: li esclude e basta, restano in
`trash_entities` col ruolo che avevano. Un consumatore li interpreta (snapbend
`detect_flat`: dritto, estremi sul contorno esterno → `"bending"`).

Un consumatore che vuole
un'interpretazione propria (un bordo di feature in rilievo vista in pianta non
è una piega) chiama `non_contour_candidates(doc)` per ottenere la stessa lista
di candidati che `heal()` userebbe, senza duplicare il criterio, e decide da
sé come marcarli — poi assegna `edge.role` sugli `Edge` restituiti (sono
riferimenti dentro `doc.edges`, mutarli si riflette lì) **prima** di chiamare
`heal()` (vedi `ContourRole` sopra, SNAPDRAW.md, MAP.md D55).

| parametro | significato |
|---|---|
| `tolerance` | se `None`, ripresa da `doc.source_meta["tolerance"]` — stesso fallback di `heal()`. |

Lavora su `doc.edges` così come sono, **prima** che `heal()` fonda segmenti
sovrapposti/cocircolari e chiuda i gap minuscoli (i suoi primi passi interni,
D50/D52): su un disegno con duplicati o gap sotto tolleranza il risultato può
differire di poco da quello che `heal()` escluderebbe a conti fatti. Non è un
problema per l'uso previsto — decidere `edge.role` prima di `heal()` — perché
la parola finale su cosa resta nel grafo la dice comunque `heal()` stesso.

```python
for edge in forge.non_contour_candidates(doc):
    if <la tua logica decide che è un bordo di feature in rilievo>:
        edge.role = forge.normalize_role("flange_up")

result = forge.heal(doc)   # "flange_up" è già fuori dal grafo, mai indovinato "bending"
```

---

## 8. Il flusso completo, in ordine

```python
import forge, ezdxf

# 1. apri — unico punto che legge ezdxf
doc = forge.load_dxf("pezzo.dxf", tolerance=0.5)

# 2. valida l'input (opzionale ma consigliato)
check = forge.validate(doc)
if not check.is_valid:
    raise SystemExit(check.errors)

# 3. topologia
result = forge.heal(doc, label="P-1024")
# 4. (opzionale) una lettura di processo, fuori da forge — es. snapbend:
#   from snapbend.flat import detect_flat
#   detect_flat(result, "all")

# 5. controlla SEMPRE prima di renderizzare
if not result.is_valid:
    raise SystemExit(result.errors)

# 6. arricchimento CAM (opzionale — solo se hai un data_injector per i testi)
result = forge.inject(result, data_injector=leggi_cartiglio, snap_distance=5.0)

# 7a. render — un documento con tutte le parti
forge.to_dxf(result, doc).saveas("pezzo_healed.dxf")

# 7b. oppure render — un file per parte
result2 = forge.split_to_files(doc, "output/", label="P-1024")

# 8. metadati
forge.save_json(result, "pezzo.json")
```

Se qualcosa non torna su un file reale: `forge.inspect_file("pezzo.dxf")`.
