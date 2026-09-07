# forge come substrato + l'interprete come primo consumatore

`forge` è una libreria **deterministica** che ripulisce la matematica pesante e
le rotture di coglioni di un file CAD, e restituisce **oggetti già pronti** su
cui altri lavorano: un agente, un'altra libreria, un nester, l'unfolder,
l'interprete di disegno.

Questo file descrive:
1. cosa forge espone perché i consumatori ci facciano molto sopra;
2. l'**interprete di disegno** — il primo consumatore, progetto nuovo e
   separato, che usa forge come motore ed estende come fa già `detect`.

Nome dell'interprete: da decidere.


## forge = substrato

### Cosa produce (deterministico)

- **cluster** — gruppi di geometria separati spazialmente (un outer, i suoi
  inner, i suoi segmenti aperti). Nel codice: `ForgeCluster` / `result.clusters`.
- feature dentro un cluster: fori (per tipo), pieghe, incisioni — via `detect`
- annotazioni tipate e ancorate: `Note` / `Dimension` / `Leader`, con `cluster_ref`
  (quale cluster contiene l'annotazione)
- bbox, posizione relativa dei cluster

### Cosa NON decide

Un cluster **può essere** un pezzo lavorabile — ma anche una vista dello stesso
pezzo, una sezione, un particolare, o il cartiglio. **forge non decide quale.**
La "part-ness" è interpretazione, ed è del consumatore.

### I tool deterministici che consumano cluster (restano in forge)

| tool | cosa fa |
|---|---|
| `heal` | file → cluster (topologia pulita) |
| `detect` | classifica la geometria dentro i cluster (fori/pieghe/incisioni → `role`) |
| `split` / `split_to_files` | divide i cluster, li nomina, li scrive uno per file |
| `interpret_annotations` | `Annotation.cluster_ref` — quale cluster contiene l'annotazione (solo geometria) |
| `inspect` | ispezione a 3 livelli |
| `to_dxf` / `to_svg` / `save_json` | export fedele dal modello |

Un consumatore può fermarsi a `heal` e fare tutto il resto a modo suo.


## L'interprete di disegno

Un **orchestratore sopra forge**: chiama i passi deterministici di forge in
sequenza, ci infila i suoi passi semantici, e riporta le sue decisioni giù a
forge come input (come fa `label_map`). Non modifica mai forge. Generalizza il
pattern di `detect`.

### Pipeline

```
file CAD
   │
   ▼
[1]  forge.load_*                     → cluster grezzi + annotazioni grezze
   │
   ▼
[2]  frame / cartiglio  (interprete)  → riconosce cornice e riquadro cartiglio,
   │                                    li segna e li passa giù al passo 3
   ▼
[3]  forge.heal                       → cluster puliti (cornice esclusa → l'outer
   │                                    vero emerge; il cartiglio non è un cluster)
   ▼
[4]  forge.detect                    → fori/pieghe/incisioni (deterministico, forge)
   │
   ▼
[5]  view classification (interprete) → quali cluster sono viste dello stesso
   │                                    pezzo (pianta / vista di fianco / sezione
   │                                    A-A), lamiera piegata → c'è uno sviluppo
   ▼
[6]  forge.interpret_annotations     → cluster_ref sulle annotazioni (forge)
   │
   ▼
[7]  callout parsing   (interprete)  → material / thickness / quantity / code per
   │                                    pezzo, dal testo delle sue annotazioni
   ▼
[8]  title-block reading (interprete) → metadati di disegno (materiale generale,
   │                                    numero disegno, revisione, scala)
   ▼
[9]  nomenclature       (interprete)  → nomi canonici di reparto (FE-DECAPATO → …).
   │                                    Tabella PRIVATA a runtime, MAI nel repo
   ▼
[10] enrichment / ERP   (interprete)  → riempie i buchi da fonti esterne (callback)
   │
   ▼
[11] "disegno interpretato" → oggetto ricco su cui lavora l'agente / il consumatore
```

I passi [1] [3] [4] [6] sono forge invariati. [2] [5] [7]-[10] sono l'interprete.

### Moduli

| modulo | cosa fa |
|---|---|
| `pipeline.py` | l'orchestratore: `interpret(path, profile=...) -> Drawing` |
| `frame.py` | rilevamento cornice / cartiglio. Riusa il `frame_detector` di forge (geometria pura: ratio ISO √2 + containment ≥ 80%, conservativo — se non è sicuro non filtra niente) |
| `views.py` | classificazione viste: raggruppa i cluster che sono viste dello stesso pezzo, distingue pianta / sezione / sviluppo; riconosce una lamiera piegata |
| `callouts.py` | parser `etichetta: valore` → `{code, material, thickness, quantity, instructions}`. Pattern in un config, sovrascrivibili per reparto |
| `titleblock.py` | legge i metadati di disegno dalla zona cornice |
| `nomenclature.py` | traduzione nomi di reparto. Ship VUOTO / stub. Tabelle vere nel config privato |
| `model.py` | `Drawing` (metadati + pezzi), `InterpretedPart` (il cluster di forge + material/thickness/quantity/code/instructions, ognuno con `source` e `confidence`) |
| `enrich.py` | hook di gap-filling (ERP, foglio di lavoro). Callback |
| `profiles/` | profili per-reparto/per-cliente: pattern callout, path nomenclatura, convenzioni cornice, materiale di default. È qui che si materializza l'apprendimento per-cliente |

### Come usa i testi

I testi sono l'overlay semantico sulla geometria. forge dà le annotazioni
tipate e ancorate; l'interprete le trasforma in conoscenza strutturata:

- callout `etichetta: valore` → campi di pezzo
- note libere → istruzioni (con ambito: il pezzo, o tutto il disegno)
- quote → tolleranze sulle feature (più avanti: legare `Dimension.references`
  ai fori / spigoli)
- testo del cartiglio → metadati di disegno

Fa cross-check: la quota concorda con `Dimension.measured_value` di forge? Un
override che non concorda è un flag. Ogni campo interpretato porta `source` +
`confidence`.

### Cosa restituisce — la forma comoda per l'agente

`drawing = interpret("part.dxf", profile="TON")` → un `Drawing` dove:

- `drawing.parts[i]` = cluster di forge **più** `.material` / `.thickness` /
  `.quantity` / `.code` / `.instructions`, ognuno con `.source` e `.confidence`
- `drawing.metadata` — numero disegno, revisione, scala, materiale generale
- `drawing.views` — quali cluster sono viste di cosa
- `drawing.unresolved` — cosa non è riuscito a determinare (l'agente sa cosa chiedere)
- `drawing.flags` — incongruenze (quota vs geometria, due materiali candidati,
  cornice incerta)
- `drawing.to_json()` — serializzabile
- `drawing.forge_result` — il risultato grezzo di forge sotto, per scendere nel dettaglio

### Onestà

L'interprete può essere probabilistico ma deve **etichettare** l'incertezza.
Dove non sa: `None` + una voce in `unresolved`. Mai una supposizione come fatto.

### Addestramento

Corpus per disegno: `(forge_result.json, interprete_output.json,
verità_umana.json)`. Il `ShopProfile` si affina dai diff. Più avanti un modello
appreso affianca le regex. Tutto qui, mai in forge — non si impara su un output
che già indovina.

### Domanda aperta

L'agente sta **sopra** l'interprete (lo usa come tool, gestisce
`unresolved` / `flags`), o **è un componente** dell'interprete (i passi
nomenclatura / gap-filling lo chiamano per il giudizio)? Da decidere.


## Cosa NON ci va

- la nomenclatura di reparto nel repo / su github
- guessing non etichettato con `source` + `confidence`
- logica di un singolo cliente fuori dai `profiles/`
- modifiche a forge per far comodo all'interprete: forge resta neutro,
  l'interprete si adatta
