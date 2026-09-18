# forge — TODO


Stato attuale: healing funzionante, export JSON/XDATA base, layer centralizzati.
Forge è un motore per comprendere geometria CAD 2D.

Nota: tutto quello che era ✅ fatto è stato tolto da qui (il record resta in
`MAP.md`, decisione per decisione). Questo file tiene solo quello che è
ancora aperto.

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

## IN CORSO — `detect` come consumatore, non cablato in `ForgeCluster` (branch `refactor/detect-overlay`)

Il cluster di `heal` è già neutro: `outer` + `inners`, geometria
provenance-free. Ma la dataclass `ForgeCluster` ha comunque i campi
`holes` / `bending_lines` / `engrave_lines` / `custom` **cablati nella
struttura**, sempre presenti e sempre liste vuote appena `heal()` finisce — i
cassetti da "pezzo di lamiera" nel modello neutro (tensione di
`forge-clusters-not-parts` non chiusa fino in fondo). `detect()`
(`tools/detect.py`) li riempie mutando direttamente quei campi (una decina di
siti: `cluster.holes.append`, `cluster.inners = new_inners`,
`cluster.bending_lines.append`, `cluster.custom[...]`). Problema concreto, non
solo estetico: **una lista vuota non distingue "detect non è mai girato" da
"è girato e non c'è nessun foro"**.

Deciso con Federico (2026-09-18): farlo, branch dedicato. Scaletta:

1. Nuovo `model/detected_features.py`: `DetectedFeatures(holes, bending_lines,
   engrave_lines, custom)` — stessa forma di oggi, spostata fuori dal cluster.
2. `ForgeCluster`: via i 4 campi feature, dentro `detected: Optional[DetectedFeatures]
   = None`. `summary()`/`area`/`to_dict()` leggono da `self.detected`,
   gestendo esplicitamente il caso `None`.
3. `detect.py`: ogni sito che oggi scrive diretto sul cluster crea/aggiorna
   `cluster.detected` invece.
4. Consumatori a valle da aggiornare a passare per `.detected`: `io/dxf.py`
   (routing output fori/pieghe/incisioni), view_model/SVG, `inspect.py`
   (`_sub_part`).
5. Test + golden aggiornati — verificare prima di rigenerare, mai alla cieca
   (`golden-files-verify-before-regenerating`).
6. Verifica finale: suite verde + un fixture reale con fori/pieghe/incisioni
   renderizzato e guardato, non solo contato
   (`render-the-drawing-before-judging-output`).

**Domanda di design ancora aperta, da decidere prima di scrivere il punto 2**:
un consumatore che oggi fa `cluster.holes` — lo lasciamo rompersi (deve
passare per `cluster.detected.holes`, esplode se `detected is None`, coerente
col motivo di questo refactor), oppure teniamo una `@property holes` di
comodo che ritorna `[]` se `detected` è `None`? La property è comoda ma
**reintroduce l'ambiguità che il refactor vuole togliere** (lista vuota
torna a significare due cose diverse). Non decisa — Federico deve ancora
scegliere quanto severo vuole questo breaking change interno.

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
