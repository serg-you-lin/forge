"""
forge
---------
DXF geometry preprocessor for manufacturing pipelines.

API pubblica — tutto quello che serve è qui.
Non devi importare i moduli interni direttamente.

Workflow consigliato (file singolo):
    import forge

    doc = forge.load_dxf("pezzo.dxf", label_map={"Piega": "bending"})

    result = forge.heal(doc, label="pezzo", source_file="pezzo.dxf")
    forge.detect(result)
    doc_out = forge.to_dxf(result, doc)
    forge.inject(result)
    doc_out.saveas("pezzo_healed.dxf")
    forge.save_json(result, "pezzo.json")

Workflow multi-pezzo:
    doc = forge.load_dxf("batch.dxf", upgrade=True)
    result = forge.split_to_files(
        doc, "output/",
        label="batch",
        source_file="batch.dxf",
    )
    forge.save_json(result, "batch.json")

load_dxf() restituisce un ForgeDocument (edges + annotations + source_meta):
dopo di essa ezdxf non viene più toccato fino a to_dxf().

Materializzazione in DXF:
    doc_out       = forge.to_dxf(result, doc)      # un Drawing, tutte le parti
    docs          = forge.split(result, doc)       # un Drawing per parte (puro)
    forge.split_to_files(doc, "output/")           # split + saveas su disco
"""

from .adapters.dxf.loader import load_dxf, document_from_msp
# load_pdf: SPERIMENTALE, fuori dal contratto pubblico (vedi MAP.md D10).
# Ritorna list[Edge], non un ForgeDocument — NON passabile a forge.heal().
# Resta importabile come forge.load_pdf per chi ci lavora sopra, ma non è in
# __all__ e non è documentato: l'API può cambiare o sparire senza preavviso.
from .adapters.pdf.loader import load_pdf
from .pipeline            import heal, split_to_files
from .pipeline.inject   import inject
from .pipeline.write  import to_dxf, split
from .pipeline.detect  import detect
from .rules.validator     import validate, validate_result
from .io.exporter         import (
    to_json,
    save_json,
    save_xml,
    to_nester_input,
    write_metadata_to_dxf,
    read_metadata_from_dxf,
    set_schema,
)
from .model         import ForgeResult, ForgePart, ForgeContour, ForgeDocument, Annotation
from .io.text_utils       import extract_texts_from_msp
from .inspect             import (
    inspect_dxf, inspect_document, inspect_result, inspect_file,
)

try:
    from importlib.metadata import version as _pkg_version, PackageNotFoundError
    try:
        __version__ = _pkg_version("forge")
    except PackageNotFoundError:
        __version__ = "0.0.0+dev"
except ImportError:  # pragma: no cover
    __version__ = "0.0.0+dev"

__all__ = [
    # Apertura file
    "load_dxf",
    "document_from_msp",
    # Validazione
    "validate",
    "validate_result",
    # Workflow
    "heal",
    "detect",
    "to_dxf",
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
    # Ispezione / debug (3 livelli: DXF grezzo → ForgeDocument → ForgeResult)
    "inspect_dxf",
    "inspect_document",
    "inspect_result",
    "inspect_file",
    # Modelli
    "ForgeResult",
    "ForgePart",
    "ForgeContour",
    "ForgeDocument",
    "Annotation",
]