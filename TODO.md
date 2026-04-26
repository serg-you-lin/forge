# dxf-forge — TODO

Stato attuale: healing funzionante, export JSON/XDATA base, layer centralizzati.
Obiettivo: tool vendibile per normalizzazione DXF e estrazione metadati da taglio laser.

---


## PRIORITÀ ALTA — blocca il prodotto

### Healing

- Implementare il parametro erase_texts se vogliamo ripulire dal testo sporcizia il file, al limite rimettendolo bene con snapmark  
-Gestire i 'nipoti' come marcatura. Se un figlio ha un figlio annidato, entrambi sono riconosciuti come parte dell'heal, ma da marcare.

### Metadati

- [ ] **Peso nel ForgeResult**
  - `weight_kg` = `area * thickness * density / 1e6`



---

## PRIORITÀ MEDIA — migliora la qualità

### Hashing

creare una fingerprint geometrica per validare na forge part.

### Microtesti

-Implementare in snapmark una modalità che funzian no nstandalone, ma importabile in modo che posso scrivere direttamente la marcatura ed i testi mentre faccio l'healing.

### Healing

- [ ] **Fallback polygonize — migliorare**
  - Attualmente produce warning generico
  - Aggiungere info su quali segmenti non si chiudono e dove sono i gap

### API

- [ ] **`forge.process()` — punto di ingresso unico**
  - `result = forge.process(input_dxf, output_dxf, upgrade=True, tolerance=0.05, write_xdata=True)`
  - Nasconde doc/msp/upgrade/write_metadata all'utente
  - Il batch script diventa 5 righe

- [ ] **`upgrade_to_r2010` — integrato automaticamente**
  - Attualmente va chiamato manualmente nel batch
  - `forge.process()` lo chiama sempre se `doc.dxfversion < 'AC1015'`. bisognerebbe consentire all'utente opzionalmente di upgrdare tutti i files, mentre per quanto mi riguarda se si vuole avere il forge i files che non gestiscono gli XDATA devono obbligatoriamente essere upgradati.

### Analisi

- [ ] **`DxfAnalyzer` — output CSV**
  - Esportare `summary_stats()` anche in CSV per analisi batch
  - Utile per misurare qualità dei fornitori

---

## PRIORITÀ BASSA — futuro

### Splitter

### Test

## NOTE ARCHITETTURALI

- `layers.py` — unica fonte di verità per i nomi layer, non toccare
- `heal()` — 3 passi sequenziali, non aggiungere casi esclusivi
- `_heal_existing_plines`, `_heal_circles`, `_loop_to_polygon` — dead code, rimuovere
- XDATA scritte su LWPOLYLINE layer=OuterContour — fragile se il file ha più parti
- Quando si implementa `forge.process()`, rivedere come XDATA vengono associate a più parti nello stesso file
- Separare costruzione geometria da scrittura msp.
