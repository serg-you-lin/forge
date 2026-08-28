# Piano regressioni — triage di `file_test_status.md`

Stato al 2026-08-27. Le descrizioni per-file stanno in `file_test_status.md`.

## Cluster A — trash non materializzato  ✅ FATTO (commit + push su `refactor/structure`)

`to_dxf(..., include_trash=True)` + `_write_trash()` in `forge/pipeline/write.py`,
`write_open_segments()` in `forge/adapters/dxf/exporter.py`. Test: `test_writeback.py`
`TestWritebackTrash` (002/003/004).

Coperti: arc_open, F6, archi_si_no, leaf, leaf_convessa, rect_3sides, rect_centerline,
rect_with_special_layers (linea mark), two_rects_with_bend, Multifeature (geometria trash),
rect_with_trash (geometria).

## Cluster A-bis — annotazioni + INSERT  ✅ FATTO (`refactor/structure`)

Decisioni prese con l'utente:
- Nuovo layer forge **`Annotation`** (non di taglio, come `Trash`), colore ACI 7.
- `to_dxf` / `split` / `split_to_files` hanno il kwarg **`annotation_layer`**
  (default `"Annotation"`; `"Trash"` o altro nome → quel layer; `None` → layer
  sorgente originale).
- **Nessuna annotazione viene più scartata**: quelle non coperte da alcuna parte
  sono scritte comunque (in `split()` assegnate alla parte più vicina, come il
  trash). Vedi `write._write_annotations` / `_emit_annotation`.
- Le **DIMENSION / LEADER / MULTILEADER** non portano geometria nei campi DXF:
  `annotation_extractor` ne appiattisce l'immagine con `virtual_entities()`
  (ricorsione sugli INSERT delle frecce) in primitive pure —
  `data["strokes"]` (direttrici, linea di misura), `data["fills"]` (frecce),
  `data["texts"]` (testo alla posizione reale). `write._emit_annotation` le
  ri-materializza fedeli all'originale.
- Quote **senza blocco geometria** (dims non pre-renderizzate): `virtual_entities()`
  ritorna vuoto e l'auditor di ezdxf le CANCELLAVA. Fix in due punti:
  (1) `load_dxf` estrae le annotazioni **prima di `doc.audit()`** (e rifà il
  merge dopo l'explode, senza duplicati); (2) `_synthesize_dimension()`
  ricostruisce direttrici + linea di misura dai def-point per le quote lineari.
  Radiali/diametrali → fallback al solo valore `get_measurement()`.
- **LEADER senza representative point** (frecce di sezione): la posizione si
  ricava dal bounding box della geometria appiattita, non si scarta più.
- I layer forge **non strutturali** (`Trash`, `Annotation`) sono sempre ignorati
  da `DxfAdapter.to_edges()` al reload: la geometria di annotazione che forge
  scrive non deve tornare geometria di parte in un round-trip.
- **`explode_inserts` ora è `True` di default** in `load_dxf()`: un INSERT non
  esploso faceva sparire tutta la geometria (footgun).

### Architettura decisa (dopo discussione col dubbio "stiamo tornando indietro?")

Il **prodotto è il modello di fabbricazione** (`ForgeResult`). I `to_*` sono
renderer del modello; un futuro `to_svg` / `to_pdf` disegna lo stesso modello
senza rileggere la sorgente. **Nulla si perde** (riferimento dell'utente:
SigmaNest importa TUTTO — quote e spazzatura). Per non perdere, il modello è
abbastanza ricco:

- **Geometria classificata** → parti / fori / feature / bending / engrave.
- **Geometria non classificata** → `result.trash_entities` (segmenti puri,
  formato-indipendenti). È il concetto generale di "resto": ogni loader lo
  alimenta, ogni renderer sceglie se disegnarlo. NON è roba dell'adapter DXF.
- **Testi e quote** → `result.annotations` (list[Annotation]), **oggetto di
  dominio** (deciso dall'utente). `heal()` le copia dal ForgeDocument.
  Ogni `Annotation` porta sia i campi semantici (`value`, `dim_kind` per le
  quote — utili anche lato loader per il check scala/unità) sia la forma
  renderizzata (`strokes`/`fills`/`texts`, primitive pure) come fallback
  disegnabile in qualsiasi formato. `to_dxf` NON usa più `source_doc` per le
  annotazioni.

Whitelist residua: `to_dxf` ri-emette solo i tipi che forge modella; entità
fuori vocabolario (HATCH, IMAGE, TABLE, 3DFACE, XLINE…) restano fuori.
`load_dxf._warn_non_roundtrip_types()` emette un warning che le elenca —
niente più perdite silenziose. Passthrough generico: solo se un file reale lo
richiede.

Test: `test_writeback.py` `TestWritebackAnnotations` (001–008 + 003b),
`TestWritebackInsertExplodedByDefault`.
Coperti: gamba_tavolo, rect_with_trash, Multifeature (16 quote block-less + 4
leader di sezione). `scritta.dxf` → Cluster B.

## Cluster B — spline non chiuse / miste → DXF vuoto  ✅ FATTO (`refactor/structure`, non committato)

poly_spline_part, spline_line, spline_line_gap, spline_line_fori, **scritta.dxf**.

**Diagnosi:** il sotto-bug (1) era l'unica causa reale per 4 file su 5. Il
modello (heal + detect) era già corretto in tutti — `to_dxf` perdeva la parte
perché `write_segments()` ritornava `None` sui contorni che mischiano
`SplineSeg` con `LineSeg`/`ArcSeg` (o con più di una spline). Il sotto-bug (2)
("spline aperta non chiude il loop") **non si riproduce più** su spline_line /
spline_line_fori / poly_spline_part: heal li chiude tutti. Il sospetto del piano
su spline_line_fori ("inner/foro in gerarchia ma outer no") era superato:
l'outer c'è nel modello, lo perdeva solo l'exporter.

**Fix (Federico: "polilinea discretizzata mai; spline come primitiva nativa,
non copiata"):** `forge/adapters/dxf/exporter.py` — `write_segments()` sui
contorni misti non ritorna più `None` ma delega a `write_open_segments()`:
emette ogni `SplineSeg` come SPLINE nativa (ricostruita da control points /
knots / weights / degree / tangenti — stesso trattamento della spline chiusa
singola, `_add_spline()` estratto e condiviso) e i tratti line/arc come
LWPOLYLINE aperte con bulge. Gli endpoint coincidono: il loop chiuso è dato
dall'insieme delle entità, il grafo di reload lo ricuce (round-trip verificato:
area/perimetro/holes/inners identici su tutti e 5).

`test_golden.py::ROUNDTRIP_KNOWN_LOSSY` ora è vuoto (era
`{poly_spline_part, spline_line_gap}`). Suite: 516 passed / 2 xfail.

**Secondo bug trovato (Federico: "in alcuni casi la spline non è identica"):**
l'inversione di una B-spline per orientare il loop invertiva i soli control
point, non il vettore nodi né i pesi. Risultato: `SPLINE` emessa deformata
all'interno (endpoint ok perché una spline clamped interpola primo/ultimo CP),
deviazione fino a ~0.66 mm su `scritta`. Gli `approx_points` del modello erano
invertiti bene → area/perimetro/golden non lo vedevano. Fix: nuovo
`SplineSeg.reversed()` in `core/primitives/segments.py` che rimappa i nodi
(`U'[i] = a + b - U[m-i]`) e inverte pesi/tangenti; i 3 punti che invertivano
spline a mano (`parser._reverse_segment`, `parser._parse_spline`,
`adapter._spline_to_primitive`) ora passano tutti da lì. Verifica: ogni spline
ricostruita coincide con la sorgente entro 3e-7 (era 0.66); round-trip di
`scritta` ora esatto (area 38791.157 identica).

**spline_line_gap — nota:** heal a `tolerance` default 0.05 dà 0 parti perché il
gap reale è 0.2 mm fine-spline `(0, 49.8)` ↔ fine-linea `(0, 50)`, cioè 4× la
tolleranza. A `tolerance ≥ 0.2` (i golden usano 0.5) heala pulito. Il gap-fixer
funziona: `compute_gap_fixes` filtra sul gate `distance <= tolerance` come per
line/line, quindi non autochiude un buco 4× la tolleranza — comportamento
coerente, non un bug. Se serve, l'utente alza `tolerance`.

## Cluster C — threaded hole falsi positivi  ✅ FATTO (`refactor/structure`, non committato)

flangia_scantonata, maniglia, maniglia_no_raccordi.

**Diagnosi:** `is_threaded_hole` cercava un arco a ~270° concentrico al foro con
raggio *qualsiasi* purché maggiore. Su questi 3 file l'arco che matchava era
geometria dell'outer, non un anello filettato:
- flangia_scantonata: foro Ø160, bordo esterno = arco Ø360 a 293° concentrico
  (rapporto raggi 2.25);
- maniglia / maniglia_no_raccordi: foro Ø29.6 all'estremità raggiata del
  profilo, arco di raccordo Ø95 a ~275° concentrico (rapporto 3.2).

**Fix — solo la tolleranza (b), la (a) non è servita:** l'anello di cresta di
una filettatura reale ha raggio di *poco* maggiore del preforo — per le
filettature metriche il rapporto Ø-nominale/Ø-preforo è ~1.1–1.3 (M6:
6.0/5.0 = 1.2) e scala con la misura. Nuova costante
`THREADED_ARC_MAX_RADIUS_RATIO = 1.6` in `rules/thresholds.py`; `is_threaded_hole`
ora accetta l'arco solo se `radius < arc.radius <= radius * max_radius_ratio`.
Tutti e 3 i falsi positivi hanno rapporto ≥ 2.25, quindi cadono; il vero
positivo geometrico (`rect_with_threaded_holes_geometric`, rapporto 1.2) resta.
Escludere gli archi dell'outer dalla lista (fix a) avrebbe richiesto di
propagare il ruolo dentro `result.all_arcs` e non è necessario: se un file
reale mostrasse un anello filettato a ridosso di un raccordo dell'outer entro
1.6×, si riprende la (a) come difesa aggiuntiva.

Golden rigenerati: flangia_scantonata, maniglia, maniglia_no_raccordi
(threaded → plain; i golden portavano anche `origin`, campo rimosso da
`Hole.to_dict()` nel refactor — riallineato). Unit: `test_geometry.py`
`TestIsThreadedHole` 013–014. Suite: 516 passed / 2 xfail.

## Cluster D — engrave esportati come punti, non edge  ✅ FATTO (`refactor/structure`, non committato)

Fu, la_104, multifeature.

**Diagnosi:** confermata l'ipotesi del piano. `to_dxf` scriveva ogni incisione con
`write_segments()`, che chiude il contorno e delega a `segments_to_pts_with_bulge()`:
questa emette il *solo punto di start* di ogni segmento (per un loop chiuso l'endpoint
di ognuno è lo start del successivo, e la chiusura riporta all'inizio). Su una traccia
APERTA di un segmento l'endpoint finale non c'è → `add_lwpolyline([un punto], close=True)`
→ in CAD si vede un punto al posto della linea. Riprodotto su tutti e 3 i file con
`label_map={"MARK": "engrave"}`: 9/32/9 incisioni tutte come LWPOLYLINE `npts=1`.

**Fix:** nuovo `write_engrave_segments()` in `forge/adapters/dxf/exporter.py`; il loop
su `part.engrave_lines` in `write.py` lo usa al posto di `write_segments()`. Emette
**geometria nativa, una entità DXF per primitiva** — `LineSeg→LINE`, `ArcSeg→ARC`
(scambiando gli angoli per un ArcSeg CW, dato che in DXF l'ARC è sempre CCW),
`SplineSeg→SPLINE` nativa, `CircleSeg→CIRCLE`. **Mai LWPOLYLINE**, nemmeno per un run
di segmenti contigui e nemmeno se in ingresso era una polilinea (decisione utente:
"le polilinee non hanno senso per le incisioni"). Coerente con le bending line (emesse
come `LINE`) e con la scelta di modello "un'incisione è N segmenti separati". Arco
verificato: round-trip esatto (center/radius/angoli identici).

**Metadati:** `total_engrave_length` era **già corretto** — `inject._compute_part_metrics`
somma `eng.length` e lo mette in `part.custom["total_engrave_length"]`, presente in
`part.to_dict()` (FU 73.14, la_104 148.43, multifeature 29.57). Nessuna modifica.

Test: `test_special_layers.py` — `TestSpecialLayerNotTrash::test_003_*` /
`test_004_no_lwpolyline_on_engrave_layer`, nuova classe `TestEngraveArcNative`.
Suite: 522 passed / 2 xfail. Golden invariati.

## Cluster E — preservare linetype + colore nell'output  ⬜ DA FARE (nuovo, da multifeature)

Le linee tratteggiate escono continue. L'utente vuole che tipo-linea e colore siano
mantenuti nel DXF di output, e in prospettiva che il role possa essere dedotto anche
da linetype/colore. "Due piccioni con una fava."

## Non bloccanti / accettati così

- archi_si_no: accettato com'è (riconoscere archi come outer romperebbe le bending, il grafo gira prima).
- F6: edge case, gestibile con tolleranze/interfaccia.
- rect_special_countersink / rect_with_threaded_holes_geometric: anello esterno del
  foro su layer dedicato opzionale; reverse-geometric feature via detection semantica. Ipotesi.
- arc_open: archi di un outer che si intersecano dovrebbero dare "invalido" e non generare il file.








 

  Sulla tua domanda keep_annotation: ricordi mezzo giusto. Esisteva keep_trash (per la geometria trash), non
  keep_annotation. Il vecchio write() mutava il modelspace sorgente sul posto, quindi testo e quote restavano
  semplicemente perché nessuno li cancellava. Col nuovo to_dxf() che ricostruisce da zero, le annotazioni passano solo
  da _write_annotations, che le tiene solo se coperte da una parte. Quindi la decisione da prendere domani (Cluster
  A-bis) è: le annotazioni non coperte → sempre scritte, su layer originale o su Trash? Il tuo istinto ("finivano in
  trash") è coerente con come si comportava prima di fatto.

