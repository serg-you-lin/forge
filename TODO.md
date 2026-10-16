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

## APERTO (16 ottobre, MAP.md D108) — rename `forge` → `topo`, distribuzione `g-topo`

Da fare: package `forge/` → `topo/`, `pyproject.toml` (`name = "g-topo"`),
import in test/script/docs, `gen_index` layers, README/README_IT, LLM.md/API.md;
poi i consumer (snapbend, snapdraw). Nessun alias.

## APERTO (16 ottobre, MAP.md D109) — contorno meno regione, traccia × contorno

Tre API geometriche da scrivere quando il prototipo esterno si è stabilizzato:
intersezione traccia × contorno chiuso col tipo di punto; contorno chiuso meno
disco (poi regione) → contorno nuovo valido; traccia tagliata da una regione.

## CHIUSO (12 ottobre, MAP.md D106) — `.polygon` vs `.segments`; resta un filo, dentro D103

Risolto: i segmenti di una faccia si leggono dal suo bordo (`topology/rim.py`,
taglio esatto delle primitive in `primitives/trim.py`, spline comprese); un
giro che tocca se stesso è una faccia per lobo (prima `buffer(0)` buttava i
lobi minori in silenzio); una faccia più stretta della tolleranza di nodo non
è una faccia. La pista di D105 (rigrafo a banda larga) è smentita dai numeri:
metà del bordo stava su edge solo in parte sul bordo, nessun ordine e nessuna
banda li recupera. Coerenza verde su 15/15, round-trip su 13/15. DXF prima/dopo
da guardare a occhio: `_debug/*_D106_prima.dxf` / `*_D106_dopo.dxf`
(anch_02, anch_03, anch_06, drw_0011, regr_01, regr_02, regr_04).

Due invarianti nuove (D107): `TestNothingDropped` (verde 15/15) e
`TestInnersDontCross` (rosso apposta su anch_03/regr_02, il filo qui sotto).
Golden delle isole: **si rigenerano tutti insieme quando i dubbi D103 sono
chiariti**, guardando prima i DXF — deciso con Federico il 12 ottobre.

**Filo rimasto, lasciato apposta (è territorio D103, sotto):** round-trip di
`anch_03`/`regr_02`, l'isola da 5806 mm² passa da 28 a 15 inner. Già rosso
su `06b89b1`. Causa: giri inner che si **sovrappongono in parte** fra loro
(es. 18.7 + 71.1 mm², unione 76.6): cicli di LoopFinder che non sono facce;
rileggendo, i contorni sovrapposti si fondono. Si decide insieme ai dubbi
D103 qui sotto (forellini di anch_03, inner "nipoti"): 27 coppie
sovrapposte su anch_03, 25 su anch_02, quasi tutte contenimento pieno.

## APERTO — 4 dubbi su D103 (`_drop_boundary_duplicates`), non verificati, segnalati da Federico il 12 ottobre guardando `_debug/*_ghosts.dxf`

Nessuno di questi quattro è stato controllato sul codice — sono dubbi legittimi,
non ancora confermati né respinti:
- **`anch_02`/`anch_03`** (50 e 4 giri scartati sui forellini del pattern di
  foratura): potrebbero essere inner annidati legittimi ("inner nipoti",
  profondità 2), non duplicati — da confrontare con come `heal()` tratta lo
  stesso tipo di nesting.
- **`anch_06`** (1 giro scartato, sovrapposto all'outer): potrebbe essere un
  simbolo di disegno vero, non un duplicato del bordo.
- **`anch_07`/`regr_05`** (1 giro scartato, 0.07 mm²): dovrebbe forse finire in
  `non_contour`/trash, non nel bucket "duplicato scartato".

Script per rigenerare i DXF con i giri scartati in rosso (layer
`FANTASMA_SCARTATO`): `_debug/mark_ghosts.py` era nello scratchpad della
sessione, non salvato nel repo — da riscrivere se serve (richiama
`island_mod._drop_boundary_duplicates` con uno spy, poi `forge.to_dxf` +
`ezdxf` per disegnare i giri scartati in rosso sopra al resto).

**`regr_04.cluster[0].inner[0]` (il "bordo doppio in un giro"): chiarito in
D106** — non era `merge_runs` (verificato corretto) ma due mezzelune fra due
cerchi tangenti internamente, giro a otto, e `build_polygon` che teneva un lobo
solo. Ora sono due inner.

**Non toccare `anch_02`/gli altri golden islands finché i dubbi D103 qui sopra
(e gli inner sovrapposti di anch_03) non sono chiariti**: rigenerare qualsiasi
golden ora rischia di congelare un numero sbagliato. Nota: D106 cambia già
`regr_04` islands[1] (1 → 2 inner) e `anch_02` (+4 strisce) — da tenerne conto
quando si rigenera.

---

## RIPARTENZA — D101 (nodo a T / quasi-tangenza), branch `topology/t-junction-noding`

**Fatto, verde** (MAP.md D101): `_split_params` (`noding.py`) fonde due tagli
entro `tolerance` in un nodo solo, non due — la causa isolata di D100. Suite
810 (809 verdi). Nuovo test: `test_noding.py::test_quasi_tangenza_e_un_nodo_
solo_non_due`. Branch creato da `main` a `108b74c` (prima dello stash del
lavoro PDF in corso, sotto).

Lo stash dell'esperimento scartato di D101 è stato tolto il 12 ottobre, con
l'ok di Federico. Resta solo lo stash del lavoro PDF in corso (`On main: WIP
pre topology-noding branch`).

**Nuovo filo aperto (11 ottobre, non ancora capito a fondo) — inner "fantasma" vicino
alle asole/forellini, anche con l'albero committato (non è un residuo dello stash
PDF):** su `tests/data/golden_islands/anch_02.dxf` (vista isometrica, cluster[1]),
confermato da Federico guardando `_debug/anch_02_3D_from_dxf_CLEAN_TREE.dxf` (`island()`
sul codice committato di questo branch, nessuno stash applicato):

1. L'asola grande (`inner[0]`, area 1011 mm², bbox 1421–1507 × 101–158) ha una punta
   arrotondata rovinata da una spike di 0.33 mm: il bordo liscio arriva a
   (1506.30, 105.58), scatta fuori a (1506.63, 105.39) e torna a (1506.30, 105.19)
   prima di richiudersi. Tre punti a 0.3–0.4 mm l'uno dall'altro che dovrebbero
   essere un nodo solo non si sono fusi — stessa famiglia di D100/D101
   (quasi-tangenza) ma **non risolta da D101**: il fix di D101 è già committato su
   questo branch e il difetto resta. Sembra un punto reale (fit-point della spline
   di raccordo) che non coincide con la curva healed, non un duplicato banale.
2. **Sistematico, non isolato**: nello stesso cluster, circa 20 forellini del
   pattern di foratura (bbox ~3.5mm, es. 1540–1544×128–134 e 1540–1544×104–109)
   hanno **due** inner quasi sovrapposti nello stesso punto: uno pulito (l'ellisse
   proiettata vera, 2 SplineSeg che chiudono da estremo a estremo, area ~16 mm²) e
   uno "fantasma" annidato dentro, fatto di 2 ArcSeg + 4-7 SplineSeg minuscoli e
   seghettati (area ~11 mm², non zero come i fantasmi di `regr_04`/D101 — qui è
   un'area reale, sbagliata). Pattern: `cluster[1].inners[26,28,30,32,...64]` su
   `anch_02.dxf` (script di ispezione non salvato, rifare con `forge.island()`
   + `max_gap=0.5` se serve riprodurre).
3. Federico non si fida più dei golden su questa classe di fogli: **confermato**
   che il motivo è reale — `test_golden_islands.py` confronta solo bbox outer e
   **conteggio** inners (non la forma), `test_golden_anchoring.py` solo il testo
   delle annotazioni: nessuno dei due avrebbe mai potuto vedere né la spike né gli
   inner fantasma, a differenza di `tests/real/test_golden.py` (`heal()`, parti
   piatte) che confronta la forma via WKT/shapely con tolleranze stette.
4. **Bisecato (11 ottobre) su worktree a commit vecchi, stesso `anch_02.dxf`, stesso
   `max_gap=0.5` — due bug distinti, non uno:**
   - **Fantasmi (punto 2 sopra): preesistenti**, identici su `1b5b02e` (D99, prima
     di tutto il lavoro di questa sessione). `fitting.py`/`points.py` non sono mai
     stati toccati per il PDF nella storia committata (solo spostati, D95) — non è
     una contaminazione del lavoro PDF. Raw edge nel punto caldo (1538–1546 ×
     127–135, prima di `island()`): 2 `ArcSeg` + 13 `SplineSeg`, un'unica rete
     connessa — e tornano spalmati esattamente sui due inner (2 spline nel pulito,
     2 arc + 11 spline nel fantasma). Quindi non è il source duplicato: è
     `island()` che da una rete sola trova due giri chiusi (uno vero, uno fantasma)
     e li riporta entrambi come inner (D71 dice "tutti i giri chiusi" — corretto
     per isole scollegate, probabilmente non per questo caso).
   - **Spike (punto 1 sopra): introdotta da D100.** Pulita su `1b5b02e` (D99, punta
     a x=1506.30 netta), già rotta su `091970a` (D100, "the outer face is the
     boundary of the union of the closed faces", x=1506.63) — **non è D101**, il
     fix di questa sessione è innocente qui. Riapre di fatto la domanda del punto 3
     di "Resta da chiudere prima di mergiare" sotto: non è solo "forse ridondante",
     D100 **regredisce** un caso quasi-tangente sul bordo dell'unione.

**Piano di fix (deciso l'11 ottobre):**

1. ✅ **Fatto (11 ottobre) — test di regressione PRIMA del fix, rossi apposta.**
   Due fixture ritagliate dal foglio reale (non costruite a mano/analiticamente:
   i bug coinvolgono spline vere, 62 nella seconda — minimizzarle a mano non
   valeva l'effort), salvate con l'API di forge (`OpenFeature`+`ForgeResult`+
   `forge.to_dxf`, mai `ezdxf` diretto) — **attenzione**: il ruolo dev'essere
   un slug qualunque tipo `"geometry"`, **non** `"unknown"` — `role_to_dxf_layer`
   manda `unknown` sul layer `Trash`, e `DxfAdapter.to_edges()` scarta `Trash` a
   lettura (`_NON_STRUCTURAL_LAYERS`, `adapter.py:40`) — ci si casca dentro,
   verificato sul roundtrip prima di fissare le fixture:
   - `tests/data/regressions/island_ghost_loop.dxf` (15 edge: 2 `ArcSeg` + 13
     `SplineSeg`, il foro col giro fantasma)
   - `tests/data/regressions/island_tangent_spike.dxf` (71 edge, l'asola con la
     spike)
   - `tests/unit/core/test_island_regressions.py` — `TestGhostLoop` e
     `TestTangentSpike`, caricano le fixture via `forge.load_dxf` +
     `forge.core.island.read_island(edges, tolerance=0.05, max_gap=0.5)`.
   Stato suite confermato: 809 passed, 3 failed (i 2 nuovi + `regr_04`, già
   rosso e noto, punto 1 sotto — nessun'altra rottura, `gen_index.py --check` ok).
2. ✅ **Fatto (11 ottobre, stessa sessione del punto 1) — i due fix.** La prima
   ipotesi (punto 3 di sotto, sede del bug in `outer_face.py`) era **sbagliata**:
   verificato con un giro-passo-passo che `outer_face()` da sola, su `doc.edges`
   crudi, già dà il risultato giusto (1011.26, nessuna spike) — il bug si
   manifesta solo dopo `_normalize()` (gap-fix), prima ancora che `outer_face`
   veda la rete. Entrambi i fix stanno quindi in `forge/core/island.py`, non in
   `outer_face.py`. Suite dopo i due fix: 810 passed, 10 failed — i 10 sono
   TUTTI golden islands/text-budget preesistenti impattati dal fix fantasmi
   (vedi "Impatto sui golden" sotto), **nessuna rottura nuova**: i 2 test di
   regressione (punto 1) sono verdi, `regr_04` resta nella stessa famiglia di
   rottura già nota (D101), `gen_index.py --check` ok.

3. ✅ **Fix spike — causa reale: `_normalize()` salda due estremi liberi che
   non sono un gap vero (`forge/core/island.py`).** La spike non nasce nel
   walk né nell'union di `outer_face.py` (quelli restano INTOCCATI): nasce
   prima, in `_normalize()`. Due `LineSeg` indipendenti (edge di un'altra
   faccia della vista isometrica, non il raccordo del contorno) hanno ciascuno
   un estremo libero a ~0.4mm dalla curva del raccordo (2 `SplineSeg` già
   chiusi fra loro, la vera punta arrotondata) — entro `max_gap=0.5`, quindi
   `compute_gap_fixes` li tratta come un gap e li prolunga (retta-retta) fino
   alla loro intersezione reale, 0.33mm **oltre** la curva vera: una spike,
   non un gap chiuso. Il segno che lo tradisce: quei due estremi erano **già
   nella stessa componente connessa del grafo** (collegati altrove dal
   raccordo stesso) — saldarli apre un secondo percorso parallelo spurio
   (sliver) accanto al contorno che si chiude già da solo, non chiude niente
   che fosse aperto. Fix: `_drop_redundant_meets()` in `island.py` scarta un
   fix "incontro" (`MoveEndpoint` di retta/arco prolungata fino
   all'intersezione) quando i suoi due estremi di partenza sono già nella
   stessa componente connessa — un gap vero collega sempre due componenti
   diverse. Verificato: rigetta *solo* la coppia spuria del fixture
   (`TestTangentSpike` verde); su `anch_03`/`anch_08`/`regr_02` (golden reali
   con gap-fix legittimi, estremi in componenti diverse) non scarta nulla —
   la prima versione (filtro per prossimità a un'altra curva, non per
   componente) scartava anche questi per errore, scoperta e corretta
   confrontando i due casi fianco a fianco prima di fissare il criterio.
4. ✅ **Fix fantasmi — non è `split_at_crossings`/noding: è D71 troppo largo
   su un giro che duplica il bordo di un altro (`forge/core/island.py`).** Le
   15 edge sono **due componenti connesse separate** (13 e 2), ognuna già un
   giro chiuso per conto suo — non c'è autoincrocio numerico da correggere.
   Il giro fantasma (11.3 mm², 2 `ArcSeg`+11 `SplineSeg`) sta **interamente
   dentro** il giro vero (16.25 mm², 2 `SplineSeg`) e il suo bordo intero resta
   entro ~0.51mm dal bordo del giro vero (tipicamente la parete visibile di un
   foro in una vista isometrica, quasi sovrapposta alla sua stessa apertura).
   D71 ("ogni giro chiuso è un inner") è corretto per isole scollegate ma non
   per un giro che segue quasi lo stesso bordo di un altro già tenuto. Fix:
   `_drop_boundary_duplicates()` in `read_island()` — dato l'outer trovato
   (o un altro giro già accettato, in ordine di area decrescente), scarta un
   giro il cui bordo intero sta entro `tolerance + max_gap` dal bordo di un
   giro più grande già accettato (`big.exterior.buffer(band).contains(small.
   exterior)`); la soglia riusa i due parametri esistenti (nessuna costante
   nuova) — misurata sul fixture: 0.51mm, oltre `max_gap` da solo (0.5) ma
   dentro `tolerance+max_gap` (0.55). Gli edge del giro scartato non si
   perdono (non-negoziabile 7): ricadono su `NonContourEdgeDetector` come
   `non_contour` o `unclassified`, non più falsi "inner".

   **Impatto sui golden, verificato caso per caso ma NON rigenerato
   (non-negoziabile 9 — Federico deve giudicare a occhio):** 8 golden islands
   (`anch_02/03/06/07`, `regr_01/02/04/05`) e 2 text-budget (`anch_02/06`)
   ora falliscono per questo fix — perdono un inner a testa (o più su
   `anch_03`/`regr_02`, 32→28: lì il pattern è sistematico, non un caso
   isolato). Controllati a mano tre casi, tutti coerenti con lo stesso bug,
   nessun falso positivo trovato:
   - `anch_02` isola più piccola: perde un inner di area 3.10 mm² annidato
     dentro un inner pulito di 19.57 mm² alla stessa posizione (bbox quasi
     identico) — stesso pattern descritto sopra per `anch_02.dxf` nelle note
     dell'11 ottobre (punto 2), sui ~20 forellini del pattern di foratura.
   - `regr_04` isola[1]: il golden aveva già, da D101, un giro fantasma ad
     area quasi-zero (9.8e-13 mm², mai rigenerato — "il golden è letto dalla
     lettura vecchia e bacata", MAP.md D101); questo fix lo scarta anche lui
     (4→1 invece di 4→2), stessa famiglia di garbage, non un nuovo problema.
   - `anch_07` isola[0]: perde un giro minuscolo (0.076 mm², quasi un punto)
     che era un inner diretto dell'outer del pezzo stesso (non di un foro),
     col bordo a 0.51mm dal contorno esterno — stesso meccanismo, comparso
     accanto al contorno principale invece che dentro un foro.
   `test_text_budget.py` cresce di riflesso (gli edge del giro scartato
   finiscono in `non_contour`/`unclassified`, resi diversamente da `to_text`).

   **Prossimo passo per Federico:** guardare questi 10 casi a occhio (DXF
   aperti, non i numeri del golden) e confermare — poi, solo dopo, punto 5.

   **Nuovo filo aperto (12 ottobre) — stesso fix, lato PDF: completamente
   sbagliato, confermato da Federico a occhio.** I due fix sopra (punto 3 e 4,
   `_drop_redundant_meets` e `_drop_boundary_duplicates`) sono stati pensati e
   verificati solo sui golden **DXF**. Sul lato PDF (`_debug/anch_02_ALL_
   ISLANDS_from_pdf_BEFORE_FIX.dxf` vs `..._FIXED.dxf`, 11 ottobre 18:00-18:04,
   stesso pomeriggio del fix) Federico ha guardato i DXF e confermato: il
   risultato è completamente sbagliato, non un caso isolato. Non ancora
   root-causato — ipotesi non verificata: `band = tolerance + max_gap` in
   `_drop_boundary_duplicates` è calibrato sulla precisione DXF, e il residuo
   di un cerchio/arco PDF (fit ai punti Bezier campionati, non esatto come un
   `ARC` DXF — stessa causa di D102/D103 nello stash dell'adapter PDF) cade
   probabilmente proprio nella fascia che il filtro tratta come "duplicato da
   scartare", portandosi via inner veri. Da investigare con numeri reali
   prima di assumere questa causa, non solo a occhio.
5. **Solo dopo la conferma di Federico sopra:** rigenerare i golden islands e
   text-budget impattati, **poi** estendere `snapshot()` in
   `tests/real/test_golden_islands.py` a confrontare anche la **forma** di
   ogni inner (non solo bbox esterno + conteggio), sul modello di
   `test_golden.py` (WKT/shapely, tolleranza stretta) — così la prossima
   regressione di questa classe non passa inosservata.

**Resta da chiudere prima di mergiare:**

1. **`regr_04` — golden da far giudicare a Federico, non ancora rigenerato.**
   `island[0].inners` passa da 4 a 2: i due persi hanno area 1.85e-15 /
   1.88e-15 mm² alla stessa posizione — loop fantasma da zero area, non buchi
   veri (vedi MAP.md D101 per i numeri). Prima di rigenerare: fargli vedere
   (un DXF della zona, se lo vuole) e fargli confermare — non rigenerare da
   solo nemmeno con la prova in mano (CLAUDE.md non-negoziabile 9).
2. **Collisione di numerazione `D##` con `main`.** Questo branch numera la
   nuova decisione **D101** da `108b74c` (l'ultimo commit prima di questa
   sessione). Nella working tree di `main`, però, c'è ancora stashato (non
   committato) il lavoro dell'adapter PDF della sessione precedente, che
   numerava le sue decisioni **D101–D103** dallo stesso punto (vedi lo stash
   `"WIP pre topology-noding branch (pdf adapter circle-fit + naming note)"`
   su `main`, o `git stash list`). Quando l'uno o l'altro lavoro arriva a
   `main` per primo, il secondo deve rinumerare le proprie decisioni per non
   avere due D101 diversi nella storia. Non toccato qui: i due lavori sono
   indipendenti e nessuno dei due è stato fuso.
3. Non ancora valutato se il patch D100 (`_faces_union_loop`, union delle
   facce chiuse) sia reso ridondante dal criterio generale di D101 su qualche
   file — non è stato rimosso, D100 resta una decisione chiusa (va riaperta
   esplicitamente se si vuole toglierlo, non assunto qui).

---

0. **`load_geometry`: gli angoli dell'arco sono ancora in gradi** "per
   convenzione CAD" (resto di D96: `polygon` al posto di `polyline` fatto,
   costruttori e `load_segments` fatti). `ArcSeg` usa i radianti; passare lo
   schema ai radianti tocca la matematica di cono e sezione di snapbend
   (`core/cone.py`, `model/section.py`, lo scambio x/y di `model/geometry.py`).
1. ✅ **fatto (D93)** — **La geometria rimasta in `snapbend/flat/detect.py` torna in forge**
   (Federico, 4 ottobre: "tutto quello che è calcolo e geometria l'avrei messo
   in forge"). Su 828 righe la geometria pura è poca, ~70 righe; il resto è
   significato (ruoli, `Hole`, pieghe, incisioni) e lì resta. Ma due pezzi
   sono già doppioni di forge: `_point_line_distance` = `_point_to_line_distance`,
   `_same_line` = `are_collinear` (`core/geometry.py`). Da portare in forge con
   nomi geometrici: "una corda, prolungata di `reach`, divide il poligono in
   due" (`_cuts_part`) e "tratti sulla stessa retta, uniti dove lo spazio fra
   loro sta dentro un poligono dato" (`_bridged_runs`). La soglia `reach`
   (1 mm, snapbend D52) resta a snapbend come parametro.

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
5. **`detect_flat()` → snapbend** — ✅ **fatto (D88, D89, D90)**: golden divisi,
   detection in `snapbend/flat/`, renderer di forge generici sull'overlay.
   **Da decidere (Federico):** 10 golden `golden_multipli/process/` (ora in
   snapbend) hanno il summary vuoto (era `custom` prima del refactor di
   inject). Per i fori non manca un controllo (sono nei layer `Hole`); restano
   3 pieghe mai controllate: `staffa_scarto_doppia` pezzi 2 e 3 (30 mm) e
   `quattro_sviluppi_un_foglio` pezzo 2 (8.5 mm). La 8.5 mm non è più una
   piega: regola nuova "una piega taglia il pezzo" (snapbend MAP D52). Le due
   da 30 mm restano da guardare nei DXF in
   `snapbend/tests/data/flat/golden_multipli/detected/`. **Aperto:** un righino
   messo di traverso in un angolo passa ancora — serve una misura minima, da
   decidere (snapbend MAP D52).
6. **Estrazione dei loop planari (half-edge/DCEL)** — l'unica cosa in lista che
   cambia di categoria il motore; dettaglio nei "limiti geometrici noti".
7. **Due cose piccole dalla roadmap del preventivo** (step 0 e 1 di
   `ROADMAP.md`): `snap_distance` anche su `inject()` — ✅ fatto (D82). Il
   controllo quota-vs-geometria misurata **non è di forge** (D69): forge dà già
   `measured_value`, `display_text` e `references`, il confronto col numero
   scritto si fa in snapdraw — da portare nel TODO di snapdraw.
   Lo script di produzione dello split (ex `scripts/13_…`) importa ancora
   `extract_forge_texts`, che non esiste più: è rotto. **Spostato in snapbend**
   (Federico, 4 ottobre: alla radice, non versionato), da riscrivere lì
   su `inject(snap_distance=...)` — vedi il TODO di snapbend.
8. **Il rename `forge` → `snapforge`** — `naming_convention.md` (non tracciato) è
   un piano scritto e **mai eseguito**: nome umano `SnapForge`, identificatore
   tecnico `snapforge` per repo, cartella, package e `import`, stessa regola per
   `SnapDraw` e `SnapBend`. Tocca `pyproject.toml`, la cartella del package, ogni
   `import forge`, i docs, il remoto su GitHub e i consumer. Da decidere se farlo
   prima della 1.0.0 (dopo è un breaking change per chi importa) e se nel
   frattempo `naming_convention.md` entra in git come piano o resta locale.
9. **Rifare il viewer (`to_view_model` + `to_svg`), in una sessione a parte.**
   Federico, 3 ottobre: "ora è davvero bruttino e limitato, non scalabile, fa
   cose che dovrebbe fare il consumer e non fa cose che dovrebbe fare lui".
   Già visto, da cui partire (l'analisi vera è il lavoro di quella sessione):
   - ~~**fa cose da consumer**~~ e ~~le altre collezioni sono solo contate~~ —
     risolti da D90: il view-model disegna ogni collezione di `detected` sotto
     `features`, dal ruolo e dalla geometria, senza nomi privilegiati; archi e cerchi diventano
     punti (sotto);
   - **non scala**: su un foglio di viste pesa più del DXF di partenza.
   Il resto del punto, scritto prima, vale come parte di questo lavoro:
   **il view-model non discretizza più archi e cerchi** (Federico, 3 ottobre:
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
11. **Doppioni trovati da `gen_index.py` (D72)** — ✅ **tutti sistemati** il
   3 ottobre (D85): `_geometry` fuso in `noding.edge_geometry`,
   `_ensure_linetype` fuso in `exporter.ensure_linetype` (un linetype ignoto
   in `RoleStyle` ora solleva), gli omonimi rinominati.
   Limite del controllo: trova solo lo **stesso nome**. Per lo stesso lavoro
   sotto nomi diversi c'è ora `gen_index.py --similar` (punto 12).
12. **Stesso lavoro con nomi diversi** — ✅ **chiuso** il 3 ottobre: D86 (pezzi
   comuni trovati con `gen_index.py --similar`) e D87 (merge collineare e
   cocircolare su un motore unico, identico al vecchio su 611 disegni).
13. **La scala delle isole** — ✅ **chiuso** il 5 ottobre. Fatto: il default
   di `island_gap` e `max_gap` è tolto, ogni chiamante dice la sua distanza
   (D98; in snapdraw un posto solo, `sheet_islands`, snapdraw D29). Scartato:
   la scala (le distanze a cui le isole si uniscono) come strada per scegliere
   la distanza — Federico: "la scala non c'entra e non c'entrerà mai con la
   detection delle isole". Non si porta in `forge.geometry`. Le misure e i
   giudizi a occhio del 4-5 ottobre sono riassunti in D98.

14. **Isole: D99-D100 chiusi il 5 ottobre.** Il punto della situazione e i
   prossimi passi (detection sulle isole, lettura delle viste) stanno nel TODO
   di snapdraw, "Dove siamo". Golden delle isole: `tests/real/test_golden_islands.py`.

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

**4 ottobre — ✅ fatto (D97):** la storia pubblicata citava ancora disegni cliente per nome; riscritta e ripubblicata con `dxf-anonymize repo`, verificata pulita su un clone preso da GitHub.

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
- Lo script di produzione dello split (ex `scripts/13_…`, ora in snapbend, non
  versionato) ha un percorso assoluto con un codice pezzo. Finche' resta non
  versionato non entra in git, ma se un giorno lo si porta alla nuova API quel
  percorso va via prima.

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
  overlay a schema libero (D44), forge non sa cosa contengono. Se un
  consumatore ha già fatto la sua detection prima di ruotare, quei dati restano
  nelle coordinate vecchie — la detection va fatta DOPO aver ruotato.

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

- ~~**Problema 2**~~ — risolto da D47, poi la tassonomia di processo è uscita
  da forge (D90, in snapbend).
- ~~**Idea "detect dovrebbe usare il suo stesso contratto"**~~ — risolta da
  D90: la detection sta in snapbend e usa gli stessi ganci di qualunque
  consumatore (`role`, `register_role_style`, `heal(is_structural=...)`,
  l'overlay).
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
