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

Test: `test_writeback.py` `TestWritebackAnnotations` (001–008 + 003b),
`TestWritebackInsertExplodedByDefault`.

Coperti: gamba_tavolo (7 quote + MTEXT), rect_with_trash (testo),
Multifeature (16 quote block-less + 4 leader di sezione).
`scritta.dxf` → spostato a Cluster B (vedi sotto).

### Aperto — passthrough entità non modellate

`to_dxf()` è una whitelist: ri-emette solo ciò che forge modella (parti, fori,
feature, bending, engrave, trash-geometria, testo/quote/leader). Entità fuori
vocabolario (HATCH, WIPEOUT, IMAGE, TABLE, 3DFACE, POINT, XLINE/RAY…) vengono
perse silenziosamente. Il vecchio `write()` mutava il modelspace sul posto e non
perdeva nulla "per caso". Da decidere: (a) accettare la copertura attuale — per
DXF di lamiera il vocabolario è di fatto completo; (b) passthrough generico
(copiare le entità sconosciute dal source doc in `to_dxf`); (c) almeno un
**warning** in `load_dxf` che elenca i tipi che non faranno round-trip.

## Cluster B — spline non chiuse / miste → DXF vuoto  ⬜ DA FARE

poly_spline_part, spline_line, spline_line_gap, spline_line_fori, **scritta.dxf**.
Due sotto-bug: (1) `write_segments` ritorna `None` per contorni misti SplineSeg+Line/Arc
→ parte persa; (2) spline aperta non chiude il loop → outer non riconosciuto.
Il round-trip (`test_golden.py` `TestGoldenWriteBack`) lo becca (1 parte → 0).
`spline_line_fori`: capire perché inner/foro sono in gerarchia ma outer no.
**scritta.dxf**: il modello è corretto (1 outer + 15 inner, lettere fatte di
line+spline), ma `to_dxf` scrive solo i 6 inner di sole `LineSeg`; i 9 misti
line+spline vengono scartati dal sotto-bug (1). NON è un problema di annotazioni:
la "scritta" è geometria esplosa, tutti gli inner.

## Cluster C — threaded hole falsi positivi  ⬜ DA FARE

flangia_scantonata, maniglia, maniglia_no_raccordi.
(a) escludere archi dell'outer dal conteggio anello filettato;
(b) tolleranza preforo↔arco: arco molto più grande del foro ⇒ non è threaded.

## Cluster D — engrave esportati come punti, non edge  ⬜ DA FARE

Fu, la_104, multifeature. Verificare anche che la lunghezza engrave arrivi nei metadati.
NB: `to_dxf` scrive engrave con `write_segments(close=True)` → probabile causa.

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

