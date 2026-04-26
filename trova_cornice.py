import ezdxf
from collections import defaultdict

# ---------------- CONFIG ----------------
INPUT_DXF = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\ARC - Copia\ARC.6200012802 Nipote\6200012802 Sviluppo.dxf"

KEYWORDS = ["cartiglio", "title", "drawing", "rev", "scale", "date"]

RADIUS = 200  # area attorno al testo
GRID_SIZE = 200  # per fallback densità

# ---------------- UTILS ----------------
def get_entity_position(e):
    try:
        if e.dxftype() in ["TEXT", "MTEXT"]:
            return e.dxf.insert[:2]
        elif e.dxftype() == "LINE":
            return e.dxf.start[:2]
        elif e.dxftype() == "LWPOLYLINE":
            return e[0][:2]
    except:
        return None

def get_text_content(e):
    try:
        if e.dxftype() == "TEXT":
            return e.dxf.text.lower()
        elif e.dxftype() == "MTEXT":
            return e.plain_text().lower()
    except:
        return ""
    return ""

# ---------------- STEP 1: KEYWORD ----------------
def find_keyword_area(msp):
    for e in msp:
        if e.dxftype() not in ["TEXT", "MTEXT"]:
            continue

        text = get_text_content(e)
        if not text:
            continue

        if any(k in text for k in KEYWORDS):
            pos = get_entity_position(e)
            if not pos:
                continue

            cx, cy = pos
            collected = []

            for ent in msp:
                p = get_entity_position(ent)
                if not p:
                    continue

                x, y = p
                if abs(x - cx) < RADIUS and abs(y - cy) < RADIUS:
                    collected.append(ent)

            print("✔ Cartiglio trovato tramite KEYWORD")
            print(f"Testo match: '{text}'")
            print(f"Centro: {pos}")
            print(f"Entità raccolte: {len(collected)}")

            return collected

    return None

# ---------------- STEP 2: DENSITY FALLBACK ----------------
def cluster_entities(msp):
    clusters = defaultdict(list)

    for e in msp:
        pos = get_entity_position(e)
        if not pos:
            continue

        x, y = pos
        key = (int(x // GRID_SIZE), int(y // GRID_SIZE))
        clusters[key].append(e)

    return clusters

def find_dense_area(msp):
    clusters = cluster_entities(msp)

    best_key = None
    best_score = 0
    best_entities = []

    for key, ents in clusters.items():
        texts = sum(1 for e in ents if e.dxftype() in ["TEXT", "MTEXT"])
        lines = sum(1 for e in ents if e.dxftype() == "LINE")

        score = len(ents) + texts * 3 + lines

        if score > best_score:
            best_score = score
            best_key = key
            best_entities = ents

    if best_entities:
        print("⚠ Fallback: cartiglio stimato tramite DENSITÀ")
        print(f"Cella: {best_key}")
        print(f"Score: {best_score}")
        print(f"Entità: {len(best_entities)}")

        return best_entities

    return None

# ---------------- MAIN ----------------
def main():
    print("Caricamento DXF...")
    doc = ezdxf.readfile(INPUT_DXF)
    msp = doc.modelspace()

    print("Ricerca cartiglio...")

    result = find_keyword_area(msp)

    if not result:
        result = find_dense_area(msp)

    if not result:
        print("❌ Nessun cartiglio trovato")
    else:
        print("✅ Operazione completata")

if __name__ == "__main__":
    main()