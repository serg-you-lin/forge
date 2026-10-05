# forge

**Motore di geometria 2D deterministico per il disegno tecnico e la geometria CAD.**

`forge` prende un disegno 2D disordinato e ne ricava un modello pulito e senza
perdite — contorni chiusi ricuciti, la loro gerarchia di contenimento, le
annotazioni del disegno, e un overlay aperto dove si attaccano le feature
rilevate — poi lo riscrive in DXF (un documento, o uno per pezzo), JSON/XML, SVG,
un view model per una UI, o (sperimentale) una lettura testuale compatta per un
modello linguistico. Il prodotto è il
modello; un formato CAD è solo una porta di entrata o di uscita. Oggi quella porta
è il DXF (DWG via ODA), gestita da un solo adapter — tutto ciò che sta a valle
lavora sul modello neutro rispetto al formato.

La parte che nessun altro strumento fa per te è l'**healing**: ricucire la
geometria rotta — matasse di `LINE`/`ARC` da un export CAM, il DXF di un cliente,
un vecchio file R12 — in contorni chiusi.

**Non è una libreria DXF** e **non è uno strumento per la lamiera**. La lamiera
e la piastra sono il contesto in cui forge è nato, e il suo primo consumatore, non
il suo confine: il motore non conosce materiale, processo né prodotto. Leggere la
geometria come "un foro da forare" o "una piega" è interpretazione del
consumatore (`snapbend` per la lamiera, `snapdraw` per la notazione del disegno):
forge non ha letture di quel tipo dentro, così un consumatore di qualunque
dominio ottiene la stessa geometria e ci mette sopra il suo vocabolario
attraverso un overlay aperto (`cluster.detected`).

> Stato: **alpha**. In produzione, ma l'API si muove ancora. Vedi `MAP.md` per le decisioni di design correnti.

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
result = forge.heal(doc)                              # topologia: contorni chiusi, outer/inner
#   fori, pieghe, incisioni sono una lettura di processo sopra: snapbend.flat.detect_flat

if not result.is_valid:                              # nessun contorno esterno chiuso
    print(result.errors)                              # si disegna lo stesso, vedi "Limiti noti"

doc_out = forge.to_dxf(result, doc)                   # -> ezdxf Drawing
doc_out.saveas("pezzo_healed.dxf")

forge.save_json(result, "pezzo.json")                 # metadati
cerchi = [c for cl in result.clusters for c in cl.inners
          if forge.geometry.contour_shape(c).kind == "circle"]
print(f"{result.cluster_count} cluster, {len(cerchi)} cerchi interni")
```

## File multi-pezzo

```python
import forge

doc    = forge.load_dxf("batch.dxf")
result = forge.split_to_files(doc, "output/", label="batch")
# scrive output/batch_P1.dxf, output/batch_P2.dxf, ... uno per pezzo
# (namer=lambda i, cluster: "..." per scegliere i nomi dei file)
forge.save_json(result, "batch.json")
```

## Un disegno di viste (più viste, isometrica)

```python
import forge

doc    = forge.load_dxf("tavola.dxf")       # cornice / cartiglio marcati per ruolo, o tolti
result = forge.island(doc, island_gap=10.0, max_gap=0.5)
for cluster in result.clusters:              # una vista (o un pezzo) per isola
    print(cluster.outer.polygon.area, len(cluster.inners))
```

`heal()` legge un disegno di sagome piane separate dall'interno (quali giri si chiudono, chi sta
dentro chi). `island()` legge un disegno di viste dall'esterno: isole per
vicinanza, poi il contorno esterno di ognuna come faccia esterna della sua rete
piana. Stesso `ForgeResult` in uscita — vedi `docs/API.md` (`island`).

Tutte e due sono ricette su passi pubblici. I passi di `heal()` (`split_labeled`,
`close_free_gaps`, `find_loops`, `build_hierarchy`, ...) sono esportati uno per
uno, così un consumatore compone il suo ordine — vedi `docs/API.md` (i passi di
`heal()`).

## Disegnare con forge

```python
import forge

fg = forge.geometry
doc = forge.load_segments(fg.rectangle(200, 100) + fg.rectangle(100, 50))
result = forge.heal(doc)                # un pezzo: outer 200×100, un inner 100×50
forge.to_dxf(result, doc).saveas("due_rettangoli.dxf")
```

I costruttori restituiscono segmenti di forge: `polygon(punti)`, `rectangle`,
`regular_polygon`, `circle`, `stadium` (con archi veri). Ogni altra forma a lati
dritti è un `polygon`.

## Forme: cos'è un contorno, non a cosa serve

forge dà nomi alla geometria, mai al suo uso. Un cerchio è un cerchio; se sia un
foro da forare, una sede o il puntino di un logo lo legge un consumatore
(snapbend per il pezzo, snapdraw per la notazione del disegno — D68, D91).

```python
for cluster in result.clusters:
    for inner in cluster.inners:
        shape = forge.geometry.contour_shape(inner)     # circle / stadium / rectangle / polygon / other
        print(shape.kind, shape.center, shape.length, shape.width)

    # cerchi con lo stesso centro, dal più piccolo (anche quelli da soli)
    for group in forge.geometry.concentric_groups(cluster.inners, tolerance=0.1):
        if len(group.items) > 1:
            print("concentrici:", group.center, group.diameters)

# archi concentrici a un cerchio e più grandi: angolo in gradi, rapporto dei raggi
for found in forge.geometry.arcs_around((10, 20), 2.5, result.all_arcs, tolerance=0.1):
    print(found.sweep, found.radius_ratio)
```

Dentro non ci sono soglie di significato: "~270° e poco più grande" è come un
disegno mostra un filetto, e quella regola sta nel consumatore.

## Linee di piega / incisione che sai già riconoscere

Se sai come la sorgente segna pieghe o incisioni — per nome, per tratteggio,
per colore o una combinazione — dillo a `load_dxf` con delle regole, così
assegna il ruolo subito invece di indovinarlo. Le regole si valutano in
ordine, vince la prima che matcha:

```python
doc = forge.load_dxf("pezzo.dxf", role_rules=[
    *forge.name_rules({"Piega": "bending", "MARK": "engrave"}),
    forge.RoleRule("construction", name_contains="constr", dashed=True),
    forge.RoleRule("bending", dashed=True),
])
```

---

## La pipeline

```
load_dxf(path)  ──►  ForgeDocument   (edge + annotazioni + source_meta)
                          │            l'unico passo che legge con ezdxf
                          ▼
     heal(doc)  ──►  ForgeResult      topologia: gap chiusi, giri trovati,
                          │            albero di contenimento outer / inner
                          ▼
  (la lettura di un consumatore)       es. snapbend: tipo di foro, linee di piega, incisioni,
                          │            attaccate a cluster.detected
                          ▼
   to_dxf(result, doc)  ──►  ezdxf Drawing        render — un documento
   split(result, doc)   ──►  list[Drawing]        render — uno per pezzo
   to_svg(result)       ──►  stringa SVG          render — per una UI / un report
   to_view_model(result)  ─►  dict (geometria completa) per un renderer esterno
   to_text(result)      ──►  Markdown              sperimentale: una lettura per un modello linguistico (D84)
   save_json / save_xml                           export del modello (metadati)
   inject(result, ...)                            arricchimento opzionale dai testi
```

Il prodotto è il modello. `to_dxf` non rilegge mai il file sorgente — ogni renderer
(DXF, SVG, view model) disegna dallo stesso modello, quindi mostrano tutti la stessa cosa.

---

## Layer del DXF in uscita

| Layer          | Significato                                 |
|----------------|---------------------------------------------|
| `OuterContour` | profilo esterno del pezzo                   |
| `InnerContour` | contorno chiuso dentro l'outer              |
| `Annotation`   | testi e quote della sorgente (non è un layer di taglio) |
| *nome del ruolo* | geometria con il ruolo di un consumatore (`frame`, `hole`, `bending`, …): un layer suo, nome e colore da `register_role_style` se il consumatore l'ha registrato |
| `Trash`        | tutto ciò che `forge` non ha saputo classificare — tenuto, mai buttato |

Niente della sorgente si perde in silenzio: la geometria non classificata va in
`Trash`, testi e quote in `Annotation`. I tipi di entità che `forge` non modella
(`HATCH`, `IMAGE`, `TABLE`, …) li segnala `load_dxf` con un warning, non li butta.

---

## Ispezionare un file reale

Tre livelli, come la pipeline:

```python
import forge

forge.inspect_dxf("pezzo.dxf")       # 1 — entità DXF grezze: cosa c'è nel file
forge.inspect_document(doc)          # 2 — edge, primitive, grafo dei nodi: cosa ha capito l'adapter
forge.inspect_result(result)         # 3 — il modello: cluster, outer/inner, quello che un consumatore ha attaccato, trash

forge.inspect_file("pezzo.dxf", role_rules=forge.name_rules({"Piega": "bending"}))   # tutti e tre, in fila
```

Tutto stampa su stdout. Serve quando qualcosa su un file vero non esce giusto e
devi vedere dove si rompe la catena.

---

## Geometria in ingresso supportata

- **Come contorni strutturali:** `LWPOLYLINE`, `POLYLINE`, `CIRCLE`, `SPLINE` chiusa, `ELLIPSE` chiusa
- **Da ricostruire in contorni:** `LINE`, `ARC`, `SPLINE`/`ELLIPSE` aperte collegate ad altre entità
- **Come annotazioni:** `TEXT`, `MTEXT`, `DIMENSION`, `LEADER`, `MULTILEADER`
- **Blocchi:** gli `INSERT` si esplodono al caricamento, di default
- **Legacy:** i file R12/R13/R14 si aggiornano a R2010
- **DWG:** né `forge` né `ezdxf` leggono il DWG direttamente — passa da
  [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter)
  (gratuito). Installalo e indica a `forge` l'eseguibile con la variabile
  d'ambiente `ODA_PATH` (percorso completo dell'eseguibile), o metti
  `ODAFileConverter` nel `PATH`. Vedi `docs/API.md` → *load_dxf → DWG* per i
  singoli sistemi operativi.

---

## Limiti noti

- **Spline ed ellissi** escono native sui layer di taglio (`to_dxf`) ma
  **discretizzate** in `to_svg` / `to_view_model` (polilinee: usa `to_dxf`
  quando conta la curva esatta).
- **`load_pdf`** esiste ma è sperimentale — ritorna edge grezzi, non un
  `ForgeDocument`, quindi non si aggancia ancora a `heal()`. Non è nell'API pubblica.
- **Gap arco/arco oltre la tolleranza** non si chiudono da soli — alza `tolerance`.
- Se non si riesce a formare un contorno esterno chiuso, `result.is_valid` è
  `False`. `to_dxf` / `to_svg` disegnano comunque quello che c'è (tutto su
  `Trash`), così vedi cosa ha capito forge; chi manda l'output a una macchina
  passa `allow_invalid=False` e riceve `ValueError`. `split` solleva sempre:
  un file per pezzo non ha senso senza pezzi.

---

## Documentazione

- **[`docs/API.md`](docs/API.md)** — ogni funzione pubblica: firma, cosa prende,
  cosa ritorna, cosa muta, quando solleva. Con esempi copiabili.
- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** — com'è fatto dentro e
  perché: gli strati, il flusso, "il prodotto è il modello".
- **`MAP.md`** — le decisioni di design, in ordine cronologico.
- **[`docs/LLM.md`](docs/LLM.md)** — riferimento compatto per un'AI che scrive
  codice contro forge: stesso contenuto di `API.md`, meno token possibile.
- **`SCRIPTS.md`** — gli script numerati in `scripts/`, uno per passo della pipeline.

---

## Licenza

Tutti i diritti riservati — vedi [`LICENSE`](LICENSE). Copyright (c) 2026
Federico Sidraschi. Non è open source; per provarlo o usarlo, scrivimi:
smia4punto6@gmail.com.
