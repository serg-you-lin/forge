"""
dxf-forge
---------
DXF geometry preprocessor for manufacturing pipelines.

API pubblica — tutto quello che serve è qui.
Non devi importare i moduli interni direttamente.

Workflow consigliato (file singolo):
    import dxf_forge as forge

    doc, msp = forge.load_dxf("pezzo.dxf")

    check = forge.validate_msp(msp)
    if not check.is_valid:
        print(check.errors)
        exit()

    result = forge.heal(msp, label="pezzo", source_file="pezzo.dxf")
    forge.detect(result, msp)
    forge.write(msp, result)
    forge.inject(msp, result)
    doc.saveas("pezzo_healed.dxf")
    forge.save_json(result, "pezzo.json")

Workflow multi-pezzo:
    doc, msp = forge.load_dxf("batch.dxf", upgrade=True)
    result = forge.split_to_files(
        msp, "output/",
        label="batch",
        source_file="batch.dxf",
    )
    forge.save_json(result, "batch.json")
"""

from .adapters.dxf.loader import load_dxf
from .workflow.healer     import heal, LAYER_OUTER, LAYER_HOLE
from .workflow.splitter   import split_to_files
from .workflow.injector   import inject
from .workflow.writeback  import write, split
from .workflow.detection  import detect
from .rules.validator     import validate, validate_msp
from .io.exporter         import (
    to_json,
    save_json,
    save_xml,
    to_nester_input,
    write_metadata_to_dxf,
    read_metadata_from_dxf,
    set_schema,
)
from .core.models         import ForgeResult, ForgePart, ForgeContour
from .io.text_utils       import extract_texts_from_msp

__version__ = "0.11.3"

__all__ = [
    # Apertura file
    "load_dxf",
    # Validazione
    "validate",
    "validate_msp",
    # Workflow
    "heal",
    "detect",
    "write",
    "split",
    "inject",
    "split_to_files",
    # Export
    "to_json",
    "save_json",
    "save_xml",
    "to_nester_input",
    # Metadati DXF
    "write_metadata_to_dxf",
    "read_metadata_from_dxf",
    "set_schema",
    # Utilità
    "extract_texts_from_msp",
    # Modelli
    "ForgeResult",
    "ForgePart",
    "ForgeContour",
    # Costanti layer
    "LAYER_OUTER",
    "LAYER_HOLE",
]