"""
dxf-forge
---------
DXF geometry preprocessor for manufacturing pipelines.

API pubblica — tutto quello che serve è qui.
Non devi importare i moduli interni direttamente.

Workflow file singolo:
    import ezdxf
    import dxf_forge as forge

    doc = ezdxf.readfile("pezzo.dxf")
    msp = doc.modelspace()

    check = forge.validate_msp(msp)
    if not check.is_valid:
        print(check.errors)
        exit()

    result = forge.heal(msp, label="pezzo", source_file="pezzo.dxf")
    forge.classify(msp, result.parts, extra_metadata={"material": "S235", "thickness": 2.0})
    forge.write_metadata_to_dxf(doc, result.parts[0])
    doc.saveas("pezzo_healed.dxf")
    forge.save_json(result, "pezzo.json")

Workflow multi-pezzo (split_to_files fa tutto internamente):
    result = forge.split_to_files(
        msp, "output/",
        label="batch",
        source_file="batch.dxf",
        extra_metadata={"material": "S235", "thickness": 3.0},
    )
    forge.save_json(result, "batch.json")
"""

from .workflow.healer     import heal, LAYER_OUTER, LAYER_HOLE
from .workflow.splitter   import split_to_files 
from .workflow.injector    import inject
from .workflow.writeback import write, split
from .rules.validator  import validate, validate_msp
from .workflow.detection import detect
from .io.exporter import (to_json, save_json, save_xml, to_nester_input,
                       write_metadata_to_dxf, read_metadata_from_dxf, 
                       upgrade_to_r2010, set_schema)
from .core.models     import ForgeResult, ForgePart, ForgeContour
from .io.text_utils import extract_texts_from_msp

__version__ = "0.10.1"
__all__ = [
    # Workflow file singolo
    "validate_msp",
    "heal",
    "inject",
    "detect",
    "write_metadata_to_dxf",
    "read_metadata_from_dxf",
    # Workflow multi-pezzo
    "split_to_files",
    "write",
    "split",
    # Export
    "validate",
    "to_json",
    "save_json",
    "save_xml",
    "to_nester_input",
    "upgrade_to_r2010",
    # Configurazione
    "DEFAULT_ENTITY_MAP",
    # Modelli
    "ForgeResult",
    "ForgePart",
    "ForgeContour",
    # Costanti layer
    "LAYER_OUTER",
    "LAYER_HOLE",
]