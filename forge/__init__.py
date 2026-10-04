"""
forge
---------
DXF geometry preprocessor for manufacturing pipelines.

API pubblica — tutto quello che serve è qui.
Non devi importare i moduli interni direttamente.

Workflow consigliato (file singolo):
    import forge

    rules = [
        forge.RoleRule("construction", name_contains="constr", dashed=True),
    ]
    doc = forge.load_dxf("pezzo.dxf", role_rules=rules)
    # regole in ordine, vince la prima che matcha (D63);
    # forge.name_rules({"Costruzione": "construction"}) per le sole regole sul nome

    result = forge.heal(doc, label="pezzo", source_file="pezzo.dxf")
    # fori, pieghe, incisioni: lettura di processo, in snapbend (MAP.md D88)

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
from .adapters.geometry.loader import load_geometry
# simplify_points: SPERIMENTALE, fuori dal contratto pubblico (vedi MAP.md D33).
# Ricostruisce linee/spline da una sequenza di punti densa e ordinata (spigoli
# + refit) — generico, zero dipendenza da immagini. Resta importabile come
# forge.simplify_points, non è in __all__ e non è documentato finché non è
# stato provato da un caso reale (Smoother). detect_corners/fit_primitives
# restano accessibili da forge.core.primitives.fitting per chi vuole comporli.
from .core.primitives.fitting import simplify_points
# rotate_*: SPERIMENTALE, fuori dal contratto pubblico (vedi MAP.md D46).
# Ruotano un ForgeCluster/ForgeResult già sano (nessun heal() in più — una
# rotazione rigida non cambia la topologia) o un ForgeDocument grezzo
# pre-heal. Restano importabili come forge.rotate_result/forge.rotate_cluster/
# forge.rotate_document/forge.rotate_to_longest, non sono in __all__ e non
# sono documentati finché non sono stati provati da un caso reale (un
# nester). structural_segments/longest_structural_segment restano
# accessibili da forge.tools.rotate per chi vuole comporli.
from .tools.rotate import rotate_result, rotate_cluster, rotate_document, rotate_to_longest
from .core.heal          import heal
from .recipes            import split_to_files
from .tools.inject       import inject
from .tools.anchor       import anchor_annotations, dimension_references, leader_target, resolve_target
from .io.dxf             import to_dxf, split
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
# Scritto per un nester mai realizzato — forge non fa nesting. Resta
# importabile come forge.to_nester_input, ma non è in __all__ né documentato.
# Per serializzare la geometria a un renderer/tool usa forge.to_view_model().
from .io.exporter         import to_nester_input
from .io.view_model       import to_view_model
from .io.svg              import to_svg, save_svg
# to_text/save_text: SPERIMENTALI (MAP.md D84) — la lettura per un agente AI.
# Importabili come forge.to_text, fuori da __all__ finché non c'è un chiamante vero.
from .io.text             import to_text, save_text
from .model         import (
    ForgeResult, ForgeCluster, ForgeContour, ForgeDocument,
    Annotation, Note, Dimension, Leader,
    DetectedFeature, DetectedFeatures,
)
# Un consumatore che marca la geometria prima di heal() (snapdraw: cornice /
# cartiglio) setta `edge.role` sugli Edge di `doc.edges` con uno slug ripulito
# da normalize_role, e is_structural_role dice se quel ruolo è contorno di
# pezzo o arredo che heal terrà fuori dal grafo. Vedi INTERPRETER.md / D30.
from .model.role      import normalize_role, is_structural_role
# Regole del chiamante che assegnano il ruolo al load (D63).
from .model.role_rule import RoleRule, name_rules
# RoleStyle (D37): override esplicito colore/linetype/lineweight per ruolo,
# indipendente dal formato — vedi rules/palette.py. Passato a to_dxf()/split()
# via role_styles={ruolo: RoleStyle(...)}, oppure registrato una volta sola
# con register_role_style() (stesso idioma di set_schema per i metadati) e
# applicato automaticamente a ogni render successivo senza ripassarlo.
from .rules.palette   import RoleStyle, register_role_style
# Stesso criterio che heal() usa internamente per escludere un edge dal grafo
# dei contorni (branching + centroide fuori dal hull, D49) — senza dire cosa
# sia quell'edge. Un consumatore che vuole decidere `edge.role` prima di
# heal() con un'interpretazione propria (non "bending" come fa detect_flat()) lo
# chiama su doc.edges. Vedi SNAPDRAW.md, MAP.md D55.
from .tools.non_contour import non_contour_candidates
# Seconda lettura di un documento, accanto a heal(): per isole, contorno
# esterno come faccia esterna della rete piana (disegni di viste, 3D
# proiettato). I mattoni restano esposti per chi compone la sua ricetta
# (snapdraw): isole, rete piana, faccia esterna, tassellature. Vedi MAP.md D58.
from .core.island import island, read_islands, read_island, IslandReading
from .core.healing.islands import spatial_islands, Island
from .core.topology.noding import split_at_crossings, NodedEdges
from .core.topology.outer_face import outer_face, OuterFace
from .core.healing.normalizer import refit_tessellations
# Forma di un contorno chiuso (cerchio, stadio, rettangolo, ...): fatto
# geometrico, non feature — vale su heal() e island(). MAP.md D68.
from .core.shape import contour_shape, ContourShape
# I passi di heal(), uno per funzione: heal() è la loro composizione di
# default, un consumatore (snapdraw) li compone nell'ordine che gli serve —
# per esempio senza build_hierarchy, finché non ha deciso da sé cosa
# significa un contorno dentro un altro. Vedi MAP.md D62.
from .core.healing.normalizer import (
    merge_collinear_overlaps, merge_cocircular_overlaps, weld_degenerate_linesegs,
)
from .core.healing.steps import (
    split_labeled, close_free_gaps, dangling_splines, find_non_contour_edges,
    repair_merged_corners, find_loops, LoopSearch, structural_loops,
    loops_to_features, polygonize_edges, polygons_to_features,
    labeled_features, build_hierarchy,
)
from .core.topology.loop_finder import edges_to_open_features
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
    "load_geometry",
    # Validazione
    "validate",
    "validate_result",
    # Workflow
    "heal",
    "island",
    "to_dxf",
    "split",
    "inject",
    "anchor_annotations",
    "leader_target",
    "dimension_references",
    "resolve_target",
    "contour_shape",
    "ContourShape",
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
    # Lettura per isole: i mattoni di island()
    "read_islands",
    "read_island",
    "IslandReading",
    "spatial_islands",
    "Island",
    "split_at_crossings",
    "NodedEdges",
    "outer_face",
    "OuterFace",
    "refit_tessellations",
    # I passi di heal()
    "merge_collinear_overlaps",
    "merge_cocircular_overlaps",
    "weld_degenerate_linesegs",
    "split_labeled",
    "close_free_gaps",
    "dangling_splines",
    "find_non_contour_edges",
    "repair_merged_corners",
    "find_loops",
    "LoopSearch",
    "structural_loops",
    "loops_to_features",
    "polygonize_edges",
    "polygons_to_features",
    "edges_to_open_features",
    "labeled_features",
    "build_hierarchy",
    # Utilità
    # Ispezione / debug (3 livelli: DXF grezzo → ForgeDocument → ForgeResult)
    "inspect_dxf",
    "inspect_document",
    "inspect_result",
    "inspect_file",
    # Modelli
    "ForgeResult",
    "ForgeCluster",
    "ForgeContour",
    "ForgeDocument",
    "Annotation",
    "Note",
    "Dimension",
    "Leader",
    "DetectedFeature",
    "DetectedFeatures",
    # Ruoli — aggancio per un consumatore che marca la geometria pre-heal
    "normalize_role",
    "is_structural_role",
    "RoleRule",
    "name_rules",
    "RoleStyle",
    "register_role_style",
    "non_contour_candidates",
]