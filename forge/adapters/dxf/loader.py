
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
import sys
import shutil
import ezdxf
from ezdxf.addons import odafc

from .sanitize import sanitize, _explode_inserts, deduplicate
from .adapter import DxfAdapter
from .annotation_extractor import DxfAnnotationExtractor
from ...model.document import ForgeDocument

# Percorso dell'eseguibile ODA File Converter. `forge` NON legge i DWG da solo:
# il supporto DWG di ezdxf È l'addon `odafc`, che è un wrapper attorno a ODA
# File Converter (converte il DWG in DXF temporaneo, ezdxf rilegge il DXF).
# Download (gratuito): https://www.opendesign.com/guestfiles/oda_file_converter
ODA_DOWNLOAD_URL = "https://www.opendesign.com/guestfiles/oda_file_converter"
ODA_PATH = os.environ.get("ODA_PATH")

# Guida rapida alle variabili d'ambiente per SO — rimando nei messaggi d'errore.
_ENV_VAR_HELP = (
    "Come impostare ODA_PATH:\n"
    "  Windows (permanente): setx ODA_PATH \"C:\\Program Files\\ODA\\"
    "ODAFileConverter X.Y.Z\\ODAFileConverter.exe\"  (riapri il terminale)\n"
    "  Windows (sessione)  : $env:ODA_PATH = \"...\\ODAFileConverter.exe\"  (PowerShell)\n"
    "  Linux / macOS       : export ODA_PATH=\"/opt/ODAFileConverter/ODAFileConverter\" "
    "in ~/.bashrc o ~/.zshrc\n"
    "  In alternativa metti l'eseguibile ODAFileConverter nel PATH di sistema."
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

def _annotation_signature(ann) -> tuple:
    return (ann.kind, round(ann.position[0], 3), round(ann.position[1], 3),
            ann.data.get("content", ""))


def _merge_annotations(base: list, extra: list) -> None:
    """Aggiunge a `base` le annotazioni di `extra` non già presenti (per firma)."""
    seen = {_annotation_signature(a) for a in base}
    for ann in extra:
        sig = _annotation_signature(ann)
        if sig not in seen:
            seen.add(sig)
            base.append(ann)


# Tipi che forge sa ri-materializzare in to_dxf(): geometria di taglio +
# annotazioni. Tutto il resto viene perso nel write-back.
_ROUNDTRIP_TYPES = frozenset({
    "LINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE", "LWPOLYLINE", "POLYLINE",
    "POINT", "TEXT", "MTEXT", "DIMENSION", "LEADER", "MULTILEADER", "INSERT",
})


def _warn_non_roundtrip_types(msp, sink: list, verbose: bool = False) -> None:
    """Avvisa sui tipi di entità che to_dxf() non riscrive (HATCH, IMAGE, …)."""
    lost = sorted({
        e.dxftype() for e in msp if e.dxftype() not in _ROUNDTRIP_TYPES
    })
    if lost:
        _emit(
            sink,
            f"tipi non riportati in output da to_dxf(): {', '.join(lost)}",
            verbose,
        )


def _emit(sink: list, msg: str, verbose: bool = False) -> None:
    """Aggiunge `msg` al canale warnings; lo stampa solo se verbose."""
    if sink is not None:
        sink.append(msg)
    if verbose:
        print(f"[loader] {msg}")


def _configure_odafc(sink: list = None, verbose: bool = False) -> None:
    """
    Punta l'addon `odafc` all'eseguibile ODA File Converter.

    Ordine di ricerca:
      1. variabile d'ambiente ODA_PATH (full path dell'eseguibile)
      2. `ODAFileConverter` nel PATH di sistema (odafc lo trova da solo)

    Raises:
        EnvironmentError: ODA_PATH non settato E nessun ODAFileConverter nel PATH.
                          Il messaggio include link di download e guida alle
                          variabili d'ambiente per SO.
    """
    # su Windows odafc usa "win_exec_path", su Linux/macOS "unix_exec_path"
    opt_key = "win_exec_path" if sys.platform == "win32" else "unix_exec_path"

    if ODA_PATH:
        if os.path.isfile(ODA_PATH):
            ezdxf.options.set("odafc-addon", opt_key, ODA_PATH)
            return
        _emit(
            sink,
            f"ODA_PATH è settato ma non punta a un file esistente: {ODA_PATH!r} "
            f"— provo a cercare ODAFileConverter nel PATH.",
            verbose,
        )

    if shutil.which("ODAFileConverter"):
        return  # odafc lo troverà da solo

    raise EnvironmentError(
        "Impossibile aprire il DWG: ODA File Converter non trovato.\n"
        "`forge` (come ezdxf) converte i DWG tramite ODA File Converter.\n\n"
        f"1. Scaricalo (gratuito) da: {ODA_DOWNLOAD_URL}\n"
        f"2. {_ENV_VAR_HELP}\n\n"
        "Nota: se hai già ODA installato ma in una cartella con la versione nel "
        "nome (es. 'ODAFileConverter 27.1.0'), ODA_PATH deve puntare al full "
        "path dell'eseguibile, non alla cartella."
    )


def _read_dwg(path: str, sink: list = None, verbose: bool = False):
    """
    Legge un file DWG usando ezdxf.addons.odafc (wrapper di ODA File Converter).

    Raises:
        EnvironmentError: ODA File Converter non trovato (vedi `_configure_odafc`)
        RuntimeError: la conversione DWG→DXF è fallita
    """
    from ezdxf.addons import odafc

    with open(path, 'rb') as f:
        version_code = f.read(6).decode('ascii', errors='ignore')
    version_name = DWG_VERSIONS.get(version_code, version_code)
    _emit(sink, f"DWG rilevato: {version_name} ({version_code}), convertito via odafc", verbose)

    _configure_odafc(sink=sink, verbose=verbose)

    try:
        doc = odafc.readfile(path)
    except Exception as ex:
        raise RuntimeError(
            f"Conversione DWG fallita ({type(ex).__name__}: {ex}).\n"
            f"Se il messaggio parla di 'ODAFileConverter not installed', "
            f"scaricalo da {ODA_DOWNLOAD_URL} e imposta ODA_PATH.\n{_ENV_VAR_HELP}"
        )

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
    explode_inserts: bool = True,
    flatten_z_flag: bool = True,
    verbose: bool = False,
    tolerance: float = 0.05,
    label_map: dict = None,
    ignore_layers=None,
    linetype_map: dict = None,
    color_map: dict = None,
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
        explode_inserts: se True (default), esplode gli INSERT in entità
                         primitive. Passa False solo se vuoi ignorare i blocchi
                         di proposito: un INSERT non esploso viene scartato e la
                         sua geometria sparisce dall'output.
        flatten_z_flag:  passa flatten_z a sanitize()
        verbose:         se True, stampa dettaglio entità in sanitize
        tolerance:       tolleranza di arrotondamento dei nodi topologici;
                         viene ripresa da heal() se non specificata lì
        label_map:       {nome_layer: work_type} — assegna il ruolo semantico
                         agli Edge in fase di traduzione
        ignore_layers:   layer da escludere dalla geometria
        linetype_map:    {nome_linetype: work_type} (es. {"DASHED": "bending"})
                         — seconda lane di classificazione, usata solo dove
                         label_map non ha già deciso il ruolo dal layer.
        color_map:       {colore: work_type} — come linetype_map ma sul
                         colore ACI dell'entità: nome standard ("cyan"),
                         intero o stringa numerica ("4").

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

    if upgrade or doc.dxfversion < 'AC1015':
        doc = _upgrade_to_r2010(doc, sink=warnings, verbose=verbose)

    # Le annotazioni vanno estratte PRIMA di doc.audit(): l'auditor di ezdxf
    # cancella le DIMENSION che referenziano un blocco geometria non definito
    # (dims salvate senza pre-rendering) — sono comunque annotazioni valide da
    # riportare in output. `_dimension_text()` / `virtual_entities()` non hanno
    # bisogno del documento auditato.
    annotations = DxfAnnotationExtractor(doc.modelspace()).extract()

    auditor = doc.audit()
    if auditor.errors:
        _emit(warnings, f"audit: {len(auditor.errors)} problemi rilevati dal reader ezdxf", verbose)
        for err in auditor.errors[:5]:
            _emit(warnings, f"audit — {err}", verbose)

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
        linetype_map=linetype_map,
        color_map=color_map,
    ).to_edges()

    # Dopo explode possono affiorare TEXT/MTEXT che stavano dentro i blocchi:
    # le aggiungiamo a quelle catturate pre-audit, senza duplicare.
    if inserts_found and explode_inserts:
        _merge_annotations(annotations, DxfAnnotationExtractor(msp).extract())

    _warn_non_roundtrip_types(msp, warnings, verbose)

    meta = {
        "$INSUNITS":     doc.header.get("$INSUNITS", 4),
        "$MEASUREMENT":  doc.header.get("$MEASUREMENT", 1),
        "tolerance":     tolerance,
        "label_map":     label_map,
        "ignore_layers": sorted(ignore),
        "linetype_map":  linetype_map or {},
        "color_map":     color_map or {},
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
    linetype_map: dict = None,
    color_map: dict = None,
) -> ForgeDocument:
    """
    Costruisce un ForgeDocument da un modelspace ezdxf già aperto.

    Utile quando il msp non viene da un file (test, geometria generata a mano)
    o è già stato preparato altrove. Non fa audit/upgrade/sanitize: si assume
    che il msp sia già pronto.

    `linetype_map` / `color_map`: vedi `load_dxf()` — seconda lane di
    classificazione sull'aspetto grezzo, usata solo dove label_map non ha già
    deciso il ruolo dal layer.
    """
    label_map = label_map or {}
    ignore = {s.lower() for s in (ignore_layers or [])}

    edges = DxfAdapter(
        msp, tolerance=tolerance, ignore_layers=ignore, label_map=label_map,
        linetype_map=linetype_map, color_map=color_map,
    ).to_edges()
    annotations = DxfAnnotationExtractor(msp).extract()

    header = getattr(getattr(msp, "doc", None), "header", None)
    meta = {
        "$INSUNITS":     header.get("$INSUNITS", 4) if header else 4,
        "$MEASUREMENT":  header.get("$MEASUREMENT", 1) if header else 1,
        "tolerance":     tolerance,
        "label_map":     label_map,
        "ignore_layers": sorted(ignore),
        "linetype_map":  linetype_map or {},
        "color_map":     color_map or {},
    }
    return ForgeDocument(
        edges=edges, annotations=annotations,
        source_meta=meta, source_path=source_path,
    )






