# Vecchi script numerati — archiviati 2026-08-29

Sostituiti dalla nuova serie `00_*.py … 12_*.py` alla radice (uno per area di
`forge.__all__`, + `11_batch_heal.py` batch su cartella e `12_to_svg.py`; vedi
MAP.md D14).

Quasi tutti usavano API morte (`forge.validate_msp`, `forge.heal(msp, ...)`,
`forge.classify`, `load_dxf` che ritornava `(doc, msp)`, `edge.geometry`).
Tenuti qui solo come riferimento storico.

- `00_print_entities.py` → ora `00_inspect.py` (inspector a 3 livelli)
- `01_run_healer_interpreter.py` → `01_load_and_validate.py` + `02_heal.py`
- `02_run_splitter.py` → `06_split.py` + `07_split_to_files.py`
- `03_pipeline_metadata.py` → `09_export.py` + `10_metadata_xdata.py`
- `04_pipeline_healing_cases.py` → ora `11_batch_heal.py` (heal di tutta una cartella)
- `11_pipeline_splitter_cases.py` → batch splitter con anti-ricorsione, non ricreato
- `14_preprocessing_healing.py` → sanitize + heal su file cliente, non ricreato
- `15_run_frame_detector.py` / `16_remove_frame_and_heal.py` → `extract_frame_handles`
  è un helper interno (`forge.adapters.dxf.frame_adapter_dxf`), non API pubblica.
  Se serve, va prima promosso in `forge.__all__`.
- `18_pdf_healing.py` → `load_pdf` è congelato (MAP.md D10).

`13_ARC_splitter_injected_fuzzy_new.py` NON è qui: resta alla radice, è codice di
produzione su file cliente, va portato alla nuova API in una sessione dedicata.
