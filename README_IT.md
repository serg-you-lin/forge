# forge

**Preprocessore di geometria 2D per la fabbricazione di lamiera / piastra.**

`forge` prende un disegno 2D disordinato — una matassa di `LINE`/`ARC` sputata da
una macchina CAM, il DXF di un cliente, un file R12 vecchio — e ne ricava un
modello pulito e strutturato: profili esterni chiusi, aperture interne, fori
(passanti / svasati / filettati), linee di piega, tracce di incisione. Quel
modello si può poi riscrivere in DXF (un file per pezzo), esportare come metadati
JSON/XML, o passare al nesting.

La parte che nessun'altra libreria DXF fa per te è l'**healing**: ricucire la
geometria rotta in contorni chiusi.

> Stato: **alpha**. In produzione per la preparazione al taglio laser/plasma, ma
> l'API si muove ancora. Vedi `MAP.md` per le decisioni di design correnti.

---

## Installazione

```bash
pip install -e .            # da un clone
pip install -e ".[pdf]"     # + input PDF sperimentale
```

Dipendenze: `ezdxf`, `shapely`, `numpy` (Python ≥ 3.10).

---

## Esempio — file singolo

```python
import forge

doc    = forge.load_dxf("pezzo.dxf", tolerance=0.5)   # -> ForgeDocument
result = forge.heal_and_detect(doc)                   # topologia + fori/pieghe/incisioni
#   == forge.heal(doc) poi forge.detect(result); chiamali separati se ti serve
#      la sola topologia

if not result.is_valid:
    raise SystemExit(result.errors)

forge.to_dxf(result, doc).saveas("pezzo_healed.dxf")
forge.save_json(result, "pezzo.json")
```

## File multi-pezzo

```python
doc    = forge.load_dxf("batch.dxf")
result = forge.split_to_files(doc, "output/", label="batch")   # un file per pezzo
forge.save_json(result, "batch.json")
```

## Layer di piega / incisione che già conosci

```python
doc = forge.load_dxf("pezzo.dxf",
                     label_map={"Piega": "bending", "MARK": "engrave"})
```

---

## Ispezionare un file reale

```python
forge.inspect_file("pezzo.dxf", label_map={"Piega": "bending"})
```

Stampa tre livelli in fila: entità DXF grezze → cosa ha capito l'adapter → il
modello prodotto. Serve quando qualcosa su un file vero non esce giusto e devi
vedere dove si rompe la catena.

---

## Documentazione

- **[`docs/API.md`](docs/API.md)** — ogni funzione: firma, cosa prende, cosa
  ritorna, cosa muta, quando solleva. Con esempi copiabili. È il documento per
  spiegare `forge` a qualcuno.
- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** — com'è fatto dentro e
  perché: gli strati, il flusso, il principio "il prodotto è il modello".
- **`MAP.md`** — le decisioni di design prese, in ordine cronologico.
