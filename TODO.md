# forge — TODO


Stato attuale: healing funzionante, export JSON/XDATA base, layer centralizzati.
Forge è un motore per comprendere geometria CAD 2D.

Nota: tutto quello che era ✅ fatto è stato tolto da qui (il record resta in
`MAP.md`, decisione per decisione). Questo file tiene solo quello che è
ancora aperto.

---

## RIPARTENZA — stato a fine sessione 2026-09-18 (seconda parte), da qui la prossima chat

Chiuso: `refactor/ellipse-primitive` (docs cleanup + `EllipseSeg`, due
commit) mergiato `--ff-only` in `main`, bump a `0.6.19`.

Primo pezzo di "funzioni geometriche" (MAP.md D46) — **rivisto una volta
dopo la prima versione**, su correzione di Federico: la prima stesura
ruotava il `ForgeDocument` grezzo e chiedeva un secondo `heal()`, e aveva
"outer" cablato nel nome della funzione invece che parametrico. Corretto:
una rotazione rigida non cambia la topologia, quindi `rotate_result`/
`rotate_cluster` ruotano DIRETTAMENTE un `ForgeResult`/`ForgeCluster` già
sano (poligoni, segmenti, `all_arcs`) — zero `heal()` di troppo, e
`rotate_cluster` è economico/ripetibile (pensato per un futuro nester che
prova molti angoli sulla stessa parte). "Quale entità allineare" è
`include_inners: bool` (outer di ogni cluster, più gli inner se True) — non
un filtro per `role` (verificato che `role` non è affidabile: un inner senza
ruolo proprio eredita quello del padre, `hierarchy._make_inner`). Dettaglio
completo, incluso perché la prima versione è stata scartata, in MAP.md D46.

`forge/tools/rotate.py`: `.rotated(angle, origin)` su ogni primitiva,
`segment_length`/`longest_segment`/`chord_angle_deg` in `core/geometry.py`,
`structural_segments`/`longest_structural_segment`/`rotate_cluster`/
`rotate_result`/`rotate_document`/`rotate_to_longest` — sperimentale, non
ancora in `forge.__init__`. Script dimostrativo
`scripts/17_rotate_to_longest_outer.py` su `tests/examples/try_for_rotation.dxf`,
un solo `heal()`, verificato manualmente (outer più lungo passa da 90° a 0°,
la diagonale interna resta intatta e ruota con tutto il resto). Suite verde:
722 passed.

**Working tree NON ancora committato dalla seconda revisione** — branch
`refactor/rotate-result-primitive`, checked out, contiene solo questa
revisione (il primo giro era già stato mergiato in `main` a `0.6.20`; questo
è un fix sopra quello). Da committare e chiedere a Federico prima di
mergiare, come da regola standard.

Resta aperto, discusso ma non affrontato:
- **Pippo che vuole sapere l'inclinazione di una flangia piegata** resta
  ambiguo fra due misure diverse: (a) l'orientamento 2D della bending line
  sullo sviluppo piatto (ora misurabile con `chord_angle_deg`) vs (b) il vero
  angolo di piega fisico, che in genere non si legge dalla sola direzione
  della linea — o è scritto altrove sul disegno, o si ricava per
  trigonometria confrontando la lunghezza vera (sviluppo) con quella
  proiettata in una vista che mostra la flangia piegata
  (`arccos(proiettata/vera)`) — ma questo richiede sapere quale edge dello
  sviluppo corrisponde a quale edge della vista, che è lavoro di
  framer/interprete, non di forge.
- **Idea collegata ma volutamente NON la stessa cosa**: "ruotare" una vista
  per farla combaciare con un'altra vista proiettata (per trasferire feature
  da una faccia allo sviluppo) è un problema di matching/registrazione fra
  due insiemi di punti (tipo ICP), non una semplice rotazione — molto più
  grosso, legato al "raggruppamento viste" di `framer` (`FRAMER.md`, ancora
  da scrivere) — non deciso se/come affrontarlo.
- Le annotazioni (`ForgeDocument.annotations`/`ForgeResult.annotations`) non
  sono ancora ruotate (nessun caso reale l'ha ancora richiesto) — se/quando
  serve, ogni sottoclasse di `Annotation` (`Note`, `Dimension`, `Leader`, ...)
  ha campi diversi da ruotare, non è un'estensione da un rigo.
- `cluster.detected`/`cluster.custom` non sono ruotati da `rotate_result` —
  overlay a schema libero (D44), forge non sa cosa contengono. Se hai già
  fatto `detect()` prima di ruotare, quei dati restano nelle coordinate
  vecchie — la guida è fare `detect()` DOPO aver ruotato, non prima.

**Fitting ellisse da punti grezzi** (generalizzare `arc_fit_tolerance` in
`tools/simplify_points.py` a un fit ellittico 5-DOF, per Smoother):
deliberatamente rimandato dopo D45 — la primitiva `EllipseSeg` ora esiste,
il fitting da una sequenza di punti grezzi è il "secondo passo" di cui
parlavamo, non ancora iniziato.

Per ripartire in una chat nuova: leggere questa sezione + `MAP.md` D45, poi
proseguire dall'inventario sopra.

---

## Limiti geometrici noti (da fixture reali, non bloccanti)

Quello che resta aperto dal vecchio triage regressioni (`REGRESSION_PLAN.md` /
`file_test_status.md`, cancellati: tutto il resto lì era già ✅ risolto e
committato — la storia sta nel git log e in `MAP.md`).

- **archi_si_no.dxf** — riconoscere gli archi come outer romperebbe le bending
  line (il grafo gira prima di quella decisione). Accettato così com'è; in
  futuro potrebbe diventare un comportamento opzionale.
- **F6.dxf** — edge case da gestire con le tolleranze; ci si aspetterebbe un
  warning sui nodi ambigui dal validator, non ancora emesso.
- **rect_special_countersink.dxf** — l'anello esterno del countersink
  potrebbe opzionalmente uscire su un layer a parte per un trattamento CAM
  diverso. Non bloccante.
- **rect_with_threaded_holes_geometric.dxf** — ipotesi: unificare a livello
  di disegno l'arco esterno di una filettatura rilevata geometricamente con
  il foro (reverse-geometric feature). Non bloccante, forse non necessario.
- **two_rects_with_bend.dxf** — una bending line con endpoint a ~10mm
  dall'outer non viene mai detectata: il filtro sulla distanza dal bordo è
  hard-coded a <1.0mm, alzare `bending_tolerance` non basta (quel parametro
  filtra solo la lunghezza minima).
- **6200013103_P1NoLineaPiega.dxf** (fixture cliente reale) — due bug noti:
  (a) il pezzo `_1` genera 1 sola bending line dove ce ne sono di più, causa
  non ancora indagata; (b) il cartiglio (`Cartiglio_sviluppo` esploso) viene
  rilevato come un cluster a sé. Il punto (b) non è più "da risolvere in
  forge": è esattamente il caso d'uso che motiva `Framer` (`FRAMER.md`), che
  lo elimina marcando `role="title_block"` prima di `heal`.
- **arc/arc oltre tolleranza** — `compute_gap_fixes` scarta ogni coppia con
  `distance > tolerance` anche per gli archi; esentarli quando i loro cerchi
  si intersecano davvero è una scelta di design da rivedere con un file
  reale (workaround oggi: alzare `tolerance`).

---

## PRIORITÀ MEDIA — migliora la qualità


### Apertura files

I files splittati non vengono aperti in Autocad, vengono aperti in sigmanest senza problemi e anche in edrawing. Se si aprono in autocad è meglio, perhcè così a lavoro posso guardarli e se i colleghi vogliono guardarli non rompono il cazzo che non si aprono.

### Hashing

creare una fingerprint geometrica per validare na forge part.

### Analisi

- [ ] **`DxfAnalyzer` — output CSV**
  - Esportare `summary_stats()` anche in CSV per analisi batch
  - Utile per misurare qualità dei fornitori

---

## PRIORITÀ BASSA — futuro

### Feature di tracciatura.
Simil_arcardini_segni_tracciati_stretto_healed --> questo file ha una serie di dentelli che partono da una linea orizzontele, che sono considerati parte del grafo giustamnete. vorrei aggiungere un parametro che sotto una certa distanza queste linee siano considerate solo dei segni di marcatura, completando il grafo solo con la linea orizzontale. Anche se ho degli inner che hanno distanza inferiore alla tolleranza di cui sopra, devono essere detectati come segni di incisione e posti sul layer 'Engrave'. probabilmente questa cosa va implementata nel modulo detect e può essere individuato il tutto solo passando detect() come facciamo con le bl che hanno la loro tolleranza.


### Implementazione nuovo formato:
Al momento in input posso avere solo dxf, ma mi sono messo in condizione di poter prendere anche svg o pdf. Da capire se implementare ad esempio almeno i pdf.



# I tools possibili sul motore geometrico:
Interrogazione (query)

measure() — distanze, aree, perimetri, bounding box
classify() — aperto/chiuso, convesso/concavo, presenza fori
compare() — similarity tra due parti (base per l'hashing/fingerprint che hai in lista)
validate() — check topologico: ci sono gap? self-intersections? geometrie degeneri?

Trasformazione

heal() — già ce l'hai
simplify() — riduzione punti, merge di segmenti collineari
offset() — kerf compensation, inset/outset contours
normalize() — porta tutto in coordinate canoniche (utile per comparison e hashing)

Analisi

nest_hint() — bounding box ottimale, orientamento suggerito per nesting
grain_direction() — suggerisce orientamento rispetto alla fibra del materiale
engrave_detect() — quello che hai in lista come "feature di tracciatura"

Decomposizione

split() — già ce l'hai
skeleton() — asse mediano (utile per bend detection avanzato)
region_decompose() — divide parti complesse in regioni semantiche


### Cos'è in poche parole:

Questa libreria è tipo un “riparatore di disegni tecnici”: legge un file DXF, controlla se le linee e le forme sono rotte o confuse, le sistema, trova le parti e gli spazi vuoti, e poi salva un disegno più pulito e ordinato.

In pratica
Ora: utile per CAD/CAM e automazione industriale.
Domani: può diventare un sistema di “interpretazione visiva di disegni” se aggiungi:
classificazione robusta,
feature detection,
model di topologia,
regole di business,
eventualmente ML/vision.


---

# linguette (`bridge_tabs`) — fatto (MAP.md D40); resta aperto solo questo

## Cosa resta parcheggiato, non toccare senza motivo

- **Problema 2**: dove vive la tassonomia hole/countersink/threaded/engrave/
  marking (oggi in `model/role.py`, concettualmente di `detect`) — bloccato
  da `core/heal.py`/`hierarchy.py` che leggono `STRUCTURAL_ROLES` per la
  topologia. Servirebbe un flag `structural: bool` invece di un elenco
  fisso, ma nessuno l'ha ancora disegnato.
- **Idea "detect dovrebbe usare il suo stesso contratto"**: `detect()` ha
  accesso diretto/privilegiato alla tassonomia dei ruoli invece di passare
  dagli stessi ganci (`role`) di un consumatore esterno come framer. Appena
  nata, non ancora messa a fuoco nemmeno da Federico. Collegata al problema
  2 ma non identica — risolvere il problema 2 potrebbe aiutare come effetto
  collaterale, non è garantito.
- **Meccanismo anti-rotazione pezzo staccato** (diverso da `tab`/`bridge_tabs`):
  un ponticello su un contorno singolo per evitare che un pezzo che si stacca
  giri libero e l'ugello ci sbatta contro — non collega un inner a un inner
  più annidato, è tutta un'altra cosa. Non ancora costruito, non ancora
  disegnato. Nome non deciso: forse "joint", di sicuro non "microjoint"
  (Federico l'ha escluso esplicitamente).

## Regola da ricordare per tutta questa roba

Mai parlare di layer DXF quando si parla di `role`/estensibilità di forge —
`label_map` è solo una comodità dell'adapter DXF (mappa layer→ruolo), il
meccanismo vero è `edge.role`, assegnabile per qualunque criterio
(raggio, posizione, geometria...), senza nessuna dipendenza da layer o
formato. In questa conversazione è già capitato di spiegare una cosa così a
Federico usando "layer" invece di "role", e si è arrabbiato parecchio — vedi
memoria `discuss-forge-in-role-terms-not-layer-terms`.
