import ezdxf
import os

def analizza_layer_nascosti(input_dxf: str):
    """
    Stampa tutte le entità sui layer nascosti (colore negativo),
    cercando anche dentro i blocchi (INSERT).
    """
    doc = ezdxf.readfile(input_dxf)
    msp = doc.modelspace()

    # Mappa layer → nascosto (True/False)
    layer_info = {}
    for layer in doc.layers:
        color = layer.dxf.get("color", 7)
        layer_info[layer.dxf.name] = {
            "hidden": color < 0,
            "color": color,
        }

    hidden_layer_names = {
        name for name, info in layer_info.items() if info["hidden"]
    }

    print(f"\n{'='*60}")
    print(f"File: {input_dxf}")
    print(f"{'='*60}")
    print(f"\nLayer nascosti ({len(hidden_layer_names)}):")
    for name in sorted(hidden_layer_names):
        print(f"  - '{name}' (color={layer_info[name]['color']})")

    def stampa_entita(entity, prefisso=""):
        t = entity.dxftype()
        layer = entity.dxf.get("layer", "?")
        is_hidden_layer = layer in hidden_layer_names

        flag = " ← NASCOSTO" if is_hidden_layer else ""
        print(f"{prefisso}[{t}] layer='{layer}'{flag}")

        # Dettagli per tipo
        try:
            if t == "LINE":
                s, e = entity.dxf.start, entity.dxf.end
                print(f"{prefisso}  start=({s.x:.2f}, {s.y:.2f})  end=({e.x:.2f}, {e.y:.2f})")
            elif t == "CIRCLE":
                c = entity.dxf.center
                print(f"{prefisso}  center=({c.x:.2f}, {c.y:.2f})  r={entity.dxf.radius:.3f}")
            elif t == "LWPOLYLINE":
                pts = list(entity.get_points())
                print(f"{prefisso}  vertici={len(pts)}  chiusa={entity.closed}")
            elif t in ("TEXT", "MTEXT"):
                testo = getattr(entity, "text", "?")[:60]
                print(f"{prefisso}  testo='{testo}'")
            elif t == "INSERT":
                print(f"{prefisso}  blocco='{entity.dxf.name}'")
        except Exception as ex:
            print(f"{prefisso}  [errore lettura dati: {ex}]")

    print(f"\n--- Entità nel MSP ---")
    for entity in msp:
        stampa_entita(entity)

    print(f"\n--- Entità dentro i BLOCCHI ---")
    for block in doc.blocks:
        # Salta i blocchi di sistema ezdxf
        if block.name.startswith("*"):
            continue
        print(f"\n  BLOCCO: '{block.name}'")
        for entity in block:
            stampa_entita(entity, prefisso="    ")


if __name__ == "__main__":
    input_dxf = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\TON_06_05_2026\6200012914 Sviluppo.dxf"
    analizza_layer_nascosti(input_dxf)