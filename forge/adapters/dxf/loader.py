
"""
adapters/dxf/loader.py
-----------------------
Punto di ingresso unico per aprire un file DXF o DWG.

Funzioni pubbliche:
    load_dxf — apre, audita, upgradia, sanitizza, traduce → ForgeDocument

load_dxf è l'UNICO punto in cui ezdxf viene toccato per la lettura: dopo di essa
il documento ezdxf sorgente sparisce e heal()/detect()/write() lavorano solo sul
ForgeDocument restituito.
"""

import os
import ezdxf
from ezdxf.addons import odafc

from .sanitize import sanitize, _explode_inserts, deduplicate
from .adapter import DxfAdapter
from .annotation_extractor import DxfAnnotationExtractor
from ...model.document import ForgeDocument

ODA_PATH = os.environ.get(
    "ODA_PATH"
)

DWG_VERSIONS = {
    'AC1012': 'R13',
    'AC1014': 'R14',
    'AC1015': 'R2000',
    'AC1018': 'R2004',
    'AC1021': 'R2007',
    'AC1024': 'R2010',
    'AC1027': 'R2013',
    'AC1032': 'R2018+',
}


# ---------------------------------------------------------------------------
# DWG → doc via odafc
# ---------------------------------------------------------------------------

def _emit(sink: list, msg: str, verbose: bool = False) -> None:
    """Aggiunge `msg` al canale warnings; lo stampa solo se verbose."""
    if sink is not None:
        sink.append(msg)
    if verbose:
        print(f"[loader] {msg}")


def _read_dwg(path: str, sink: list = None, verbose: bool = False):
    """
    Legge un file DWG usando ezdxf.addons.odafc.
    Richiede ODA File Converter installato e ODA_PATH settato.

    Raises:
        EnvironmentError: se ODA_PATH non è settato
        RuntimeError: se la conversione fallisce
    """
    from ezdxf.addons import odafc

    with open(path, 'rb') as f:
        version_code = f.read(6).decode('ascii', errors='ignore')
    version_name = DWG_VERSIONS.get(version_code, version_code)
    _emit(sink, f"DWG rilevato: {version_name} ({version_code}), convertito via odafc", verbose)

    if not ODA_PATH:
        raise EnvironmentError(
            "[loader] ODA_PATH non settato.\n"
            "Installa ODA File Converter e setta la variabile d'ambiente ODA_PATH."
        )

    ezdxf.options.set("odafc-addon", "win_exec_path", ODA_PATH)

    try:
        doc = odafc.readfile(path)
    except Exception as ex:
        raise RuntimeError(f"[loader] Conversione DWG fallita: {ex}")

    return doc

# ---------------------------------------------------------------------------
# Upgrade R12 → R2010
# ---------------------------------------------------------------------------

def _upgrade_to_r2010(doc, sink: list = None, verbose: bool = False) -> object:
    """
    Converte un documento DXF legacy in R2010.
    Esplode INSERT e POLYLINE in place, poi copia tutto nel nuovo doc.
    Funzione privata — chiamata da load_dxf.
    """
    if doc.dxfversion >= 'AC1015':
        return doc

    _emit(sink, f"file legacy {doc.dxfversion}: upgrade a R2010", verbose)

    new_doc = ezdxf.new('R2010')
    new_msp = new_doc.modelspace()
    old_msp = doc.modelspace()

    for entity in list(old_msp.query('INSERT')):
        try:
            entity.explode()
        except Exception as ex:
            _emit(sink, f"upgrade: explode INSERT fallito — {ex}", verbose)

    for entity in list(old_msp.query('POLYLINE')):
        try:
            entity.explode()
        except Exception as ex:
            _emit(sink, f"upgrade: explode POLYLINE fallito — {ex}", verbose)

    for entity in old_msp:
        # Le entità devono essere copiate nel nuovo documento: non è lecito
        # trasferire un'entità da un DXF all'altro tramite add_entity().
        new_msp.add_entity(entity.copy())

    return new_doc


# ---------------------------------------------------------------------------
# Entry point pubblico
# ---------------------------------------------------------------------------

def load_dxf(
    path: str,
    upgrade: bool = False,
    explode_inserts: bool = False,
    flatten_z_flag: bool = True,
    verbose: bool = False,
    tolerance: float = 0.05,
    label_map: dict = None,
    ignore_layers=None,
) -> ForgeDocument:
    """
    Apre un documento DXF o DWG e lo traduce in un ForgeDocument.

    Sequenza:
        1. se DWG → conversione via odafc (ODA File Converter)
        2. readfile
        3. audit (stampa solo se ci sono errori)
        4. upgrade R2010 se necessario o richiesto
        5. explode INSERT se richiesto
        6. sanitize (normalize_ocs + flatten_z)
        7. traduzione: DxfAdapter.to_edges() + DxfAnnotationExtractor.extract()

    Args:
        path:            percorso del file .dxf o .dwg
        upgrade:         se True, forza upgrade a R2010
        explode_inserts: se True, esplode INSERT in entità primitive
        flatten_z_flag:  passa flatten_z a sanitize()
        verbose:         se True, stampa dettaglio entità in sanitize
        tolerance:       tolleranza di arrotondamento dei nodi topologici;
                         viene ripresa da heal() se non specificata lì
        label_map:       {nome_layer: work_type} — assegna il ruolo semantico
                         agli Edge in fase di traduzione
        ignore_layers:   layer da escludere dalla geometria

    Returns:
        ForgeDocument (edges + annotations + source_meta + warnings) — pronto
        per heal(). La diagnostica sul file grezzo (audit, INSERT non esplosi,
        Z != 0 riportate sul piano, duplicati rimossi) finisce in
        `doc.warnings`; con verbose=True viene anche stampata.
        `forge.validate(doc)` rilancia queste warnings.
    """
    warnings: list = []

    if str(path).lower().endswith('.dwg'):
        doc = _read_dwg(path, sink=warnings, verbose=verbose)
    else:
        doc = ezdxf.readfile(path)

    auditor = doc.audit()
    if auditor.errors:
        _emit(warnings, f"audit: {len(auditor.errors)} problemi rilevati dal reader ezdxf", verbose)
        for err in auditor.errors[:5]:
            _emit(warnings, f"audit — {err}", verbose)

    if upgrade or doc.dxfversion < 'AC1015':
        doc = _upgrade_to_r2010(doc, sink=warnings, verbose=verbose)

    msp = doc.modelspace()

    inserts_found = list(msp.query("INSERT"))
    if inserts_found:
        if explode_inserts:
            n = _explode_inserts(msp, sink=warnings)
            if n:
                _emit(warnings, f"{n} INSERT esplosi in entità primitive", verbose)
        else:
            _emit(
                warnings,
                f"{len(inserts_found)} INSERT non esplosi ignorati — "
                "usa explode_inserts=True in load_dxf() per includerli",
                verbose,
            )

    removed = deduplicate(msp)
    if removed > 0:
        _emit(warnings, f"{removed} entità duplicate rimosse dal modelspace", verbose)

    flattened = sanitize(msp, flatten_z_flag=flatten_z_flag, verbose=verbose)
    if flattened:
        _emit(warnings, f"{flattened} entità con Z != 0 riportate sul piano", verbose)

    label_map = label_map or {}
    ignore = {s.lower() for s in (ignore_layers or [])}

    edges = DxfAdapter(
        msp,
        tolerance=tolerance,
        ignore_layers=ignore,
        label_map=label_map,
    ).to_edges()
    annotations = DxfAnnotationExtractor(msp).extract()

    meta = {
        "$INSUNITS":     doc.header.get("$INSUNITS", 4),
        "$MEASUREMENT":  doc.header.get("$MEASUREMENT", 1),
        "tolerance":     tolerance,
        "label_map":     label_map,
        "ignore_layers": sorted(ignore),
    }

    return ForgeDocument(
        edges=edges,
        annotations=annotations,
        source_meta=meta,
        source_path=str(path),
        warnings=warnings,
    )


def document_from_msp(
    msp,
    tolerance: float = 0.05,
    label_map: dict = None,
    ignore_layers=None,
    source_path: str = "",
) -> ForgeDocument:
    """
    Costruisce un ForgeDocument da un modelspace ezdxf già aperto.

    Utile quando il msp non viene da un file (test, geometria generata a mano)
    o è già stato preparato altrove. Non fa audit/upgrade/sanitize: si assume
    che il msp sia già pronto.
    """
    label_map = label_map or {}
    ignore = {s.lower() for s in (ignore_layers or [])}

    edges = DxfAdapter(
        msp, tolerance=tolerance, ignore_layers=ignore, label_map=label_map,
    ).to_edges()
    annotations = DxfAnnotationExtractor(msp).extract()

    header = getattr(getattr(msp, "doc", None), "header", None)
    meta = {
        "$INSUNITS":     header.get("$INSUNITS", 4) if header else 4,
        "$MEASUREMENT":  header.get("$MEASUREMENT", 1) if header else 1,
        "tolerance":     tolerance,
        "label_map":     label_map,
        "ignore_layers": sorted(ignore),
    }
    return ForgeDocument(
        edges=edges, annotations=annotations,
        source_meta=meta, source_path=source_path,
    )






