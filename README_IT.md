# dxf-forge

Libreria Python per processare file DXF provenienti da macchine CAM e software di taglio laser/plasma.

Gestisce file "sporchi" — geometrie rotte, entità miste, file con più pezzi nello stesso spazio — e li normalizza in strutture usabili.

---

## Il problema che risolve

I file DXF che escono dal CAD raramente sono puliti. Tipicamente:

- Il contorno di un pezzo è fatto di decine di `LINE` e `ARC` separati, non collegati
- Più pezzi diversi vivono nello stesso file, sovrapposti o affiancati
- Fori e contorni interni non sono classificati
- Entità di lavorazione (marcature, piegature) sono mescolate alla geometria strutturale

dxf-forge prende questi file e li normalizza: ricostruisce i contorni, classifica outer/inner/hole, separa i pezzi in file distinti.

---

## Cosa fa

### `heal(msp)`
Ripara la geometria di un modelspace ezdxf.

- Riconnette `LINE` e `ARC` sparsi in `LWPOLYLINE` chiuse
- Classifica i contorni: `OuterContour`, `InnerContour`, `Hole`
- Gestisce `CIRCLE`, `SPLINE` chiuse, `ELLIPSE`
- Chiude gap piccoli tra segmenti (tolleranza configurabile)
- Separa le entità su layer speciali (marcature, piegature) dalla geometria strutturale
- Restituisce un `ForgeResult` con tutti i `ForgePart` trovati

```python
doc = ezdxf.readfile("pezzo.dxf")
msp = doc.modelspace()
result = forge.heal(msp, tolerance=0.5, write_to_msp=True)

print(f"Pezzi trovati: {result.part_count}")
for part in result.parts:
    print(f"  Area: {part.area:.1f} mm²  Fori: {len(part.inners)}")
```

### `split_to_files(msp, output_folder)`
Divide un file con più pezzi in N file figli, uno per pezzo.

- Heala internamente (o riusa un `heal_result` già fatto)
- Salva un DXF per ogni `ForgePart` trovato
- Copia le entità extra (marcature, testi, ecc.) nel file figlio corretto
- Supporta un `namer` custom per i nomi dei file

```python
result = forge.split_to_files(
    msp,
    output_folder="output/",
    label="codice_pezzo",
    source_file="multiplo.dxf",
)
```

### `is_multi(result)`
Restituisce `True` se il file contiene più di un pezzo.

```python
result = forge.heal(msp, write_to_msp=True)
if forge.is_multi(result):
    forge.split_to_files(msp, output_folder="output/", heal_result=result)
else:
    forge.write_metadata_to_dxf(doc, result.parts[0])
    doc.saveas("output/pezzo.dxf")
```

### Metadati
I metadati geometrici (area, perimetro, bbox, fori) vengono scritti come XDATA nel DXF e possono essere esportati in JSON o XML.

```python
forge.write_metadata_to_dxf(doc, part)
forge.save_json(result, "metadata.json")
forge.save_xml(result, "metadata.xml")
```

---

## Layer strutturali

| Layer | Significato |
|---|---|
| `OuterContour` | Contorno esterno del pezzo |
| `InnerContour` | Apertura interna (asola, cava) |
| `Hole` | Foro circolare (diametro < 32.1 mm) |
| `Trash` | Entità non classificate |

---

## Tipi geometrici supportati

Come contorni strutturali: `LWPOLYLINE`, `CIRCLE`, `SPLINE` chiusa, `ELLIPSE`

Come geometria da ricostruire: `LINE`, `ARC`, `SPLINE` aperta connessa

---

## Dipendenze

```
ezdxf
shapely
numpy
```

---

## Struttura

```
dxf_forge/
  healer.py      — riparazione geometria, cuore della libreria
  splitter.py    — divisione file multipli
  geometry.py    — funzioni geometriche pure
  graph.py       — grafo topologico per trovare loop chiusi
  virtual.py     — rappresentazione in memoria dei loop
  classifier.py  — classificazione entità extra per layer/colore
  exporter.py    — serializzazione JSON/XML/XDATA
  validator.py   — validazione pre-healing
  models.py      — ForgeResult, ForgePart, ForgeContour
  layers.py      — unica fonte di verità per nomi layer e colori
```

---

## Note

Progetto sperimentale. Nato per gestire file reali da macchine CAM in un contesto di taglio laser/plasma. Non è una libreria general-purpose per DXF — è specializzata su un problema specifico.