"""
read_xdata.py
-------------
Legge e stampa i metadati FORGE XDATA da un file DXF healato.

Uso:
    python read_xdata.py path/al/file.dxf
    python read_xdata.py  (usa il file di default sotto)
"""

import sys
import json
import ezdxf

# ← CAMBIA QUI oppure passa il path come argomento
DEFAULT_FILE = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\ARC\6200012808 Sviluppo\6200012808_PART5.dxf"


def read_xdata(filepath: str):
    try:
        doc = ezdxf.readfile(filepath)
    except IOError:
        print(f"Errore: file non trovato — {filepath}")
        return
    except ezdxf.DXFStructureError:
        print(f"Errore: file DXF non valido — {filepath}")
        return

    msp = doc.modelspace()
    print(f"\nFile: {filepath}")
    print("-" * 50)

    found = 0
    for entity in msp:
        try:
            xdata = entity.get_xdata('FORGE')
        except Exception:
            continue
        if not xdata:
            continue

        for tag in xdata:
            if tag.code == 1000:
                try:
                    meta = json.loads(tag.value)
                    found += 1
                    print(f"\nEntità: {entity.dxftype()}  layer={entity.dxf.layer}")
                    print(json.dumps(meta, indent=2, ensure_ascii=False))
                except json.JSONDecodeError as e:
                    print(f"  [WARN] XDATA non parsabile: {e}")
                    print(f"  raw: {tag.value}")

    if found == 0:
        print("Nessun metadato FORGE trovato nel file.")
        print("Il file è stato healato con write_metadata=True?")
    else:
        print(f"\nTotale entità con metadati FORGE: {found}")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FILE
    read_xdata(filepath)