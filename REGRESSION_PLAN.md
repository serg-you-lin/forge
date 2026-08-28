# Piano regressioni — triage di `file_test_status.md`

Stato al 2026-08-28. Le descrizioni per-file stanno in `file_test_status.md`.

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

## Cluster D — engrave esportati come punti, non edge  ✅ FATTO (`refactor/structure`, committato)

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

## Cluster F — bending detection  🟡 IN CORSO

### F1 — bending line scritte due volte (Bending + Trash)  ✅ FATTO (`refactor/structure`, non committato)

**Sintomo (il caso che ha fatto perdere 2 ore all'utente):** su
`6200012964_lineette_bastarde.dxf` le 2 bending line da parte a parte *sono*
detectate e scritte su layer `Bending`, **ma la stessa geometria resta anche in
`result.trash_entities`** e `to_dxf` la riscrive come LWPOLYLINE su `Trash`.
A CAD si vedevano solo le entità Trash, sovrapposte alle Bending.

Verifica sul modello: le 2 corde da 303.6 mm comparivano identiche in
`part.bending_lines` **e** in `result.trash_entities`.

**Causa:** `pipeline/detect.py::_detect_bending` promuoveva il proxy con
`part.bending_lines.append(...)` **senza rimuoverlo da `result.trash_entities`**.
La lane label_map (`_detect_labeled`) traccia `classified_ids` e filtra la trash
alla fine; la lane geometrica no.

**Perché sembrava "regressione recente":** il doppione nel modello è vecchio
(latente). Prima del **Cluster A** la trash non veniva materializzata in output,
quindi non si vedeva. Cluster A ha iniziato a scriverla → il doppione è diventato
visibile. Non c'entra né l'epsilon (`0f2ed5c`, isolato dietro `if not loops:`) né
il refactor di struttura.

**Fix:** `_detect_bending` raccoglie gli `id()` dei proxy promossi e li toglie da
`result.trash_entities` alla fine — stesso pattern di `_detect_labeled`.
`6200012964`: trash 6→4 (restano i 4 segmenti-leaf da 0.3 mm sugli archi),
nessuna entità doppia in output. Suite: 522 passed / 2 xfail (invariata).
Fixture rigenerate con modifica semantica (rimozione LWPOLYLINE Trash duplicate):
`Linee_piegatura_healed.dxf`, `linee_di_piegatura_interne_healed.dxf`,
`rect_with_special_layers_healed.dxf`.

### F2 — lineette_bastarde: i 4 monconi da 0.3 mm  ✅ NON È PIÙ UN BUG (`refactor/structure`, non committato)

L'appunto diceva che i 4 segmenti-leaf da 0.344 mm sugli angoli raccordati
finivano su `Bending` invece che in trash. **Sul branch attuale non è più
così:** il file dà `1 outer + 2 bending line (corde da 303.6 mm) + 4 monconi in
`trash_entities``, esattamente l'esito voluto — lo ha sistemato F1 (commit
`5570dec`). L'utente vedeva 6 entità su Bending perché stava guardando
`6200012964_lineette_bastarde_healed.*`, artefatti locali generati prima di F1 e
mai rigenerati (nessun test li legge; provenivano da una API morta
`dxf_forge.io.exporter`). Ora rigenerati / rimossi.

`tests/real/test_layers.py::TestLineetteBastarde` è il guard vero (2 bending + 4
trash) ed è verde.

**Collegato — `test_loops.py::TestSplitArcStubs`:** i due `@unittest.expectedFailure`
erano fuorvianti. `test_un_solo_loop` faceva `self.assertEqual(len(self.outer), 1)`
con `self.outer` mai assegnato → xfallava per `AttributeError`, non testava nulla.
Il `LoopFinder` nudo sul grafo esatto *davvero* non pota gli stub di grado 3 (0
loop) — ma è un limite del solo loop finder: la pipeline completa lo recupera
(clustering endpoint + riparazione angoli). Test riscritto per verificare
l'esito del prodotto: `forge.heal(ForgeDocument(edges=...))` → 1 part, area
corretta, 4 stub in `trash_entities`. `@expectedFailure` rimossi.

### F3 — nessun contorno esterno chiuso = risultato invalido  ✅ FATTO (`refactor/structure`, non committato)

**Decisione utente:** se il file non compone nessun outer chiuso (endpoint che
non si congiungono entro tolleranza, anche dopo il ponte retto di fallback), il
risultato **non è un pezzo** — va dichiarato invalido, come il modelspace vuoto,
e nessun file va generato.

**Fix:**
- `HealStep._build_hierarchy`: dopo `builder.build()`, se `not parts` →
  `errors.append(...)` + `is_valid = False`. La trash resta popolata per la
  diagnostica.
- `to_dxf()` / `split()`: `raise ValueError` se `not result.is_valid` — niente
  più output di sola spazzatura. `split_to_files()` già usciva presto su
  `not result.is_valid`.

Effetto: `arc_open` a tolleranza default (gap arco/arco ~0.26 mm > 0.05) →
invalido, `to_dxf` solleva. A `tolerance ≥ 0.3` il gap si chiude, 1 part
regolare (`_solve_arc_arc` prolunga entrambi gli archi all'intersezione dei
cerchi — già funzionava). `rect_3sides` (3 lati di un rettangolo, aperto per
costruzione) ora è invalido, come atteso.

Test: `test_writeback.py::TestWritebackTrash::test_005_no_output_when_no_closed_outer`.
`test_004_open_trash_not_closed` spostato su `two_rects_with_bend` (che ha una
traccia trash aperta con una parte valida). Suite: 526 passed / 0 xfail.

### F4 — limiti noti (⬜ non bloccanti, servono dati/decisione cliente)

- **two_rects_with_bend** — BL interna con endpoint a ~10 mm dall'outer: mai
  detectata. `_detect_bending` vuole entrambi gli endpoint a `< 1.0` dal bordo
  (hard-coded); `bending_tolerance` filtra solo la lunghezza minima, non la
  distanza dal bordo. Alzare `bending_tolerance` non recupera il caso.

`AMBIGUO`: le 8 `bending_lines` sono **corrette** (confermato dall'utente), non è
over-detection.

## Non bloccanti / accettati così

- archi_si_no: accettato com'è (riconoscere archi come outer romperebbe le bending, il grafo gira prima).
- F6: edge case, gestibile con tolleranze/interfaccia.
- rect_special_countersink / rect_with_threaded_holes_geometric: anello esterno del
  foro su layer dedicato opzionale; reverse-geometric feature via detection semantica. Ipotesi.
- **arc/arc oltre tolleranza**: `compute_gap_fixes` scarta ogni coppia con
  `distance > tolerance`, archi come le linee. Esentare gli archi i cui cerchi
  si intersecano davvero è una scelta di design ("perché gli archi sì e le
  linee no") — si rivede con un file reale. Workaround: alzare `tolerance`.
- **archi auto-intersecanti / che non si toccano nemmeno prolungati**: fuori
  scope; oggi assorbiti da F3 (nessun loop → invalido).





