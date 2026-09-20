"""
dwg_to_dxf.py — converte DWG -> DXF per aprire i disegni in CAD e ripulirli
===========================================================================

Usa ODA File Converter (deve essere installato: https://www.opendesign.com/
guestfiles/oda_file_converter). Il nome file resta lo stesso, cambia solo
l'estensione (.dwg -> .dxf), nella stessa cartella del sorgente.

Uso:
    python dwg_to_dxf.py percorso\al\file.dwg
    python dwg_to_dxf.py                          # converte tutti i .dwg in questa cartella
"""

import sys
from pathlib import Path

import ezdxf
from ezdxf.addons import odafc

LAB_DIR = Path(__file__).parent

# Percorso reale trovato sulla macchina — la cartella ha il numero di
# versione nel nome, quindi il default di ezdxf ("...\ODAFileConverter\
# ODAFileConverter.exe", senza versione) non lo trova da solo.
ODAFC_EXE = r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"


def _ensure_odafc() -> None:
    ezdxf.options.set("odafc-addon", "win_exec_path", ODAFC_EXE)
    if not odafc.is_installed():
        raise SystemExit(f"ODA File Converter non trovato in: {ODAFC_EXE}")


if __name__ == "__main__":
    _ensure_odafc()

    if len(sys.argv) > 1:
        targets = [Path(sys.argv[1])]
    else:
        targets = sorted(LAB_DIR.glob("*.dwg")) + sorted(LAB_DIR.glob("*.DWG"))

    if not targets:
        raise SystemExit(f"Nessun file .dwg da convertire (passa un percorso, o mettine uno dentro {LAB_DIR}).")

    for dwg_path in targets:
        dxf_path = dwg_path.with_suffix(".dxf")
        odafc.convert(dwg_path, dxf_path, version="R2018", audit=True, replace=True)
        print(f"{dwg_path} -> {dxf_path}")
