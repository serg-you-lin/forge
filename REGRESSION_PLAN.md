# Piano regressioni — triage di `file_test_status.md`

Stato al 2026-08-27. Le descrizioni per-file stanno in `file_test_status.md`.

## Cluster A — trash non materializzato  ✅ FATTO (commit + push su `refactor/structure`)

`to_dxf(..., include_trash=True)` + `_write_trash()` in `forge/pipeline/write.py`,
`write_open_segments()` in `forge/adapters/dxf/exporter.py`. Test: `test_writeback.py`
`TestWritebackTrash` (002/003/004).

Coperti: arc_open, F6, archi_si_no, leaf, leaf_convessa, rect_3sides, rect_centerline,
rect_with_special_layers (linea mark), two_rects_with_bend, Multifeature (geometria trash),
rect_with_trash (geometria).

## Cluster A-bis — annotazioni + INSERT  ⬜ DA FARE

- **gamba_tavolo**, **rect_with_trash (testo)**: testo/quote stanno in `doc.annotations`,
  non in `trash_entities`. `_write_annotations` li scarta se non coperti da una parte.
  Da decidere con l'utente: c'era un `keep_annotation` storico? Le annotazioni non
  coperte vanno scritte sempre — su layer originale o su `Trash`?
- **scritta.dxf**: `load_dxf` trova 1 INSERT non esploso e scarta tutto. Serve
  `explode_inserts=True` (o esplodere di default).

## Cluster B — spline non chiuse / miste → DXF vuoto  ⬜ DA FARE

poly_spline_part, spline_line, spline_line_gap, spline_line_fori.
Due sotto-bug: (1) `write_segments` ritorna `None` per contorni misti SplineSeg+Line/Arc
→ parte persa; (2) spline aperta non chiude il loop → outer non riconosciuto.
Il round-trip (`test_golden.py` `TestGoldenWriteBack`) lo becca (1 parte → 0).
`spline_line_fori`: capire perché inner/foro sono in gerarchia ma outer no.

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








  Sui cluster: sì, li ritrovo. Ho scritto REGRESSION_PLAN.md nella root (non committato — committalo tu se vuoi che
  resti in git). Domani basta che mi dici "riprendi da REGRESSION_PLAN.md" e ripartiamo. Contiene i 5 cluster + stato, i  non-bloccanti, e ho già aggiunto il Cluster E nuovo che è emerso dal tuo commento su multifeature: linetype + colore
  da preservare nel DXF di output (le tratteggiate escono continue), con l'idea di dedurre il role anche da
  tipo-linea/colore.

  Sulla tua domanda keep_annotation: ricordi mezzo giusto. Esisteva keep_trash (per la geometria trash), non
  keep_annotation. Il vecchio write() mutava il modelspace sorgente sul posto, quindi testo e quote restavano
  semplicemente perché nessuno li cancellava. Col nuovo to_dxf() che ricostruisce da zero, le annotazioni passano solo
  da _write_annotations, che le tiene solo se coperte da una parte. Quindi la decisione da prendere domani (Cluster
  A-bis) è: le annotazioni non coperte → sempre scritte, su layer originale o su Trash? Il tuo istinto ("finivano in
  trash") è coerente con come si comportava prima di fatto.

  Buonanotte.