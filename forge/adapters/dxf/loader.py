
"""
adapters/dxf/loader.py
-----------------------
Punto di ingresso unico per aprire un file DXF o DWG.

Funzioni pubbliche:
    load_dxf — apre, audita, upgradia, sanitizza → (doc, msp)
"""

import os
import ezdxf
from ezdxf.addons import odafc
from .sanitize import sanitize, _explode_inserts, deduplicate

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

def _read_dwg(path: str):
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
    print(f"[loader] DWG rilevato: {version_name} ({version_code})")

    if not ODA_PATH:
        raise EnvironmentError(
            "[loader] ODA_PATH non settato.\n"
            "Installa ODA File Converter e setta la variabile d'ambiente ODA_PATH."
        )

    # odafc.win_exec_path = ODA_PATH

    ezdxf.options.set("odafc-addon", "win_exec_path", ODA_PATH)

    try:
        doc = odafc.readfile(path)
    except Exception as ex:
        raise RuntimeError(f"[loader] Conversione DWG fallita: {ex}")

    print(f"[loader] DWG convertito correttamente")
    return doc

# ---------------------------------------------------------------------------
# Upgrade R12 → R2010
# ---------------------------------------------------------------------------

def _upgrade_to_r2010(doc) -> object:
    """
    Converte un documento DXF legacy in R2010.
    Esplode INSERT e POLYLINE in place, poi copia tutto nel nuovo doc.
    Funzione privata — chiamata da load_dxf.
    """
    if doc.dxfversion >= 'AC1015':
        return doc

    new_doc = ezdxf.new('R2010')
    new_msp = new_doc.modelspace()
    old_msp = doc.modelspace()

    for entity in list(old_msp.query('INSERT')):
        try:
            entity.explode()
        except Exception as ex:
            print(f"  [WARN] upgrade: explode INSERT fallito — {ex}")

    for entity in list(old_msp.query('POLYLINE')):
        try:
            entity.explode()
        except Exception as ex:
            print(f"  [WARN] upgrade: explode POLYLINE fallito — {ex}")

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
) -> tuple:
    """
    Apre un documento DXF o DWG e lo prepara per heal().

    Sequenza:
        1. se DWG → conversione via odafc (ODA File Converter)
        2. readfile
        3. audit (stampa solo se ci sono errori)
        4. upgrade R2010 se necessario o richiesto
        5. explode INSERT se richiesto
        6. sanitize (normalize_ocs + flatten_z)

    Args:
        path:           percorso del file .dxf o .dwg
        upgrade:        se True, forza upgrade a R2010
        explode_inserts: se True, esplode INSERT in entità primitive
        flatten_z_flag: passa flatten_z a sanitize()
        verbose:        se True, stampa dettaglio entità in sanitize

    Returns:
        (doc, msp) pronti per heal()

    # TODO: logging audit su file
    """
    # if path.lower().endswith('.dwg'):
    if str(path).lower().endswith('.dwg'):
        doc = _read_dwg(path)
    else:
        doc = ezdxf.readfile(path)

    auditor = doc.audit()
    if auditor.errors:
        print(f"[loader] audit: {len(auditor.errors)} problemi trovati")
        for err in auditor.errors:
            print(f"  [audit] {err}")

    if upgrade or doc.dxfversion < 'AC1015':
        doc = _upgrade_to_r2010(doc)

    msp = doc.modelspace()

    inserts_found = list(msp.query("INSERT"))
    if inserts_found:
        if explode_inserts:
            n = _explode_inserts(msp)
            if n:
                print(f"[loader] {n} INSERT esplosi.")
        else:
            print(f"[loader] Trovati {len(inserts_found)} INSERT non esplosi — usa explode_inserts=True in load_dxf() per includerli.")

    removed = deduplicate(msp)
    if removed > 0:
        print(f"Rimosse {removed} entità duplicate dal msp.")
    sanitize(msp, flatten_z_flag=flatten_z_flag, verbose=verbose)

    return doc, msp






