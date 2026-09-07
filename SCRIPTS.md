# Script numerati — palestra dell'API

Serie di script standalone in `scripts/`, uno per area di `forge.__all__`.
Ognuno ha un blocco `CONFIG` in testa (INPUT, tolleranza, label_map) e gira
senza argomenti:

```
python scripts/00_inspect.py
```

Gli input di default puntano a `tests/examples/`. Gli output vanno in
`pipeline_output/` (ignorato da git).

**Percorsi — un solo modo.** La prima riga di ogni script è `import _paths`
(vedi `scripts/_paths.py`): fa `os.chdir()` alla radice del repo, quindi da
riga di comando, dal pulsante Run di VS Code o da un terminale aperto in
un'altra cartella il comportamento è identico. Nel blocco `CONFIG` si scrive il
percorso grezzo e basta:

```python
import _paths  # noqa: F401

INPUT  = r"tests/examples/Multifeature.dxf"   # relativo → parte dal repo
INPUT  = r"C:\job\disegno_cliente.dxf"        # assoluto → usato com'è
OUTDIR = r"pipeline_output"                   # scritto in <repo>/pipeline_output
```

| # | script | funzioni forge | cosa mostra |
|---|--------|----------------|-------------|
| 00 | `00_inspect.py` | `inspect_file`, `inspect_dxf`, `inspect_document`, `inspect_result` | l'ispettore a 3 livelli — il primo strumento su un file che non torna |
| 01 | `01_load_and_validate.py` | `load_dxf`, `document_from_msp`, `validate` | aprire un file → `ForgeDocument`; validare l'input |
| 02 | `02_heal.py` | `heal`, `validate_result` | ricostruzione topologia → parti, albero outer/inner (niente fori) |
| 03 | `03_detect.py` | `detect`, `ALL_FEATURES` | classificazione feature: nudo vs `"holes"`/`"bending"`/`"all"`, `max_drill_diameter` |
| 04 | `04_heal_and_detect.py` | `heal_and_detect` | la via del 90% — heal + detect in un colpo |
| 05 | `05_to_dxf.py` | `to_dxf` | render del modello in un DXF nuovo; `filter_cluster`, `include_trash` |
| 06 | `06_split.py` | `split` | un `Drawing` per parte (puro); `namer`, `on_cluster`, `exclude_types` |
| 07 | `07_split_to_files.py` | `split_to_files` | pipeline multi-pezzo completa su disco |
| 08 | `08_inject.py` | `extract_forge_texts`, `extract_texts_from_msp`, `inject` | arricchimento CAM dai testi del disegno |
| 09 | `09_export.py` | `to_json`, `save_json`, `save_xml`, `to_nester_input` | metadati fuori da forge |
| 10 | `10_metadata_xdata.py` | `write_metadata_to_dxf`, `read_metadata_from_dxf`, `set_schema` | metadati DENTRO il DXF (XDATA) + schema custom |
| 11 | `11_batch_heal.py` | `load_dxf` + `heal_and_detect` + `to_dxf` | heal di tutti i DXF di una cartella → `X_healed.dxf` + `.json` a fianco |
| 12 | `12_to_svg.py` | `to_view_model`, `to_svg`, `save_svg` | JSON per un renderer esterno + SVG del modello |
| 14 | `14_style_classification.py` | `load_dxf(linetype_map=..., color_map=...)` | classificare dal tratteggio/colore quando il layer non basta (Cluster E) |

`11_batch_heal.py` accetta una cartella come argomento (`python
scripts/11_batch_heal.py path/`) e `--tol`; senza argomenti processa
`tests/examples/`. Salta i file già `*_healed`.

I tipi di dominio (`ForgeResult`, `ForgeCluster`, `ForgeContour`, `ForgeDocument`,
`Annotation`) sono mostrati inline dentro gli script.

## Fuori serie

- `scripts/13_ARC_splitter_injected_fuzzy_new.py` — codice di produzione su file
  cliente, ancora su API pre-refactor (usa path assoluti propri, non `_paths`).
  Da portare alla nuova API in una sessione dedicata e collaudare con
  l'overlay-check in SigmaNest. Non versionato.
- `_archive/old_scripts/` — la vecchia serie numerata (API morte), tenuta come
  riferimento storico.
- `dev_tools/` — prototipi (grafo, dashboard, split verify). Base di partenza per
  la futura repo dashboard (MAP.md D16).
- `scripts/_paths.py` — `import _paths` come prima riga di ogni script della
  serie: `chdir` alla radice del repo. Non fa parte del package.
