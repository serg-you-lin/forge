"""
forge
---------
DXF geometry preprocessor for manufacturing pipelines.

API pubblica — tutto quello che serve è qui.
Non devi importare i moduli interni direttamente.

Workflow consigliato (file singolo):
    import forge

    doc, msp = forge.load_dxf("pezzo.dxf")

    check = forge.validate_msp(msp)
    if not check.is_valid:
        print(check.errors)
        exit()

    result = forge.heal(msp, label="pezzo", source_file="pezzo.dxf")
    forge.detect(result)
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
from .adapters.pdf.loader import load_pdf
from .pipeline            import heal, split_to_files
from .rules.layers import LAYER_OUTER, LAYER_HOLE
from .pipeline.inject   import inject
from .pipeline.write  import write, split
from .pipeline.detect  import detect
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
from .model         import ForgeResult, ForgePart, ForgeContour
from .io.text_utils       import extract_texts_from_msp

__version__ = "0.5.0"

__all__ = [
    # Apertura file
    "load_dxf",
    "load_pdf",
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