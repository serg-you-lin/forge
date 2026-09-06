"""
forge
---------
DXF geometry preprocessor for manufacturing pipelines.

API pubblica — tutto quello che serve è qui.
Non devi importare i moduli interni direttamente.

Workflow consigliato (file singolo):
    import forge

    doc = forge.load_dxf("pezzo.dxf", label_map={"Piega": "bending"})
    # se il layer non basta: linetype_map={"DASHED": "bending"},
    # color_map={"cyan": "engrave"} — seconda lane, sull'aspetto grezzo,
    # usata solo dove label_map non ha già deciso dal layer

    result = forge.heal_and_detect(doc, label="pezzo", source_file="pezzo.dxf")
    # equivale a: result = forge.heal(doc, ...); forge.detect(result, "all")
    # forge.detect(result) nudo classifica solo i ruoli da label_map/linetype_map/color_map

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
# load_geometry: SPERIMENTALE, fuori dal contratto pubblico (vedi MAP.md).
# Costruisce un ForgeDocument da geometria pura (dict), non da un file — stesso
# contratto di ritorno di load_dxf, ma senza sorgente su disco. Pensato per
# generatori parametrici (es. sviluppi cono/cilindro) e ricostruttori di
# geometria da punti. Resta importabile come forge.load_geometry, non è in
# __all__ e non è documentato finché non è stato provato da un caso reale.
from .adapters.geometry.loader import load_geometry
from .pipeline            import heal, heal_and_detect, split_to_files
from .pipeline.inject   import inject
from .pipeline.write  import to_dxf, split
from .pipeline.detect  import detect, ALL_FEATURES
from .rules.validator     import validate, validate_result
from .io.exporter         import (
    to_json,
    save_json,
    save_xml,
    write_metadata_to_dxf,
    read_metadata_from_dxf,
    set_schema,
)
# to_nester_input: SPERIMENTALE, fuori dal contratto pubblico (vedi MAP.md D18).
# Scritto per un nester mai realizzato — dxf-forge non fa nesting. Resta
# importabile come forge.to_nester_input, ma non è in __all__ né documentato.
# Per serializzare la geometria a un renderer/tool usa forge.to_view_model().
from .io.exporter         import to_nester_input
from .io.view_model       import to_view_model
from .io.svg              import to_svg, save_svg
from .model         import ForgeResult, ForgePart, ForgeContour, ForgeDocument, Annotation
from .io.text_utils       import extract_texts_from_msp, extract_forge_texts
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
    "ALL_FEATURES",
    "heal_and_detect",
    "to_dxf",
    "split",
    "inject",
    "split_to_files",
    # Export
    "to_json",
    "save_json",
    "save_xml",
    "to_view_model",
    "to_svg",
    "save_svg",
    # Metadati DXF
    "write_metadata_to_dxf",
    "read_metadata_from_dxf",
    "set_schema",
    # Utilità
    "extract_texts_from_msp",
    "extract_forge_texts",
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