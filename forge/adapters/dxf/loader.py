# """
# adapters/dxf/loader.py
# -----------------------
# Punto di ingresso unico per aprire un file DXF o DWG.

# Funzioni pubbliche:
#     load_dxf — apre, audita, upgradia, sanitizza → (doc, msp)
# """

# import os
# import subprocess
# import tempfile
# import ezdxf
# from .copy_adapter import copy_entity
# from .sanitize import sanitize


# # ---------------------------------------------------------------------------
# # CAMBIA QUI se ODA File Converter è installato in un percorso diverso
# # ---------------------------------------------------------------------------

# # ODA_PATH = os.environ.get(
# #     "ODA_PATH",
# #     r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe"
# # )
# ODA_PATH = os.environ.get(
#     "ODA_PATH"
# )

# r"""
# Per settare variabile di ambiente ODA_PATH su Windows:
# Tasto destro su "Questo PC" → Proprietà → 
# Impostazioni di sistema avanzate → 
# Variabili d'ambiente → 
# Nuovo (nella sezione "Variabili utente") → 
# nome ODA_PATH, valore c:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe.

# """
# # ---------------------------------------------------------------------------
# # DWG → DXF via ODA File Converter
# # ---------------------------------------------------------------------------

# def _dwg_to_dxf(path: str) -> str:
#     """
#     Converte un file DWG in DXF R2010 usando ODA File Converter.
#     Restituisce il path del DXF temporaneo prodotto.

#     Raises:
#         FileNotFoundError: se ODA non è installato in ODA_PATH
#         RuntimeError: se la conversione fallisce
#     """
#     if not os.path.isfile(ODA_PATH):
#         raise FileNotFoundError(
#             f"[loader] ODA File Converter non trovato in: {ODA_PATH}\n"
#             "Scaricalo da https://www.opendesign.com/guestfiles/oda_file_converter\n"
#             "e aggiorna ODA_PATH in adapters/dxf/loader.py"
#         )

#     input_dir  = os.path.dirname(path)
#     input_file = os.path.basename(path)
#     output_dir = tempfile.mkdtemp()

#     cmd = [
#         ODA_PATH,
#         input_dir,
#         output_dir,
#         "DXF",    # formato output
#         "R2010",  # versione output
#         "0",      # non ricorsivo
#         "1",      # audit
#         input_file,
#     ]

#     print(" ".join(f'"{x}"' for x in cmd))

#     print("Return code:", result.returncode)
#     print("STDOUT:")
#     print(result.stdout)
#     print("STDERR:")
#     print(result.stderr)
#     result = subprocess.run(cmd, capture_output=True, text=True)

#     base_name  = os.path.splitext(input_file)[0]
#     output_dxf = os.path.join(output_dir, f"{base_name}.dxf")

#     if not os.path.isfile(output_dxf):
#         raise RuntimeError(
#             f"[loader] Conversione DWG fallita per: {path}\n"
#             f"ODA stderr: {result.stderr.strip()}"
#         )

#     print(f"[loader] DWG convertito → {output_dxf}")
#     return output_dxf


# # ---------------------------------------------------------------------------
# # Upgrade R12 → R2010
# # ---------------------------------------------------------------------------

# def _upgrade_to_r2010(doc) -> object:
#     if doc.dxfversion >= 'AC1015':
#         return doc

#     new_doc = ezdxf.new('R2010')
#     new_msp = new_doc.modelspace()
#     old_msp = doc.modelspace()

#     for entity in list(old_msp.query('INSERT')):
#         try:
#             entity.explode()
#         except Exception as ex:
#             print(f"  [WARN] upgrade: explode INSERT fallito — {ex}")

#     for entity in list(old_msp.query('POLYLINE')):
#         try:
#             entity.explode()
#         except Exception as ex:
#             print(f"  [WARN] upgrade: explode POLYLINE fallito — {ex}")

#     copied = 0
#     skipped = 0
#     for entity in old_msp:
#         result = copy_entity(entity, new_msp)
#         if result is not None:
#             copied += 1
#         else:
#             skipped += 1

#     print(f"  [upgrade] {copied} entità copiate, {skipped} skippate → R2010")
#     return new_doc


# # ---------------------------------------------------------------------------
# # Entry point pubblico
# # ---------------------------------------------------------------------------

# def load_dxf(
#     path: str,
#     upgrade: bool = False,
#     flatten_z_flag: bool = True,
#     verbose: bool = False,
# ) -> tuple:
#     """
#     Apre un documento DXF o DWG e lo prepara per heal().

#     Sequenza:
#         1. conversione DWG→DXF se necessario (via ODA)
#         2. readfile
#         3. audit (stampa solo se ci sono errori)
#         4. upgrade R2010 se necessario o richiesto
#         5. sanitize (normalize_ocs + flatten_z)

#     Args:
#         path:           percorso del file .dxf o .dwg
#         upgrade:        se True, forza upgrade a R2010
#         flatten_z_flag: passa flatten_z a sanitize()
#         verbose:        se True, stampa dettaglio entità in sanitize

#     Returns:
#         (doc, msp) pronti per heal()

#     # TODO: logging audit su file
#     """
#     if path.lower().endswith('.dwg'):
#         path = _dwg_to_dxf(path)

#     doc = ezdxf.readfile(path)

#     auditor = doc.audit()
#     if auditor.errors:
#         print(f"[loader] audit: {len(auditor.errors)} problemi trovati")
#         for err in auditor.errors:
#             print(f"  [audit] {err}")

#     if upgrade or doc.dxfversion < 'AC1015':
#         doc = _upgrade_to_r2010(doc)

#     msp = doc.modelspace()
#     sanitize(msp, flatten_z_flag=flatten_z_flag, verbose=verbose)

#     return doc, msp

#######################################################################################
#######################################################################################
#######################################################################################

# """
# adapters/dxf/loader.py
# -----------------------
# Punto di ingresso unico per aprire un file DXF o DWG.

# Funzioni pubbliche:
#     load_dxf — apre, audita, upgradia, sanitizza → (doc, msp)
# """

# import os
# import subprocess
# import tempfile
# import shutil
# import ezdxf

# from .copy_adapter import copy_entity
# from .sanitize import sanitize


# # ---------------------------------------------------------------------------
# # ODA PATH
# # ---------------------------------------------------------------------------

# ODA_PATH = os.environ.get(
#     "ODA_PATH",
#     r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"
# )


# # ---------------------------------------------------------------------------
# # DWG → DXF via ODA File Converter (FIXED)
# # ---------------------------------------------------------------------------

# def _dwg_to_dxf(path: str) -> str:
#     if not ODA_PATH or not os.path.isfile(ODA_PATH):
#         raise FileNotFoundError(f"ODA_PATH non valido: {ODA_PATH}")

#     ODA_INPUT  = r"C:\ODA_input"
#     ODA_OUTPUT = r"C:\ODA_output"
#     os.makedirs(ODA_INPUT,  exist_ok=True)
#     os.makedirs(ODA_OUTPUT, exist_ok=True)

#     filename  = os.path.basename(path)
#     base_name = os.path.splitext(filename)[0]
#     src_dir   = os.path.dirname(path)

#     shutil.copy(path, ODA_INPUT)

#     cmd = [
#         ODA_PATH,
#         ODA_INPUT,
#         ODA_OUTPUT,
#         "DXF",
#         "2010 ASCII DXF",
#         "0",
#         "1",
#     ]

#     subprocess.run(cmd, capture_output=True, text=True)

#     output_dxf = os.path.join(ODA_OUTPUT, f"{base_name}.dxf")
#     if not os.path.isfile(output_dxf):
#         # cerca qualsiasi dxf prodotto
#         dxfs = [f for f in os.listdir(ODA_OUTPUT) if f.lower().endswith(".dxf")]
#         if not dxfs:
#             raise RuntimeError(f"[loader] ODA non ha prodotto nessun DXF per: {path}")
#         output_dxf = os.path.join(ODA_OUTPUT, dxfs[0])

#     # sposta nella cartella del file originale
#     final_path = os.path.join(src_dir, f"{base_name}.dxf")
#     shutil.move(output_dxf, final_path)

#     # pulisci input
#     os.remove(os.path.join(ODA_INPUT, filename))

#     print(f"[loader] DWG convertito → {final_path}")
#     return final_path


# # ---------------------------------------------------------------------------
# # Upgrade R12 → R2010
# # ---------------------------------------------------------------------------

# def _upgrade_to_r2010(doc) -> object:
#     if doc.dxfversion >= 'AC1015':
#         return doc

#     new_doc = ezdxf.new('R2010')
#     new_msp = new_doc.modelspace()
#     old_msp = doc.modelspace()

#     for entity in list(old_msp.query('INSERT')):
#         try:
#             entity.explode()
#         except Exception as ex:
#             print(f"[WARN] explode INSERT fallito — {ex}")

#     for entity in list(old_msp.query('POLYLINE')):
#         try:
#             entity.explode()
#         except Exception as ex:
#             print(f"[WARN] explode POLYLINE fallito — {ex}")

#     copied = 0
#     skipped = 0

#     for entity in old_msp:
#         result = copy_entity(entity, new_msp)
#         if result is not None:
#             copied += 1
#         else:
#             skipped += 1

#     print(f"[upgrade] {copied} copiate, {skipped} skippate → R2010")
#     return new_doc


# # ---------------------------------------------------------------------------
# # ENTRY POINT
# # ---------------------------------------------------------------------------

# def load_dxf(
#     path: str,
#     upgrade: bool = False,
#     flatten_z_flag: bool = True,
#     verbose: bool = False,
# ) -> tuple:

#     if path.lower().endswith(".dwg"):
#         path = _dwg_to_dxf(path)

#     doc = ezdxf.readfile(path)

#     auditor = doc.audit()
#     if auditor.errors:
#         print(f"[loader] audit: {len(auditor.errors)} problemi trovati")
#         for err in auditor.errors:
#             print(f"  [audit] {err}")

#     if upgrade or doc.dxfversion < "AC1015":
#         doc = _upgrade_to_r2010(doc)

#     msp = doc.modelspace()
#     sanitize(msp, flatten_z_flag=flatten_z_flag, verbose=verbose)

#     return doc, msp




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
from .copy_adapter import copy_entity
from .sanitize import sanitize

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

    copied = 0
    skipped = 0
    for entity in old_msp:
        result = copy_entity(entity, new_msp)
        if result is not None:
            copied += 1
        else:
            skipped += 1

    print(f"  [upgrade] {copied} entità copiate, {skipped} skippate → R2010")
    return new_doc


# ---------------------------------------------------------------------------
# Entry point pubblico
# ---------------------------------------------------------------------------

def load_dxf(
    path: str,
    upgrade: bool = False,
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
        5. sanitize (normalize_ocs + flatten_z)

    Args:
        path:           percorso del file .dxf o .dwg
        upgrade:        se True, forza upgrade a R2010
        flatten_z_flag: passa flatten_z a sanitize()
        verbose:        se True, stampa dettaglio entità in sanitize

    Returns:
        (doc, msp) pronti per heal()

    # TODO: logging audit su file
    """
    if path.lower().endswith('.dwg'):
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
    sanitize(msp, flatten_z_flag=flatten_z_flag, verbose=verbose)

    return doc, msp