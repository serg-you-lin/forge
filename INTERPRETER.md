# L'interprete di disegno — struttura

Progetto **nuovo e separato** che usa `forge` come motore deterministico ed
estende le sue funzionalità come `detect()` fa già oggi con fori e pieghe.
Non vive in questo repo; questo file è il piano.

Nome provvisorio: `interpret` (da decidere).


## Il principio

`forge` è la base **deterministica**: da un file CAD tira fuori un modello
strutturato affidabile — parti, feature, annotazioni tipate e ancorate — e sa
riscrivere un output fedele. Non indovina, non interpreta convenzioni di
reparto. È lo strumento di cui l'agente si fida per ricostruire un disegno.

L'**interprete** è un **orchestratore che sta sopra forge**. Chiama i passi
deterministici di forge in sequenza, ci infila i suoi passi semantici, e
riporta le sue decisioni giù a forge come input (esattamente come `label_map`
oggi). Non modifica mai forge.

Precedente: `detect()` prende la topologia di forge e classifica
(contorno interno → foro → foro filettato → `role` giusto → layer giusto).
L'interprete generalizza quel pattern.


## La pipeline dell'interprete

```
file CAD (dxf / pdf / svg)
   │
   ▼
[1]  forge.load_*                     → ForgeDocument (edges + annotazioni grezze)
   │
   ▼
[2]  frame detection        (interprete) → riconosce cornice / cartiglio; segna
   │                                       quei contorni role="frame" e li passa
   │                                       giù come input al passo 3
   ▼
[3]  forge.heal                       → ForgeResult (parti; con la cornice esclusa
   │                                    l'outer VERO emerge, gli inner sono giusti,
   │                                    il cartiglio non è più una parte)
   ▼
[4]  forge.detect                    → fori, pieghe, incisioni (deterministico, forge)
   │
   ▼
[5]  forge.interpret_annotations     → Annotation.part_ref (geometria pura, forge)
   │
   ▼
[6]  callout parsing        (interprete) → material / thickness / quantity / code
   │                                       per parte, dal testo delle sue annotazioni
   ▼
[7]  title-block reading    (interprete) → metadati di disegno (materiale generale,
   │                                       numero disegno, revisione, scala) dalle
   │                                       annotazioni nella zona cornice
   ▼
[8]  nomenclature mapping   (interprete) → nomi canonici di reparto
   │                                       (FE-DECAPATO → acciaio). Tabella PRIVATA,
   │                                       caricata a runtime, MAI nel repo.
   ▼
[9]  enrichment / ERP       (interprete) → riempie i buchi (materiale, quantità)
   │                                       da fonti esterne. Callback, come il
   │                                       data_injector di forge.
   ▼
[10] "disegno interpretato"  → oggetto ricco su cui lavora l'agente / il consumatore
   │
   ▼
[11] forge.to_dxf / to_svg / save_json   (export deterministico, forge)
     + output propri dell'interprete (file di taglio per parte, un report, ...)
```

I passi [1] [3] [4] [5] [11] sono forge, invariati. I passi [2] [6]-[10] sono
l'interprete.


## I moduli dell'interprete

| modulo | cosa fa |
|---|---|
| `pipeline.py` | l'orchestratore: `interpret(path, profile=...) -> Drawing` |
| `frame.py` | rilevamento cornice / cartiglio. Riusa `forge.core.classification.frame_detector` (geometria pura: ratio ISO √2 + containment ≥ 80%, conservativo) o lo reimplementa. Output: quali contorni sono mobilio di disegno |
| `callouts.py` | parser dei callout `etichetta: valore`. Regex → `{code, material, thickness, quantity, instructions}`. Pattern in un config, sovrascrivibili per reparto |
| `titleblock.py` | legge i metadati di disegno dalle annotazioni nella zona cornice |
| `nomenclature.py` | traduzione nomi di reparto. Ship VUOTO / con uno stub. Le tabelle vere stanno nel config privato del reparto, caricate a runtime. **Mai nel repo, mai su github** |
| `model.py` | il modello "disegno interpretato": `Drawing` (metadati + parti), `InterpretedPart` (il `ForgePart` di forge + material/thickness/quantity/code/instructions, ognuno con `source` e `confidence`) |
| `enrich.py` | hook di gap-filling (ERP, foglio di lavoro). Callback, come `data_injector` |
| `profiles/` | profili per-reparto / per-cliente: pattern callout, path tabella nomenclatura, convenzioni cornice, materiale di default. Un `ShopProfile`. È qui che si materializza l'apprendimento per-cliente |


## Come usa forge

Come `detect` estende forge con la classificazione fori/pieghe, l'interprete
estende con:

- **classificazione cornice** (prima di `heal`)
- **metadati semantici** (dopo `detect`)

Non tocca forge. Chiama l'API pubblica e aggiunge `role` e dati sopra. Se un
domani serve un `role` che forge non conosce (`"frame"`, `"section"` per
l'unfolder), forge deve essere estendibile sui role — un contorno con un role
esterno non va in trash, viene trasportato ed esportato sul layer di quel role
via una mappa che il chiamante estende. (Da implementare in forge quando serve.)


## Come usa i testi per interpretare il disegno

I testi sono l'**overlay semantico sulla geometria**. forge dà le annotazioni
tipate e ancorate (`Note` / `Dimension` / `Leader`, con `part_ref`). L'interprete
le trasforma in **conoscenza strutturata**:

- callout `etichetta: valore` → campi di parte
- note libere → istruzioni (con ambito: la parte, o tutto il disegno)
- quote → tolleranze sulle feature (più avanti: legare `Dimension.references`
  ai fori / spigoli)
- testo del cartiglio → metadati di disegno

E fa **cross-check**: la quota concorda con la geometria misurata? forge dà
`Dimension.measured_value`; un override che non concorda è un flag.

Ogni campo interpretato porta **da dove viene** (quale annotazione, quale
pattern) e una **confidence**.


## Cosa restituisce — la forma comoda per l'agente

Una chiamata sola: `drawing = interpret("part.dxf", profile="TON")` che ritorna
un `Drawing` dove:

- `drawing.parts[i]` è un `ForgePart` di forge **più** `.material`, `.thickness`,
  `.quantity`, `.code`, `.instructions` — ognuno con `.source` e `.confidence`
- `drawing.metadata` — numero disegno, revisione, scala, materiale generale
- `drawing.unresolved` — la lista di "non sono riuscito a determinare X", così
  l'agente sa cosa chiedere o cercare
- `drawing.flags` — incongruenze (quota vs geometria, due materiali candidati,
  rilevamento cornice incerto)
- `drawing.to_json()` — serializzabile, per uso fuori processo / diff / altri tool
- `drawing.forge_result` — il `ForgeResult` grezzo sotto, per quando serve
  scendere nel dettaglio


## Onestà

Il principio del determinismo di forge, portato su: l'interprete **può** essere
probabilistico, ma deve **etichettare** l'incertezza. Dove non sa, `None` + una
voce in `unresolved`. Mai una supposizione presentata come fatto.


## Profili per-cliente e addestramento

Corpus: per ogni disegno si salva
`(forge_result.json, interprete_output.json, verità_umana.json)`.

Il `ShopProfile` si affina dai diff tra output dell'interprete e verità umana:
quali pattern aggiungere, quali convenzioni cornice, quale nomenclatura. Più
avanti: un modello appreso affianca / sostituisce le regex. Tutto qui, mai in
forge — non si impara su un output che già indovina.


## Domanda aperta: l'agente dentro o sopra l'interprete

Due letture, da decidere:

- l'interprete è deterministico-ish (regole + profili) e l'agente sta **sopra**,
  lo usa come tool e gestisce `unresolved` / `flags`
- l'agente **è un componente** dell'interprete — es. il passo nomenclatura o il
  gap-filling chiamano l'agente per il giudizio


## Cosa NON ci va

- la traduzione della nomenclatura di reparto nel repo / su github
- qualsiasi guessing non etichettato con source + confidence
- logica specifica di un singolo cliente fuori dai `profiles/`
- modifiche a forge per far comodo all'interprete: forge resta neutro,
  l'interprete si adatta
