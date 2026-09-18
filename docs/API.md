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
3. [Elaborazione e render](#3-elaborazione-e-render) — `heal` (core), `detect` / `anchor_annotations` / `inject` (tools), `to_dxf` / `split` (io), `heal_and_detect` / `split_to_files` (recipes)
4. [Export](#4-export) — `save_json`, `to_json`, `save_xml`, `to_view_model`, `to_svg`, `save_svg`
5. [Metadati XDATA](#5-metadati-xdata) — `write_metadata_to_dxf`, `read_metadata_from_dxf`, `set_schema`
6. [Ispezione / debug](#6-ispezione--debug) — `inspect_dxf`, `inspect_document`, `inspect_result`, `inspect_file`
7. [Utilità](#7-utilità) — `extract_forge_texts`, `extract_texts_from_msp`
8. [Tipi di dominio](#8-tipi-di-dominio)
9. [Il flusso completo, in ordine](#9-il-flusso-completo-in-ordine)

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
    label_map=None,
    ignore_layers=None,
    linetype_map=None,
    color_map=None,
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
| `label_map` | `{nome_layer: work_type}` — assegna il **ruolo** agli `Edge` già in fase di traduzione. Chiavi case-insensitive. `work_type` che forge conosce: `outer`, `hole`, `bending`, `inner`, `countersink`, `threaded_hole`, `engrave`, `marking`. Un valore diverso (`frame`, `title_block`, `section`, …) **non è un errore**: viene ripulito in uno slug e conservato sul ruolo, forge lo tratta come non strutturale e in output lo scrive su un layer col nome dello slug (`unknown` → `Trash`) — vocabolario aperto, MAP.md D27 / D31. **Lane autoritativa** — se decide lei, `linetype_map`/`color_map` non intervengono più su quell'entità. |
| `ignore_layers` | lista di layer da escludere dalla geometria. |
| `linetype_map` | `{nome_linetype: work_type}` (es. `{"DASHED": "bending"}`) — seconda lane di classificazione, sullo **stile della linea** invece che sul layer. Si applica solo alle entità che `label_map` non ha già classificato. Stesso vocabolario `work_type` di `label_map`. Il linetype confrontato è quello **effettivo**: se l'entità è `ByLayer`, viene risolto al linetype del layer che la contiene, non lasciato `"ByLayer"`. |
| `color_map` | `{colore: work_type}` (es. `{"cyan": "engrave"}`) — come `linetype_map` ma sul **colore ACI** dell'entità. Chiavi: nome standard (`red`, `yellow`, `green`, `cyan`, `blue`, `magenta`, `white`/`black`, `gray`/`grey`, `lightgray`/`lightgrey`, `pink`), intero ACI, o stringa numerica (`"4"`). Anche qui il colore confrontato è quello effettivo — un'entità `color=256` (BYLAYER) viene risolta al colore del layer, non lasciata BYLAYER. |

**Ritorna** un `ForgeDocument`. La diagnostica sul file grezzo (audit, INSERT non
esplosi, Z≠0, duplicati rimossi, tipi non ri-materializzabili in output) finisce
in `doc.warnings`; `forge.validate(doc)` la rilancia.

**Solleva** `FileNotFoundError`, `EnvironmentError` (DWG senza `ODA_PATH`),
`RuntimeError` (conversione DWG fallita), o le eccezioni di lettura di `ezdxf`.

```python
doc = forge.load_dxf("pezzo.dxf", tolerance=0.5,
                     label_map={"Piega": "bending", "MARK": "engrave"})
for w in doc.warnings:
    print("loader:", w)
```

Quando il disegno non usa layer dedicati ma porta l'intenzione nello stile
della linea (pieghe tratteggiate, marcature colorate su un layer qualsiasi):

```python
doc = forge.load_dxf(
    "pezzo.dxf",
    linetype_map={"DOT": "bending", "DASHED": "bending"},
    color_map={"cyan": "engrave"},
)
```

Vedi `14_style_classification.py` per un esempio completo (i tre classificatori
isolati uno per uno, su un file reale in `tests/examples/`).

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
     (non la cartella — se ODA è in `ODAFileConverter 27.1.0\`, il path deve
     includere `\ODAFileConverter.exe`);
   - oppure `ODAFileConverter` raggiungibile dal `PATH` di sistema.

Impostare `ODA_PATH`:

| SO | comando |
|---|---|
| Windows, permanente | `setx ODA_PATH "C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"` — poi **riapri il terminale** |
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
    label_map=None,
    ignore_layers=None,
    source_path="",
    linetype_map=None,
    color_map=None,
) -> ForgeDocument
```

Costruisce un `ForgeDocument` da un `modelspace` `ezdxf` **già aperto**. Utile per
i test o per geometria generata a mano. **Non** fa audit / upgrade / sanitize: si
assume che il `msp` sia già pronto. `linetype_map`/`color_map` funzionano come in
`load_dxf()` — vedi sopra.

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
| `entities` | lista di dict, uno per entità geometrica. `type` supportati: `line` (`start`, `end`), `arc` (`center`, `radius`, `start_angle`/`end_angle` **in gradi**, `ccw`), `circle` (`center`, `radius`), `polyline` (`points`, `closed`), `spline` (`control_points`, `knots`, `degree`, più `weights`/`fit_points`/`closed` opzionali — stessi campi di `SplineSeg`), `ellipse` (`center`, `major_axis` come **vettore** dal centro, più `ratio`/`start_param`/`end_param`/`ccw` opzionali — stessi campi di `EllipseSeg`, stessa parametrizzazione del gruppo DXF ELLIPSE; default = ellisse piena). `role` è opzionale su ogni entità — stesso vocabolario di `label_map` (`outer`, `hole`, `bending`, …); un valore diverso è conservato come slug di consumatore, non un errore. |
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
result = forge.heal_and_detect(doc, label="sviluppo_cono")
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

Provato da un caso reale (`bendly`, che lo usa per portare gli sviluppi che
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
poligono outer valido e non vuoto, area > 0, fori contenuti nell'outer.

Viene **già chiamata automaticamente da `heal()`** — la usi a mano solo se
costruisci un `ForgeResult` per altre vie.

---

## 3. Elaborazione e render

`heal` è l'atto del motore (`forge/core/`); `detect` / `anchor_annotations` /
`inject` sono stadi opzionali su un `ForgeResult` (`forge/tools/`, il caller
sceglie quali e in che ordine); `to_dxf` / `split` sono renderer del modello
(`forge/io/`); `heal_and_detect` / `split_to_files` sono le scorciatoie della
via del 90% (`forge/recipes.py`). Tutto resta accessibile come `forge.<nome>`.

### `heal`

```python
forge.heal(doc: ForgeDocument, tolerance=None, label="", source_file="",
           is_structural=None) -> ForgeResult
```

Il passo difficile: ricostruzione della topologia. Lavora su `doc.edges`, zero
`ezdxf`. Chiude i gap, individua le linee di piega candidate, trova i loop chiusi,
costruisce l'albero di contenimento outer / inner.

`heal()` **non classifica i fori** (D15): consegna solo `ForgeCluster(outer,
inners=[ForgeContour...])`. La promozione a `Hole` è di `detect(features="holes")`.

| parametro | significato |
|---|---|
| `tolerance` | se `None`, ripresa da `doc.source_meta["tolerance"]` (quella passata a `load_dxf`). |
| `label` | etichetta del pezzo, finisce in `cluster.label` e nei metadati. |
| `source_file` | nome file sorgente, finisce nei metadati. |
| `is_structural` | `Callable[[str], bool] \| None` — "questo ruolo è topologia di contorno di pezzo?", usato per decidere quali `Edge` già etichettati (da `label_map`) restano nel grafo prima della ricerca loop. `heal()` da solo conosce solo `outer`/`inner`; senza questo parametro un ruolo manifatturiero (`"hole"`, ...) è trattato come non strutturale ed **esce** dal grafo (heal lo segnala con un warning). Passa `forge.tools.manufacturing_role.is_structural` per farlo riconoscere — `heal_and_detect()`/`split_to_files()` lo fanno già in automatico. |

`label_map`/`linetype_map`/`color_map` **non sono parametri di `heal`** — vanno
passati a `load_dxf()`, che assegna i ruoli agli `Edge`.

**Ritorna** un `ForgeResult`. Se non si forma nessun contorno esterno chiuso,
`result.is_valid` è `False` e `result.errors` è popolato (la `trash_entities`
resta piena per la diagnostica).

**Solleva** `TypeError` se non gli passi un `ForgeDocument`.

```python
result = forge.heal(doc, tolerance=0.5, label="P-1024")
```

---

### `detect`

```python
forge.detect(
    result: ForgeResult,
    features=None,                      # None/() | "all" | {"holes","bending","engrave"}
    *,
    max_drill_diameter=32.1,            # HOLE_DIAMETER_THRESHOLD
    bending_tolerance=1.0,
    engrave_tolerance=1.0,
    deduplicate_boundary_open=True,
    boundary_tolerance=0.05,
) -> ForgeResult
```

Il passo semantico: classifica le feature dentro le parti già trovate da `heal()`.

`detect(result)` **nudo** fa solo il minimo: la lane `label_map`/`linetype_map`/
`color_map` (autoritativa, decisa in `load_dxf()`) e la pulizia della topologia.
I contorni circolari restano `inners`, nessun `Hole` — è il default per il
taglio laser.

Le lane geometriche sono **opt-in** via `features`:

| chiamata | cosa fa in più |
|---|---|
| `detect(result, "holes")` | promuove a `Hole` i contorni circolari con Ø `< max_drill_diameter` (`plain` / `countersink` / `threaded`); i Ø maggiori restano contorni interni |
| `detect(result, "bending")` | linee di piega geometriche (segmenti da bordo a bordo) |
| `detect(result, "engrave")` | inferenza incisioni (oggi no-op, D13) |
| `detect(result, "all")` | tutte e tre |

**Muta** `result` in-place (parti, `trash_entities`, `classified_entities`) **e lo
ritorna** — la catena resta esplicita: `result = forge.detect(result, "all")`.
Ogni feature trovata si attacca a `cluster.detected` (D44), leggibile con
`cluster.features("holes"|"bending_lines"|"engrave_lines")` — `[]` se
`detect()` non è mai girato. `forge.describe_features(cluster)` dà il
conteggio ricco per tipo (fori per tipo, pieghe raggruppate, lunghezza
incisioni).

| parametro | significato |
|---|---|
| `features` | quali lane geometriche eseguire. `None`/`()` = nessuna. `"all"` o l'iterabile `{"holes","bending","engrave"}`. |
| `max_drill_diameter` | parametro di processo: sotto questo Ø un contorno circolare è un foro da punta, sopra resta contorno interno. Default `32.1` mm. |
| `bending_tolerance` | lunghezza minima di una traccia perché sia considerata piega. |
| `engrave_tolerance` | riservato all'inferenza geometrica delle incisioni (oggi no-op). |
| `deduplicate_boundary_open` | rimuove dalla trash i segmenti aperti che coincidono col bordo outer. |

```python
result = forge.heal(doc)
result = forge.detect(result, "all", max_drill_diameter=25.0)
```

---

### `heal_and_detect`

```python
forge.heal_and_detect(
    doc: ForgeDocument,
    tolerance=None, label="", source_file="",
    features="all",
    max_drill_diameter=32.1,
    bending_tolerance=1.0, engrave_tolerance=1.0,
    deduplicate_boundary_open=True, boundary_tolerance=0.05,
) -> ForgeResult
```

`heal()` + `detect()` in un colpo solo — la via del 90% dei chiamanti. A
differenza di `detect()` nudo, qui `features="all"` è il default: fori, pieghe e
incisioni vengono classificati. `detect()` viene saltato se `heal()` non produce
parti valide (il `result` torna comunque, con `is_valid=False` e gli errori
popolati). I primi parametri sono quelli di `heal()`, gli altri quelli di
`detect()`.

`heal()` e `detect()` separati restano disponibili: un renderer o un nesting tool
possono volere la sola topologia, senza classificazione feature.

```python
doc    = forge.load_dxf("pezzo.dxf", label_map={"Piega": "bending"})
result = forge.heal_and_detect(doc, label="P-1024")
if not result.is_valid:
    raise SystemExit(result.errors)
```

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
) -> ezdxf.document.Drawing
```

Materializza il modello in un **documento DXF nuovo** (R2010). Non rilegge mai
entità dalla sorgente: `source_doc` serve solo a riportare gli header
(`$INSUNITS`, `$MEASUREMENT`). Testi e quote arrivano da `result.annotations`.

| parametro | significato |
|---|---|
| `filter_cluster` | `callable(ForgeCluster) -> bool` — scrive solo le parti che passano. |
| `include_trash` | `True` (default): la geometria non classificata va sul layer `Trash`. Un operatore CAM deve poter vedere ogni entità del disegno di partenza. |
| `annotation_layer` | `"Annotation"` → layer forge dedicato; `"Trash"` o altro nome → quel layer; `None` → layer originale della sorgente. Nessuna annotazione viene mai scartata. |
| `role_styles` | override esplicito, per ruolo, di colore/linetype/lineweight (vedi `RoleStyle` sotto). Agisce sul layer — tutto ciò che forge scrive è BYLAYER. `None` (default) = nessun cambiamento rispetto alla palette di `rules/palette.py`. |

```python
# la cornice (ruolo "frame", assegnato da un consumatore come framer) in nero
forge.to_dxf(result, doc, role_styles={"frame": forge.RoleStyle(color=(0, 0, 0))})
```

**Ritorna** un `Drawing` `ezdxf`. Sta a te fare `doc_out.saveas(...)`.

**Solleva `ValueError`** se `result.is_valid` è `False` — non genera un file di
sola spazzatura. **Controlla `result.is_valid` prima di chiamarlo.**

```python
if result.is_valid:
    forge.to_dxf(result, doc).saveas("out.dxf")
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
    on_cluster=None,
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
| `on_cluster` | `callable(cluster, doc_out)` — hook per parte, prima che il `Drawing` entri nella lista. |

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
    linetype:   str | None = None                     # nome standard ezdxf, es. "DASHED"
    lineweight: float | None = None                   # mm
    layer_name: str | None = None                     # nome layer/gruppo di output
```

Override, indipendente dal formato, dell'aspetto visivo di un ruolo in
output — noto al motore (`"outer"`, `"inner"`) o assegnato da chiunque
altro, `detect()` incluso (`"hole"`, ...) o un consumatore esterno
(`"frame"`, `"title_block"`, ...) — nessuno dei due è privilegiato. Ogni
campo lasciato `None` resta il default di forge per quel ruolo. Passato a
`to_dxf`/`split` come `role_styles={ruolo: RoleStyle(...)}` — dizionario
esplicito del chiamante, stesso idioma di `label_map`, riusabile su più
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
`forge.set_schema()` per i metadati. Un consumatore (framer, bendly, ...)
lo chiama una volta al proprio setup invece di ricostruire `role_styles=`
a ogni chiamata; `forge.tools.manufacturing_role` lo usa per registrare i
propri colori di default (`hole` magenta, `bending` rosa, ...) — stesso
meccanismo pubblico, nessun trattamento privilegiato per i ruoli di
`detect()`. `role_styles=` passato a una singola chiamata resta possibile e
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
) -> ForgeResult
```

Flusso completo multi-pezzo + salvataggio su disco: `heal → detect → split →
.saveas()` per cluster. **È l'unica funzione di forge che scrive su disco.**
Il nome file è `f"{cluster.label}.dxf"`, dove `cluster.label` è quello che assegna
`namer(i, cluster)`; senza `namer` diventa `f"{label}_P{i+1}"` (es. `batch_P1.dxf`).

**Ritorna** il `ForgeResult` (per poterci fare `save_json` dopo). Se il risultato
non è valido, ritorna il result senza scrivere niente.

```python
result = forge.split_to_files(doc, "output/", label="batch")
forge.save_json(result, "batch.json")
```

---

### `inject`

```python
forge.inject(
    result: ForgeResult,
    data_injector=None,
    texts=None,
    tolerance=0.1,   # accettato per compat, non più usato
) -> ForgeResult
```

Arricchimento CAM **opzionale**. **Muta** `result.clusters[i].custom` in-place e
ritorna il `result`. Fa **una cosa**: se passi `data_injector` —
`callable(cluster, list[str]) -> dict` — gli passa i testi che ricadono dentro
l'outer di ogni parte e mette il dict restituito in `cluster.custom` (codice pezzo,
materiale, spessore, …). Senza `data_injector`, `inject()` non fa nulla.

`texts` va passato come **`list[ForgeText]`** (`content` + `position`) — il
filtraggio per parte è geometrico, servono le posizioni. Si ottiene con
`forge.extract_forge_texts(msp)`, **non** con `extract_texts_from_msp` (che
ritorna stringhe nude). Il `data_injector` riceve comunque `list[str]`.

I **conteggi delle feature** (fori per tipo, pieghe, lunghezza incisioni) NON si
fanno più qui: vengono da `cluster.summary` (conteggio grezzo, sempre
disponibile) + `tools.detect.describe_features(cluster)` (il dettaglio ricco
per i tipi noti di forge — MAP.md D8, D44). `save_json` / `save_xml` li
fondono automaticamente; per una detection *tua*, che forge non può
conoscere, passa `extra_metadata` (vedi sotto).

```python
import ezdxf
msp = ezdxf.readfile("pezzo.dxf").modelspace()

def leggi_cartiglio(cluster, testi):
    return {"material": next((t for t in testi if t.startswith("S")), "S275JR")}

forge.inject(result, data_injector=leggi_cartiglio,
             texts=forge.extract_forge_texts(msp))
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
una detection tua (es. una `FlangeViewHint`) che `cluster.summary`/
`describe_features()` non possono conoscere. Struttura:

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
      "bending_lines": 2, "countersink_count": 0, "threaded_holes_count": 4,
      "total_engrave_length_mm": 0.0,
      "area_mm2": 12345.67, "holes_count": 6, "inner_contours_count": 1,
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

> `to_nester_input(result) -> list[dict]` esiste ancora (`label`, `bbox`,
> `outer_coords`, `holes_coords` per parte) ma è **sperimentale**, fuori da
> `__all__` — scritto per un nester mai realizzato (MAP.md D18). Per serializzare
> la geometria usa `to_view_model`.

Tutta la geometria è **discretizzata a polilinee** (`points: [[x, y], …]`):
archi, cerchi, spline appiattiti. I fori portano anche `center` + `diameter` per
disegnare un cerchio vero. Coordinate nel sistema del sorgente (Y in alto).

```python
vm = forge.to_view_model(result)
vm["clusters"][0]["outer"]        # {"role": "outer", "color": "#00ff00", "points": [...], "closed": true}
vm["clusters"][0]["holes"][0]     # + hole_type, diameter, center, source, confidence
vm["palette"]                  # {"outer": "#00ff00", "hole": "#ff00ff", ...}
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
    holes_as_circles=True,
    stroke_width=None,        # None = auto (diagonale bbox / 400)
    size=None,                # None = niente width/height → scala al contenitore
    units=None,               # "mm" = SVG in scala reale per import CAM/laser 1:1
) -> str
forge.save_svg(result, path, **kwargs) -> None
```

Renderer SVG del modello (MAP.md D12) — **per visualizzazione** (UI/report/
anteprima). Un colore per ruolo (stessa palette semantica del DXF di output). La
Y viene ribaltata (modello Y-su → SVG Y-giù). Una parte = un `<g data-cluster="…">`.
Costruito sopra `to_view_model`.

`size=None` (default) **non** scrive `width`/`height` sull'`<svg>`: l'immagine è
vettoriale e scala a riempire il contenitore (o la finestra del browser) — la
zoomi quanto vuoi. Passa `size="800"` per fissare la larghezza in px.

`units="mm"` produce un SVG **in scala reale** (`width="…mm"`, padding e sfondo a
zero) per chi importa SVG in un software laser/CAM che vuole 1 unità = 1 mm.
**Attenzione:** archi, cerchi e spline restano discretizzati a polilinea — per un
taglio ad alta fedeltà (fori a tolleranza, cerchi lisci) usa `to_dxf`, non l'SVG.

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
gli `Edge` (ruolo, primitiva, endpoint, `closed_path`), le annotazioni, e il
grafo dei nodi (nodi totali, loop degeneri, nodi di branching, estremi liberi).
"Cosa ha capito l'adapter."

```python
forge.inspect_result(result, coords=False) -> None
```
**Livello 3** — un `ForgeResult`: validità, warning/errori, e per ogni parte
outer/inner/holes (tipati)/bending/engrave/custom, più `trash_entities`,
`classified_entities`, annotazioni. "Cosa ha prodotto forge."

```python
forge.inspect_file(path, tolerance=0.05, label_map=None,
                   run_heal=True, run_detect=True, entities=True, coords=False,
                   linetype_map=None, color_map=None) -> None
```
Orchestratore: apre il file e stampa i tre livelli in fila. `run_heal=False` /
`run_detect=False` per fermarti a un livello precedente. `linetype_map` /
`color_map` come in `load_dxf()`.

```python
forge.inspect_file("pezzo.dxf", label_map={"Piega": "bending"})
forge.inspect_file("pezzo.dxf", linetype_map={"DOT": "bending"}, color_map={"cyan": "engrave"})
```

---

## 7. Utilità

### `extract_forge_texts`

```python
forge.extract_forge_texts(msp) -> list[ForgeText]
```

Estrae i testi da un `modelspace` `ezdxf` come `ForgeText` (`content` +
`position`). **È questo** l'argomento `texts` di `inject()` — il filtraggio per
parte è geometrico e servono le posizioni. Non gestisce `INSERT` — vanno esplosi
prima (`load_dxf` lo fa; qui riapri il file solo per i testi).

### `extract_texts_from_msp`

```python
forge.extract_texts_from_msp(msp) -> list[str]
```

Come sopra ma ritorna solo le stringhe, senza posizione. Per chi vuole i testi e
basta — **non** passabile a `inject()`.

---

## 8. Tipi di dominio

### `ForgeDocument`

Prodotto da `load_dxf` / `document_from_msp`. È il contratto tra l'adapter e il
core: dopo di lui, `ezdxf` non si tocca più.

| campo | tipo | contenuto |
|---|---|---|
| `edges` | `list[Edge]` | geometria tradotta in primitive pure — input di `heal()` |
| `annotations` | `list[Annotation]` | testi e quote della sorgente |
| `source_meta` | `dict` | `$INSUNITS`, `$MEASUREMENT`, `tolerance`, `label_map`, `ignore_layers`, `linetype_map`, `color_map` |
| `source_path` | `str` | percorso del file |
| `warnings` | `list[str]` | diagnostica del loader sul file grezzo |

### `Annotation`

`kind` (`"TEXT"` | `"MTEXT"` | `"DIMENSION"` | `"LEADER"` | `"MULTILEADER"`),
`position` `(x, y)`, `data` `dict` (contenuto testuale + forma renderizzata come
primitive pure per le quote).

### `ForgeText`

Prodotto da `extract_forge_texts(msp)`, consumato da `inject()`. `content` (`str`,
già ripulito) + `position` (shapely `Point`, per il containment check per parte).

### `ForgeResult`

Prodotto da `heal()`, arricchito da `detect()` / `inject()`.

| campo | tipo | contenuto |
|---|---|---|
| `clusters` | `list[ForgeCluster]` | un elemento per contorno esterno chiuso |
| `is_valid` | `bool` | **controllalo prima di `to_dxf` / `split`** |
| `warnings` / `errors` | `list[str]` | diagnostica |
| `trash_entities` | `list` | geometria non classificata (proxy con `segments`, formato-indipendenti) |
| `annotations` | `list[Annotation]` | copiate da `heal()` dal `ForgeDocument` |
| `classified_entities` | `list[ClassifiedEntity]` | feature senza classe dedicata (marking, work_type custom) |
| `all_arcs` | `list[ArcSeg]` | tutti gli archi — usato dal detector fori filettati |
| `label_map` | `dict` | configurazione di sessione, non serializzata |
| `cluster_count` | property | `len(clusters)` |

Metodo `to_dict()` → dizionario JSON-ready (usato internamente dagli export).

### `ForgeCluster`

| campo | tipo | contenuto |
|---|---|---|
| `outer` | `ForgeContour` | profilo esterno (ha `polygon`, `segments`, `role`, `area`, `bbox`) |
| `inners` | `list[ForgeContour]` | aperture interne non classificate come foro |
| `label` | `str` | etichetta, base del nome file |
| `custom` | `dict` | dati aggiunti da un `data_injector` esterno (materiale, spessore, codice) |
| `detected` | `Optional[DetectedFeatures]` | overlay di `detect()` — `None` finché nessuno ci ha scritto (D44) |
| `features(name)` | metodo | collezione `name` da `detected` — `[]` se `detected` è `None` o `name` non è stato scritto. Legge `"holes"` (`list[Hole]`), `"bending_lines"` (`list[BendingLine]`), `"engrave_lines"` (`list[Engraving]`), o un nome custom attaccato da un tool esterno |
| `summary` | property | conteggio **grezzo**, sempre disponibile: `{nome}_count: len(items)` per ogni collezione in `detected` — `{}` se `detected` è `None`. Vedi `tools.detect.describe_features(cluster)` per il conteggio ricco per tipo (`plain_holes_count`, `countersink_count`, `threaded_holes_count`, `bending_lines` gruppi, `total_engrave_length`, `total_marking_length`) |
| `area` | property | outer − fori − inner |
| `bbox` | property | `(minx, miny, maxx, maxy)` |

Un consumatore esterno attacca la sua detection con lo stesso meccanismo di
`detect()`: `cluster.detected = cluster.detected or DetectedFeatures();
cluster.detected.attach("flange_view_hint", [...])`, poi la legge con
`cluster.features("flange_view_hint")`. Nessuno dei due è privilegiato nello
schema (D44) — `DetectedFeature` (`typing.Protocol`, `source`/`confidence`)
è il contratto minimo, non imposto a runtime.

### `ForgeContour`

`role` (`ContourRole`), `polygon` (shapely), `segments` (primitive native),
proprietà `area` e `bbox`.

### `ContourRole` (ruoli del motore — vocabolario aperto)

Il motore conosce solo tre ruoli: `unknown`, `outer`, `inner` (MAP.md D47,
"roles out of core" — prima l'enum includeva anche i sei ruoli
manifatturieri, spostati in `tools/manufacturing_role.py`: vedi sotto).
**Non è un universo chiuso**: chiunque — `detect()` incluso, non è
privilegiato — può assegnare un ruolo che il motore non conosce (`hole`,
`frame`, `title_block`, `section`, …). Passa per `normalize_role()` — ripulito
in uno slug `[a-z0-9_-]` ≤ 64 char — e forge lo conserva senza sollevare; in
output lo scrive su un layer DXF **col nome dello slug** (o quello registrato
con `register_role_style`), colore grigio salvo override (`unknown` →
`Trash`, rosso). `role_str(role)` dà il valore stringa che il ruolo sia una
costante o uno slug (MAP.md D27 / D31).

**`forge.normalize_role(value) -> str`** e **`forge.is_structural_role(role) ->
bool`** sono pubbliche (MAP.md D30). `is_structural_role` (il predicato del
motore, solo `outer`/`inner`) è quello che `heal()` usa di default se non gli
passi `is_structural=...` — vedi `heal()` sopra e MAP.md D47 per il predicato
esteso (`tools.manufacturing_role.is_structural`, quello che
`heal_and_detect()` inietta). Un consumatore che marca la geometria **prima
di `heal`**: tiene i riferimenti agli `Edge` di `doc.edges`, imposta
`edge.role = forge.normalize_role("frame")` — resta fuori dal grafo per
default (nessun predicato lo riconosce strutturale), la geometria marcata
finisce in `trash_entities` col ruolo intatto e l'output la scrive sul layer
`frame`. È l'aggancio usato da `framer` per cornice e cartiglio
(`FRAMER.md`).

### `tools.manufacturing_role` (vocabolario di `detect()`, non del motore)

`forge.tools.manufacturing_role` (non in `__all__`, importa esplicitamente)
tiene `HOLE`/`COUNTERSINK`/`THREADED_HOLE`/`BEND`/`ENGRAVE`/`MARKING`
(stringhe semplici, stessi valori di prima: `"hole"`, `"countersink"`, ...),
`is_structural(role) -> bool` (il predicato ESTESO — outer/inner + i tre
ruoli foro — quello che `heal_and_detect()`/`split_to_files()` passano a
`heal(is_structural=...)` automaticamente), e registra i propri colori/nomi
layer di default con `register_role_style` al proprio import — nessun
trattamento privilegiato, stesso meccanismo pubblico di un consumatore
esterno (MAP.md D47).

---

## 9. Il flusso completo, in ordine

```python
import forge, ezdxf

# 1. apri — unico punto che legge ezdxf
doc = forge.load_dxf("pezzo.dxf", tolerance=0.5,
                     label_map={"Piega": "bending"})

# 2. valida l'input (opzionale ma consigliato)
check = forge.validate(doc)
if not check.is_valid:
    raise SystemExit(check.errors)

# 3. + 4. topologia + semantica in un colpo
result = forge.heal_and_detect(doc, label="P-1024")
# separati, se ti serve la sola topologia:
#   result = forge.heal(doc, label="P-1024")
#   result = forge.detect(result, "all")   # detect(result) nudo non classifica i fori

# 5. controlla SEMPRE prima di renderizzare
if not result.is_valid:
    raise SystemExit(result.errors)

# 6. arricchimento CAM (opzionale — solo se hai un data_injector per i testi)
result = forge.inject(result, data_injector=leggi_cartiglio, texts=...)

# 7a. render — un documento con tutte le parti
forge.to_dxf(result, doc).saveas("pezzo_healed.dxf")

# 7b. oppure render — un file per parte
result2 = forge.split_to_files(doc, "output/", label="P-1024")

# 8. metadati
forge.save_json(result, "pezzo.json")
```

Se qualcosa non torna su un file reale: `forge.inspect_file("pezzo.dxf")`.
