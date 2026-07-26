# forge — mappa architetturale
> Documento di riferimento per sessioni di refactoring.
> Risponde a tre domande: quali tipi esistono, come viaggia un dato, cosa si elimina.

---

## 1. Il problema attuale in una frase

Lo stesso concetto — "forma geometrica" — è rappresentato da tipi diversi
in punti diversi della codebase, e nessuno di essi è autosufficiente:
chi ne ha bisogno va a leggere `source_ref` come se fosse ezdxf.

---

## 2. I tipi che esistono oggi e cosa fanno davvero

### `core/primitives/segments.py`
Segmenti geometrici puri. Zero dipendenze esterne.

| Tipo | Dati | Scopo reale |
|---|---|---|
| `LineSeg` | start, end | segmento rettilineo |
| `ArcSeg` | center, radius, start_angle, end_angle, clockwise | arco |
| `SplineSeg` | control_points, knots, degree | spline |
| `DiscretizedArcSeg` | pts | arco approssimato a punti |
| `CircularArcSeg` | center, radius, start_angle, end_angle | arco circolare (usato da hole_detector) |

**Questi tipi fanno una cosa sola e la fanno bene. Non toccarli.**

---

### `core/primitives/contour.py` — DUPLICATO
`Contour` costruisce un `Polygon` shapely da una lista di primitive.
Non ha `source_ref`, non ha `origin`. È un passaggio intermedio
che esiste come classe ma dovrebbe essere una funzione.

**→ Da eliminare come tipo pubblico. La logica di costruzione del
poligono è geometria pura — va in `core/primitives/contour.py`
come funzione `build_polygon(primitives) -> Polygon`.
L'adapter la chiama, ma non la possiede.**

---

### `model/shape_proxy.py` — SOVRACCARICO
`ShapeProxy` nasce per le forme chiuse della hierarchy, ma viene usato
anche per forme aperte (linee, archi, bending). I due casi non hanno
niente in comune tranne `origin` e `source_ref`.

**Campi attuali:**
```
polygon      → ha senso solo per forme chiuse
origin       → comune a tutti
source_ref   → comune a tutti (opaco, per write-back)
shape_type   → "circle"|"polyline"|"spline"|"line"|"arc"|"virtual"
is_virtual   → flag ad hoc
diameter     → solo per cerchi
center       → solo per cerchi
```

**Il problema:** per le forme aperte (`shape_type = "line"`, `"arc"`)
non ci sono dati geometrici — solo `source_ref`. Quindi `detect.py`
chiama `source_ref.dxftype()`, `source_ref.dxf.start`, ecc.
Questo è il punto esatto dove rientra la dipendenza DXF nel core.

**→ Vedere sezione 4: cosa fare.**

---

### `model/part.py` — `ForgeContour`
Forma chiusa con `polygon` e `source_ref`, usata dentro `ForgePart`
come `part.outer` e `part.inners`.

**→ È la rappresentazione finale di una forma chiusa dopo la hierarchy.
Diversa da `ShapeProxy` per scopo (non è input della hierarchy, è output).
Il nome è giusto. Va tenuta.**

---

### `model/edge.py` — `Edge` e `BendingLine`

`Edge` è l'input del grafo topologico — porta un segmento grezzo
con `source_ref` opaco. Non è una forma, è un arco del grafo.

`BendingLine` è output semantico di `detect()` — porta geometria
shapely, `angle_deg`, `part_label`, `source_ref`. Non è una forma,
è un risultato classificato.

**→ Entrambi corretti. Nessuna sovrapposizione con gli altri tipi.**

---

### `model/classified.py` — `ClassifiedEntity`
Output di `detect()` per forme non-hole (engrave, marking, bending
libero). Porta `work_type`, `confidence`, `source`, `data`, `source_ref`.

**→ Corretto. Ma `_probe_point` in `detect.py` accede a `source_ref`
come ezdxf per ricavare un punto rappresentativo — questo va risolto
(vedi sezione 4).**

---

## 3. Come viaggia una forma chiusa nella pipeline

```
entità (e.g. un DXF)
    │
    │  adapter DXF — unico punto che tocca ezdxf
    ▼
ShapeProxy
    polygon:    Polygon shapely    ← costruito dall'adapter
    origin:     str                ← layer DXF tradotto
    source_ref: entità ezdxf       ← opaco da qui in poi
    shape_type: "circle" ecc.
    │
    │  HealStep — hierarchy, topology, loop detection
    ▼
ForgeContour  (part.outer, part.inners[])
    polygon:    Polygon shapely
    source_ref: opaco
    │
    │  detect() — semantica
    ▼
Hole / BendingLine / ClassifiedEntity
    │
    │  inject() — metriche CAM
    │  write()  — write-back DXF via source_ref
    ▼
output (DXF healato, JSON, split)
```

**Il contratto:** da `ShapeProxy` in poi, nessuno sa che il formato
è DXF. `source_ref` è opaco. Chi viola questo contratto introduce
una dipendenza DXF nel core.

---

## 4. Il problema aperto: forme aperte in `ShapeProxy`

`trash_entities: List[ShapeProxy]` contiene anche forme aperte
(linee, archi) che non hanno `polygon`. Per queste forme, `detect.py`
accede a `source_ref` come ezdxf — violazione del contratto.

**Soluzione: due tipi distinti.**

```python
# model/shape.py  ← file nuovo, sostituisce shape_proxy.py

@dataclass
class ClosedShape:
    """
    Forma chiusa pronta per la hierarchy.
    Prodotta dall'adapter, consumata da HealStep.
    """
    polygon:    Polygon
    origin:     str
    source_ref: Any
    shape_type: str          # "circle" | "polyline" | "spline" | "virtual"
    diameter:   Optional[float] = None
    center:     Optional[Tuple[float, float]] = None


@dataclass
class OpenShape:
    """
    Forma aperta (linea, arco, spline aperta).
    Prodotta dall'adapter, consumata da detect().
    Porta i dati geometrici necessari — zero accesso a source_ref nel core.
    """
    shape_type:  str                              # "line" | "arc" | "spline"
    origin:      str
    source_ref:  Any                              # opaco, per write-back
    pts:         Tuple[Tuple[float, float], ...]  # start/end per line, center per arc
    length:      float
```

**Conseguenze:**
- `trash_entities` diventa `List[OpenShape]`
- `detect.py` legge `shape.pts` e `shape.length` — zero `dxftype()`
- `_probe_point` scompare — il punto rappresentativo è `pts[0]`
  o la media di `pts`
- `_shape_length` scompare — è già in `length`
- L'adapter DXF popola `pts` e `length` una volta sola

---

## 5. Cosa eliminare

| Tipo / file | Azione | Motivo |
|---|---|---|
| `core/primitives/contour.py` — `Contour` | eliminare come classe | passaggio intermedio, sostituito da `build_polygon()` in `core/primitives/polygon_builder.py` |
| `model/shape_proxy.py` — `ShapeProxy` | rinominare + sdoppiare | `ClosedShape` per forme chiuse, `OpenShape` per forme aperte |
| `pipeline/detect.py` — `_probe_point` | eliminare | sostituito da `OpenShape.pts` |
| `pipeline/detect.py` — `_shape_length` | eliminare | sostituito da `OpenShape.length` |
| `pipeline/detect.py` — `_extract_data` (parte bending) | semplificare | legge da `OpenShape.pts` invece di `source_ref` |

---

## 6. Cosa NON toccare

- `core/primitives/segments.py` — corretto, stabile
- `model/edge.py` — `Edge` e `BendingLine` corretti
- `model/part.py` — `ForgeContour` e `ForgePart` corretti
- `model/hole.py` — `Hole` corretto
- `model/classified.py` — `ClassifiedEntity` corretto (solo `_probe_point` da correggere)
- `core/topology/` — grafo e loop corretti
- `core/healing/` — hierarchy e gap solver corretti
- `rules/layers.py` — corretto

---

## 7. Ordine di esecuzione (prossime sessioni)

**Sessione A — modello**
1. Creare `model/shape.py` con `ClosedShape` e `OpenShape`
2. Eliminare `model/shape_proxy.py`
3. Aggiornare `core/adapter_base.py` — `to_proxies()` → `to_closed()` + `to_open()`
4. Aggiornare `adapters/dxf/adapter.py` — popola `pts` e `length` su `OpenShape`
5. Test verdi

**Sessione B — detect**
1. Riscrivere `_detect_bending` usando `OpenShape.pts`
2. Eliminare `_probe_point`, `_shape_length`
3. Semplificare `_extract_data`
4. Test verdi

**Sessione C — eliminate Contour**
1. Creare `core/primitives/polygon_builder.py` con `build_polygon(primitives) -> Polygon`
2. Sostituire tutti gli usi di `Contour` con la funzione
3. Eliminare `core/primitives/contour.py`
4. Test verdi

**Sessione D — inject**
1. Rimuovere `msp` dalla firma di `inject()`
2. Riscrivere `_inject_bending` usando `BendingLine.geometry` (già shapely)
3. Riscrivere `_extract_texts_for_part` senza `get_representative_point(source_ref)`
4. Test verdi

---

## 8. Invarianti da non violare mai

1. **Nessun import ezdxf fuori da `adapters/dxf/`** — mai in `core/`, `model/`, `pipeline/`
2. **`source_ref` è opaco** — chi lo riceve non chiama `.dxftype()`, `.dxf.*`, niente
3. **Un tipo per concetto** — forme chiuse: `ClosedShape`; forme aperte: `OpenShape`; segmenti: `*Seg`; risultato classificato: `ClassifiedEntity` / `Hole` / `BendingLine`
4. **L'adapter è l'unico che sa del formato** — tutto ciò che serve al core deve essere estratto e tradotto lì