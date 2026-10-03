# forge — TODO


Stato attuale: healing funzionante, export JSON/XDATA base, layer centralizzati.
Forge è un motore per comprendere geometria CAD 2D.

Nota: tutto quello che era ✅ fatto è stato tolto da qui (il record resta in
`MAP.md`, decisione per decisione). Questo file tiene solo quello che è
ancora aperto.

---

## I FILI APERTI — si riparte da qui

Lista corta e in ordine, scritta perché una sessione nuova non ricominci da capo
dimenticando quella prima. Il dettaglio di ognuno sta più sotto o in `MAP.md`.

1. **Pushare.** ✅ fatto insieme al rewrite (D81), 2 ottobre.
2. **`anonymize`** — **si prosegue in snapdraw** (deciso il 2 ottobre): il lavoro
   sul cartiglio e sui loghi è lettura del disegno, quindi è di snapdraw. Lo
   stato lasciato qui sotto vale come punto di partenza.
    — ✅ costruito (D77) e ✅ **uscito da forge (D80)**: non è più
   `forge.tools.anonymize`, è un progetto a sé (`dxf-anonymize`, repo privata,
   locale in `GitHub/dxf-anonymize/`), perché una dipendenza dichiarata in
   `pyproject.toml` di un consumer (snapbend, snapdraw) esporrebbe comunque nome
   e scopo dello strumento a chi guarda quella repo, anche con `dxf-anonymize`
   stessa privata. Dipende da forge (oracolo `heal()`), mai il contrario; si
   installa una volta con `pipx` e si lancia da terminale, nessun progetto lo
   nomina nei suoi file tracciati. `scan` aggregato su più disegni e `--find
   PAROLA...` ci sono già (fatti prima dell'estrazione, portati con sé).
   **Manca ancora:** installarla con `pipx` sul sistema (la repo privata è già
   su GitHub). **Aperto dal primo lotto vero (33 disegni, 2 ottobre):**
   `dxf-anonymize` ora legge i DWG (via ODA), scrive sul posto solo dopo che
   `heal()` ha verificato, e il conteggio con `whole_value` è corretto — tutto
   **non committato** in quella repo, insieme a `remove_title_logos` (dato il
   riquadro del cartiglio da snapdraw: toglie i retini lì dentro, svuota i
   blocchi logo — inseriti nel cartiglio, con retini, ≤ metà del cartiglio — e
   rifiuta di scrivere se cambia un solo edge di forge fuori dal riquadro) —
   ora **committato** in `dxf-anonymize`.
   Lotto pulito in `anonimizzati/drw_0001…0033.dxf`, originali intatti, fatto
   con `dxf-anonymize batch CARTELLA --rules regole.json --out ...` (le
   regole con i nomi del cliente in un JSON locale, accanto ai disegni).
   Cancellare *tutto* dentro il cartiglio: provato e **scartato** (toglieva il
   cartiglio). **Ancora aperto:** loghi senza retini (solo archi/cerchi, due
   disegni), e i 6 disegni dove snapdraw non è sicuro del cartiglio.
   **snapdraw `read_titleblock` alla prova del lotto:** trova il cartiglio in
   27/33, ma i campi letti sono quasi tutti sbagliati — `drawn_by` aggancia
   "DISEGNO DI PROPRIETÀ", `date` prende le etichette vicine o "PEZZA",
   `drawing_number` ha letto "Group" in 8 disegni. Nomi e date li hanno trovati
   le regole sul testo, non il cartiglio.
3. **I 32 disegni che la suite usa e non ha in git** — ✅ **IN GIT, D79 risolto**
   `anonymize scan` aggregato su 261 stringhe distinte (D78): zero percorsi
   assoluti, un nome di persona, una sigla sui tre stili di quota, ripuliti su
   8 file, `heal()` identica, suite 887.
   
   Non con un `git add -f` in una cartella ignorata: `tests/data/` è diventata
   la radice tracciata (D79, `.gitignore` la dichiara da anni inutilizzata). Un
   disegno è pubblicabile **perché sta lì**, non perché qualcuno si ricorda una
   flag. `tests/examples/` resta locale (originali cliente, `islands/`,
   `111-23/`). 534 spostati con `git mv`, 32 nuovi + 2 golden, suite 887 dopo
   il move.
4. **Il rewrite della history** — ✅ **fatto (D81)**, 2 ottobre: un force-push,
   albero di oggi identico, `audit_names.py --history` pulito.
5. **`detect_flat()` → snapbend** — direzione già decisa; bloccata dal flag
   `structural: bool` al posto di `STRUCTURAL_ROLES` (vedi "Problema 2" in
   fondo).
6. **Estrazione dei loop planari (half-edge/DCEL)** — l'unica cosa in lista che
   cambia di categoria il motore; dettaglio nei "limiti geometrici noti".
7. **Due cose piccole dalla roadmap del preventivo** (step 0 e 1 di
   `ROADMAP.md`): `snap_distance` anche su `inject()` — ✅ fatto (D82). Il
   controllo quota-vs-geometria misurata **non è di forge** (D69): forge dà già
   `measured_value`, `display_text` e `references`, il confronto col numero
   scritto si fa in snapdraw — da portare nel TODO di snapdraw.
   `scripts/13_production_splitter.py` importa ancora
   `extract_forge_texts`, che non esiste più: lo script è rotto e **passerà con
   ogni probabilità in snapbend** (Federico, 2 ottobre), da riscrivere lì su
   `inject(snap_distance=...)`.
8. **Il rename `forge` → `snapforge`** — `naming_convention.md` (non tracciato) è
   un piano scritto e **mai eseguito**: nome umano `SnapForge`, identificatore
   tecnico `snapforge` per repo, cartella, package e `import`, stessa regola per
   `SnapDraw` e `SnapBend`. Tocca `pyproject.toml`, la cartella del package, ogni
   `import forge`, i docs, il remoto su GitHub e i consumer. Da decidere se farlo
   prima della 1.0.0 (dopo è un breaking change per chi importa) e se nel
   frattempo `naming_convention.md` entra in git come piano o resta locale.
9. **Il view-model non discretizza più archi e cerchi** (Federico, 3 ottobre:
   "è ridicolo") — **riapre D12**, che li appiattiva in polilinee. Un cerchio
   resta cerchio (centro + raggio), un arco resta arco (centro, raggio, angoli):
   l'SVG ha `<circle>` e gli archi nei `path`, quindi `to_svg` non perde niente,
   e un renderer esterno disegna l'entità vera. Misurato: su `anch_07`/`anch_08`
   la discretizzazione rende `to_view_model` **più grande del DXF sorgente**
   (≈300k token contro 79k). Le spline restano da decidere: l'SVG ha solo
   Bézier cubiche, una NURBS qualsiasi non ci entra esatta.
   **Coordinate arrotondate al terzo decimale** nelle uscite di lettura
   (view-model, SVG, la futura lettura per un agente). Non in `to_dxf`, che va
   a una macchina e resta esatto — da confermare con Federico.
   Quando si fa, diventa un `D##` in `MAP.md`.
10. **`to_text`: la lettura per un agente AI** — ✅ **fatto, sperimentale
   (D84)**, 3 ottobre. Resta aperto: la prova del valore, in snapdraw dopo la
   sua detection (è nel TODO di snapdraw); se sopravvive, entra in `__all__` e
   in `API.md`. Sui fogli di viste il peso è ancora quasi tutto cornice,
   tacche e retini non classificati: si abbassa quando snapdraw li etichetta.

---

## `anonymize` — ripulire un disegno cliente per farne un fixture

**Costruito (D77).** `forge/tools/anonymize.py` + `forge/adapters/dxf/tags.py`,
11 test in `tests/unit/test_anonymize.py`. Quello che segue è il perché, che
resta valido come guida all'uso; quello che resta da fare è passarci i 32
fixture del punto 3.

```
python -m forge.tools.anonymize scan  disegno.dxf [--all]
python -m forge.tools.anonymize clean disegno.dxf --map mappa.json \
        [--out fixture.dxf] [--also golden1.json golden2.json] [--whole-value]
```

Il bisogno vale per forge **e per tutti i consumer**: i test si fanno per forza
con disegni di clienti, quindi serve un passaggio che li renda pubblicabili. Vive
in `forge/tools/anonymize.py` con la lettura/scrittura del formato in
`adapters/dxf/tags.py`; fuori da `forge.__all__`, i consumer lo importano da
`forge.tools.anonymize`.

**Perché non un round-trip attraverso forge.** `load_dxf` → `heal` → `to_dxf`
restituisce la *lettura* di forge, non il file: spline strane, entità fuori
contorno, il `Trash` — cioè esattamente ciò che rende quel disegno un caso di
prova — non tornerebbero uguali. Il fixture deve restare il file, byte per byte,
tranne le stringhe che identificano.

**Quindi passata testuale diretta sul DXF, non `ezdxf`.** Un DXF ASCII è una
sequenza di coppie (codice, valore), una per riga: si riscrivono solo i valori
stringa, i numeri non si toccano mai e la struttura resta allineata. I gruppi che
possono portare un'identità: `1`/`3`/`304` (testi), `2` (nomi di tabella e di
blocco, compresi gli stili di quota), `6`/`7`/`8` (linetype, stile, layer),
`300`-`309` e `1000` (testo arbitrario e XDATA), `9` (variabili d'intestazione
tipo `$LASTSAVEDBY`, `$PROJECTNAME`, `$HYPERLINKBASE`), `999` (commenti).

**forge è l'oracolo.** Dopo la pulitura: `heal()` prima e dopo, e numero di
cluster, aree, perimetri, bbox e `trash` devono coincidere. Se cambia un numero
lo strumento ha sbagliato e si rifiuta di scrivere.

Due trappole viste sul campo, da gestire dentro lo strumento:

- una stringa si **sostituisce, non si cancella**: togliere il testo del
  cartiglio cambia quello che vedono `annotations` e `inject()`;
- se un golden cita quel testo (`"display_text": …`) va riallineato nello stesso
  passaggio, altrimenti il test rompe; e un layer rinominato va rinominato in
  *tutti* i posti dove compare (record di tabella, blocchi, gruppo 8 di ogni
  entità).

Due modalità:

```
python -m forge.tools.anonymize scan  disegno.dxf
python -m forge.tools.anonymize clean disegno.dxf --out fixture.dxf --map mappa.json
```

`scan` stampa tutto quello che è scritto dentro, da leggere con l'occhio: è la
parte che non si può automatizzare, perché un **codice** ha una forma e un
pattern lo trova, un **nome** no. Prova che serve: il nome di uno studio usato
come nome di uno stile di quota in uno dei disegni, trovato solo dumpando 576
stringhe e leggendole una per una (ora sostituito). `clean` applica una mappa (sigle inventate generate,
o scritta a mano) e dice cosa ha sostituito. **La mappa resta locale**: è l'unico
file che lega il fixture all'originale.

Quello che NON è dato cliente, verificato con Federico: la **marcatura** — il
testo dentro il disegno che ripete il numero del pezzo — la scrive Advance Steel
per ogni pezzo tagliato, è il nome del normalino e può stare in git. In D76 era
stata sostituita per eccesso di zelo; non è un danno (ora il marchio coincide col
nome del fixture) ma la regola per il futuro è: la marcatura si tiene.

---

## Due cose decise a voce e mai scritte

### `to_dxf` su un `ForgeResult` non valido — ✅ fatto (D83)

`allow_invalid=True` su `to_dxf` **e** `to_svg` (alcune macchine prendono SVG):
di default si vede tutto, chi consegna a una macchina passa `False`. snapbend lo
fa già nei tre `forge.to_dxf` di `snapbend/io/dxf.py` (modifica locale, **non
committata**: quel file è ancora non tracciato in snapbend). In snapbend 3 test
falliscono da prima, non per questo: `tests/test_to_dxf_integration.py` usa
`cluster.bending_lines`, che non esiste più.

### il "pnger": forge sa già mostrare, solo non in raster

Sono due cose diverse. **Renderizzare il modello** — che geometria c'è, con
ruoli e colori — è di forge, e forge lo fa già due volte: `to_svg` e
`to_view_model`. Un SVG lo apre qualsiasi browser, è scalabile, e per un umano è
meglio di un PNG. **Comporre un'immagine per un lettore preciso** — ritagliare,
togliere le quote perché un modello leggerebbe i numeri invece delle forme — è
del consumatore: quelle scelte hanno bisogno di `ViewLayout` e dei ruoli
`FRAME`/`TITLE_BLOCK`/`CONSTRUCTION`, che forge non ha.

Quindi: il raster serve quando il lettore è una macchina, non quando sei tu.
`to_svg` resta la via umana di forge e **non** si aggiunge `to_png` adesso; in
snapdraw il pnger si riscrive su Pillow (una ventina di righe, e matplotlib esce
di scena con la sua dipendenza non dichiarata). Se un domani il raster serve
anche a forge, è un `to_png` sottile sopra lo stesso view-model, nell'extra
`raster` che il `pyproject` già dichiara. L'interattivo è un viewer, cioè un'app
a parte (MAP.md D16).

---

## Audit dati cliente prima della 1.0.0 — resta il rewrite della history

D76 ha rifatto l'audit e il "zero sospetti" di D73/D75 era cieco in tre punti
(path quotati da git, `\b` che non scatta dentro gli underscore, e il contenuto
dei disegni mai letto). Ora `python scripts/audit_names.py --strict` controlla
quattro cose — nomi, prosa e codice, **dentro i disegni**, nomi di sole cifre —
ed esce 0. Dentro i DXF tracciati c'erano un percorso di rete con nome cliente e
commessa, il nome di una stampante d'ufficio e cinque codici pezzo come nomi di
layer e testi di cartiglio: tutto sostituito, suite ferma a 876. Il dettaglio
sta in MAP.md D76.

**3 ottobre — blocchi definiti e mai usati.** `anch_01…06` portavano ancora la
*definizione* di un logo cancellato a mano (geometria del logo e nome di una
ditta nel nome del blocco), invisibile in CAD, leggibile nel testo. `audit_names`
non l'ha visto perché il nome non ha la forma di un codice. Tolti con il nuovo
`dxf-anonymize purge` (`heal()` e golden di ancoraggio identici). **Solo
nell'HEAD:** i commit vecchi li hanno ancora, e Federico ha deciso di **non**
riscrivere la storia per questo adesso — da riconsiderare nell'audit della
1.0.0.

Restano due cose:

1. **Mettere in git i 32 disegni che la suite usa e non ha.** Letti e puliti in
   D78 — `anonymize scan` su tutti e 32, aggregato in un elenco unico di 261
   stringhe distinte, lette a occhio: zero percorsi assoluti, un nome di persona
   in `$LASTSAVEDBY` e una sigla di tre lettere su tre stili di quota,
   sostituiti su **otto** file (gli stessi disegni stanno in più cartelle, e la
   pulitura segue la stringa, non la lista dell'audit). `heal()` identica su
   tutti, suite 887.

   `python scripts/audit_fixtures.py` li elenca (3,2 MB, tutti puliti secondo
   l'audit): senza di loro 61 golden su 114 fanno `skipTest` su un clone pulito,
   e la suite resta verde mentre gira meno di quello che mostra. Decisione presa
   (i golden devono girare anche da chi scarica il progetto), manca solo lo
   `git add -f` — `tests/examples/` e' ignorato in blocco, quindi serve il
   `-f`:

   ```
   python scripts/audit_fixtures.py --list > fixtures.txt
   git add -f --pathspec-from-file=fixtures.txt
   python scripts/audit_fixtures.py --strict   # deve dire "tutti in git"
   ```

   `--pathspec-from-file` e non `$(cat ...)`: un fixture ha uno spazio nel nome
   (`flangia semplice.DXF`) e la sostituzione di shell lo spezzerebbe in due
   percorsi che non esistono. `fixtures.txt` si cancella subito dopo.

2. **Il rewrite della history** (il punto 6 del piano). I codici sono nei commit
   gia' pushati: `git filter-repo` su tutta la history + un solo force-push,
   dopo che tutto il resto e' committato. Cambia ogni SHA, quindi un eventuale
   clone va riclonato; GitHub puo' tenere gli oggetti vecchi raggiungibili per
   SHA per un po'. Da rifare contro la lista di D76 e D77, non solo contro i nomi
   di file: nei commit vecchi ci sono i codici che stavano **dentro** i disegni,
   le due sigle ripulite in D77 e la sigla ripulita in D78 — quest'ultima stava
   in tre disegni **già tracciati e pushati**, e `audit_names.py --strict` li
   dava per puliti perché cerca codici e quella è un nome. E non basta riscrivere
   il contenuto dei file: almeno un **messaggio di commit** porta un codice pezzo
   nell'oggetto, quindi serve anche un `--message-callback`.

Due cose viste di passaggio, da decidere quando capita:

- `tests/examples/cartella_3/` — il nome della cartella non e' un codice pezzo e
  l'audit non lo segnala, ma non e' neanche un nome inventato. La cartella non
  e' tracciata e nessun test la usa (il `la_104.DXF` che i test usano e' quello
  in `tests/examples/`), quindi non e' un problema di git: e' da guardare.
- `scripts/13_production_splitter.py` (non versionato, "fuori serie"
  in SCRIPTS.md) ha un percorso assoluto con un codice pezzo nel `CONFIG`.
  Finche' resta non versionato non entra in git, ma se un giorno lo si porta
  alla nuova API quel percorso va via prima.

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

Branch `refactor/rotate-result-primitive` mergiato `--ff-only` in `main`,
bump a `0.6.21`. `main` è la verità corrente, niente da committare.

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
  snapdraw/interprete, non di forge.
- **Idea collegata ma volutamente NON la stessa cosa**: "ruotare" una vista
  per farla combaciare con un'altra vista proiettata (per trasferire feature
  da una faccia allo sviluppo) è un problema di matching/registrazione fra
  due insiemi di punti (tipo ICP), non una semplice rotazione — molto più
  grosso, legato al "raggruppamento viste" di `snapdraw` (`SNAPDRAW.md`, ancora
  da scrivere) — non deciso se/come affrontarlo.
- Le annotazioni (`ForgeDocument.annotations`/`ForgeResult.annotations`) non
  sono ancora ruotate (nessun caso reale l'ha ancora richiesto) — se/quando
  serve, ogni sottoclasse di `Annotation` (`Note`, `Dimension`, `Leader`, ...)
  ha campi diversi da ruotare, non è un'estensione da un rigo.
- `cluster.detected`/`cluster.custom` non sono ruotati da `rotate_result` —
  overlay a schema libero (D44), forge non sa cosa contengono. Se hai già
  fatto `detect_flat()` prima di ruotare, quei dati restano nelle coordinate
  vecchie — la guida è fare `detect_flat()` DOPO aver ruotato, non prima.

**Fitting ellisse da punti grezzi** (generalizzare `arc_fit_tolerance` in
`core/primitives/fitting.py` a un fit ellittico 5-DOF, per Smoother):
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
- **senza_linea_piega.dxf** (fixture cliente reale) — due bug noti:
  (a) il pezzo `_1` genera 1 sola bending line dove ce ne sono di più, causa
  non ancora indagata; (b) il cartiglio (`Cartiglio_sviluppo` esploso) viene
  rilevato come un cluster a sé. Il punto (b) non è più "da risolvere in
  forge": è esattamente il caso d'uso che motiva `snapdraw` (`SNAPDRAW.md`), che
  lo elimina marcando `role="title_block"` prima di `heal`.
- **arc/arc oltre tolleranza** — `compute_gap_fixes` scarta ogni coppia con
  `distance > tolerance` anche per gli archi; esentarli quando i loro cerchi
  si intersecano davvero è una scelta di design da rivedere con un file
  reale (workaround oggi: alzare `tolerance`).
- **outer che non si chiude su viste vere, ricorrente** — non più un caso
  isolato: tre disegni reali indipendenti, stesso sintomo in superficie
  ("outer vero, tutto in trash") ma **cause diverse** — non era un bug solo:
  - **foglio A** (snapdraw MAP D5, mesi fa): pezzi veri non chiudono in `heal`,
    tanti archi e linee di costruzione — causa non ancora ri-analizzata con
    gli strumenti di oggi.
  - **foglio B** ✅ **risolto, MAP.md D49** — non era un gap né una
    duplicazione da fondere: il file ha due viste indipendenti sullo stesso
    foglio (il piano e, sopra, una vista sottile dello spessore), e
    `NonContourEdgeDetector` calcolava il convex hull su TUTTO il documento
    invece che per singola forma connessa — la vista piccola perdeva 3 dei
    suoi 4 lati veri, scambiati per corde interne perché "dentro" l'hull
    dominato dalla vista grande. Fix: hull per componente connessa
    (`Graph.connected_components()`, nuovo). Ora chiude in 2 cluster puliti.
  - **foglio di rilievo C** (snapdraw, survey reale): di 3 viste sullo stesso
    foglio, 1 sana, 2 no. Sintomo diverso dal **foglio B**: `result.trash_entities` qui non
    sono ~10 frammenti ma **1682**, con lunghe catene di segmenti minuscoli
    (~0.3-0.5mm ciascuno) che sembrano un profilo curvo scomposto in tanti
    tratti retti che non richiudono l'anello — non ancora capito se manchi
    un singolo anello di congiunzione in fondo alla catena o se la
    frammentazione stessa sia il problema. Non ancora riverificato con gli
    strumenti di oggi (D49/D50) — segmenti di un profilo curvo hanno
    direzioni leggermente diverse l'uno dall'altro, quindi `D50` (che
    richiede la STESSA retta esatta) probabilmente non li tocca; da
    verificare comunque su un file reale prima di escluderlo.

  Non ancora deciso se/quando riaprire un'indagine dedicata sui fogli **A**
  e **C** — `refactor/heal-branch-topology` (D49, D50) ha chiuso il
  caso più semplice dei tre, non gli altri due.

- **linea tracciata a spezzoni sovrapposti** ✅ **risolto, MAP.md D50** —
  pattern distinto dal precedente (non viste multiple, una singola riga
  ridisegnata più volte quasi sullo stesso tratto). Trovato e riprodotto su
  `tests/examples/dedup.dxf`: un trapezio coi lati tracciati a 3-4 frammenti
  sovrapposti mandava tutto in `polygonize` invece di chiudere.
  `core/healing/normalizer.merge_collinear_overlaps()` (nuovo, gira in
  `heal()` prima di tutto il resto) fonde 2 o più frammenti che si toccano
  o si sovrappongono sulla stessa retta esatta, mai fra edge con un ruolo
  già assegnato — quel filtro sul ruolo resta l'unica vera protezione,
  perché decide qualcosa che la geometria da sola non può decidere (un
  ruolo da role_rules è dato di dominio, D30). Il dettaglio di due giri di
  falsi positivi prima di arrivare qui (e del bug di arrotondamento che
  in realtà li causava, non il contatto o il numero di frammenti) è in
  MAP.md D50, non ripetuto qui.

- **outer che non chiude su un grafo densamente ramificato — causa distinta
  dal punto precedente, non va nello stesso branch** — trovato su
  `tests/lab/3d_1.dxf` (una vista isolata da un disegno con più viste,
  export Creo via ODA File Converter, 259/423 entità sono SPLINE). Qui non
  c'è nessun gap: la componente connessa più grande ha 70 nodi, zero
  estremi liberi anche a 1mm di tolleranza (provato 0.1/0.3/0.5/1.0, zero
  differenza sul risultato), ma **64 di quei 70 nodi sono a grado>2**.
  L'euristica di `loop_finder.py` ("prosegui nella direzione più collineare
  all'arrivo") regge i bivi isolati visti finora, ma non un grafo dove il
  91% dei nodi è un bivio: il perimetro vero finisce interamente in
  `Trash` (bounding box del Trash identica a quella dell'intero disegno),
  mentre le feature interne (fori, bozze), chiudendosi bene da sole,
  emergono come cluster di primo livello invece che come inner — non è un
  bug di hierarchy, è che l'outer che dovrebbe contenerle non viene mai
  costruito.
  Trovato anche perché il dedup esistente non l'ha già ripulita:
  `sanitize.py::_key_for` (usato da `core/healing/normalizer.
  find_duplicates`) copre solo LINE/LWPOLYLINE/POLYLINE/CIRCLE/ARC — SPLINE
  produce `key=None` e viene ignorata da `find_duplicates`, quindi su un
  file quasi tutto SPLINE il dedup di fatto non gira. Anche dove si applica,
  la chiave è un'uguaglianza esatta a 2 decimali: due entità quasi
  coincidenti ma scostate di qualche decimo di mm (come le tracciature
  doppie viste sia qui che nel foglio B) hanno chiavi diverse e non vengono
  mai considerate duplicate — è un dedup per copie esatte, non per
  prossimità.
  Non è la stessa causa degli altri punti: lì servirebbe riconoscere
  geometria doppia/quasi-coincidente; qui servirebbe un'estrazione loop
  planare corretta (es. half-edge/DCEL con una regola di svolta coerente),
  che è un algoritmo diverso, non un'estensione dell'euristica attuale — va
  affrontato a parte. `merge_collinear_overlaps` (MAP.md D50, fatto dopo
  questa nota) non aiuta qui: lavora solo su `LineSeg`, e questo file è quasi
  tutto SPLINE.

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
Il caso: un disegno (quello dei segni tracciati stretti, oggi non più su disco)
ha una serie di dentelli che partono da una linea orizzontale, che sono considerati parte del grafo giustamnete. vorrei aggiungere un parametro che sotto una certa distanza queste linee siano considerate solo dei segni di marcatura, completando il grafo solo con la linea orizzontale. Anche se ho degli inner che hanno distanza inferiore alla tolleranza di cui sopra, devono essere detectati come segni di incisione e posti sul layer 'Engrave'. probabilmente questa cosa va implementata nel modulo detect e può essere individuato il tutto solo passando detect_flat() come facciamo con le bl che hanno la loro tolleranza.


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
- **Idea "detect dovrebbe usare il suo stesso contratto"**: `detect_flat()` ha
  accesso diretto/privilegiato alla tassonomia dei ruoli invece di passare
  dagli stessi ganci (`role`) di un consumatore esterno come snapdraw. Appena
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
`role_rules` sono solo il modo di assegnarlo al load (D63), il
meccanismo vero è `edge.role`, assegnabile per qualunque criterio
(raggio, posizione, geometria...), senza nessuna dipendenza da layer o
formato. In questa conversazione è già capitato di spiegare una cosa così a
Federico usando "layer" invece di "role", e si è arrabbiato parecchio — vedi
memoria `discuss-forge-in-role-terms-not-layer-terms`.
