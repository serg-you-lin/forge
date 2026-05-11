# dxf-forge — TODO

Stato attuale: healing funzionante, export JSON/XDATA base, layer centralizzati.
Obiettivo: tool vendibile per normalizzazione DXF e estrazione metadati da taglio laser.

---


## PRIORITÀ ALTA — blocca il prodotto


sessione dedicata ai test



---

## PRIORITÀ MEDIA — migliora la qualità

### Hashing
bending lines nell'interpreter
creare una fingerprint geometrica per validare na forge part.


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

Agente

Astrazione ad esempio....
# core/geometry.py
_HANDLERS = {}

def register(dxftype):
    def decorator(fn):
        _HANDLERS[dxftype] = fn
        return fn
    return decorator

@register("LINE")
def _line_length(entity):
    ...

@register("ARC")
def _arc_length(entity):
    ...

def entity_length(entity):
    handler = _HANDLERS.get(entity.dxftype())
    if handler is None:
        return 0.0
    return handler(entity)


