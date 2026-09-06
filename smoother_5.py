


from pathlib import Path
import cv2
import ezdxf
from ezdxf.math import BSpline
import forge
import numpy as np

# ==========================
# Configurazione
# ==========================
INPUT = r"cancello 1_healed.dxf"  # ora passa il DXF grezzo, non l'healed
DXF_OUT = r"cancello_2_smooth.dxf"
PNG = r"temp_bw.png"

FATTORE_SCALA = 8
SCALA_DXF = 0.1
AREA_MIN = 50
SUBSAMPLE = 10
SOGLIA_SPIGOLO = 50.0

TOLERANCE = 0.01
SPECIAL_LAYERS = {}

# ==========================
# Geometria
# ==========================


def angolo_tra_vettori(v1, v2) -> float:
    n1 = np.linalg.norm(v1)
    n2 = np.linalg.norm(v2)
    if n1 == 0 or n2 == 0:
        return 180.0
    cos_a = np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0)
    return np.degrees(np.arccos(cos_a))


def classifica_punti(points: list[tuple], soglia: float) -> list[bool]:
    n = len(points)
    spigoli = [False] * n
    for i in range(n):
        p_prec = np.array(points[(i - 1) % n])
        p_curr = np.array(points[i])
        p_succ = np.array(points[(i + 1) % n])
        v1 = p_prec - p_curr
        v2 = p_succ - p_curr
        angolo = angolo_tra_vettori(v1, v2)
        if angolo < soglia:
            spigoli[i] = True
    return spigoli


def rimuovi_duplicati(pts_3d: list, soglia: float = 1e-6) -> list:
    puliti = [pts_3d[0]]
    for p in pts_3d[1:]:
        if np.linalg.norm(np.array(p[:2]) - np.array(puliti[-1][:2])) > soglia:
            puliti.append(p)
    return puliti


def scrivi_contorno(msp, points: list[tuple], spigoli: list[bool]) -> dict:
    n = len(points)
    contatori = {"spline": 0, "line": 0}
    indici_spigoli = [i for i, s in enumerate(spigoli) if s]

    if not indici_spigoli:
        pts_3d = [(x, y, 0) for x, y in points]
        pts_3d = rimuovi_duplicati(pts_3d)
        if len(pts_3d) >= 3:
            if pts_3d[0] != pts_3d[-1]:
                pts_3d.append(pts_3d[0])

            # Rimosso 'is_periodic', usiamo from_fit_points standard
            bspline = BSpline.from_fit_points(pts_3d, degree=3)
            spline = msp.add_spline()
            spline.apply_construction_tool(bspline)
            spline.closed = True
            spline.dxf.color = 3
            contatori["spline"] += 1
        return contatori

    start = indici_spigoli[0]
    points_rot = points[start:] + points[:start]
    spigoli_rot = spigoli[start:] + spigoli[:start]

    tratti = []
    tratto_corrente = [points_rot[0]]
    for i in range(1, n):
        tratto_corrente.append(points_rot[i])
        if spigoli_rot[i]:
            tratti.append(tratto_corrente)
            tratto_corrente = [points_rot[i]]
    tratto_corrente.append(points_rot[0])
    tratti.append(tratto_corrente)

    for tratto in tratti:
        if len(tratto) <= 3:
            for j in range(len(tratto) - 1):
                line = msp.add_line(tratto[j], tratto[j + 1])
                line.dxf.color = 2
                contatori["line"] += 1
        else:
            pts_3d = [(x, y, 0) for x, y in tratto]
            pts_3d = rimuovi_duplicati(pts_3d)

            if len(pts_3d) >= 3:
                # Rimosso 'is_periodic'
                bspline = BSpline.from_fit_points(pts_3d, degree=3)
                spline = msp.add_spline()
                spline.apply_construction_tool(bspline)
                spline.dxf.color = 3
                contatori["spline"] += 1
            else:
                for j in range(len(pts_3d) - 1):
                    line = msp.add_line(pts_3d[j], pts_3d[j + 1])
                    line.dxf.color = 2
                    contatori["line"] += 1

    return contatori


# ==========================
# Sorgenti
# ==========================


def punti_da_immagine(path: str) -> list[list[tuple]]:
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    gray_small = cv2.GaussianBlur(img, (3, 3), 0)
    width = int(gray_small.shape[1] * FATTORE_SCALA)
    height = int(gray_small.shape[0] * FATTORE_SCALA)
    img_resized = cv2.resize(
        gray_small, (width, height), interpolation=cv2.INTER_CUBIC
    )
    _, bw = cv2.threshold(
        img_resized, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    kernel = np.ones((3, 3), np.uint8)
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel)
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel)
    cv2.imwrite(PNG, bw)
    print("PNG creato:", PNG)
    contours, _ = cv2.findContours(bw, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    risultato = []
    for cnt in contours:
        if cv2.contourArea(cnt) < AREA_MIN:
            continue
        pts = [
            (p[0][0] * SCALA_DXF, -p[0][1] * SCALA_DXF)
            for p in cnt[::SUBSAMPLE]
        ]
        if len(pts) >= 3:
            risultato.append(pts)
    return risultato


def punti_da_dxf(path: str) -> tuple[list[list[tuple]], object, object]:
    doc_in, msp_in = forge.load_dxf(path)
    base_name = Path(path).stem

    result = forge.heal(
        msp_in,
        tolerance=TOLERANCE,
        special_layers=SPECIAL_LAYERS,
        label=base_name,
        source_file=Path(path).name,
    )
    forge.detect(result, msp_in)
    forge.write(msp_in, result)
    forge.inject(msp_in, result)

    print(f"Pezzi trovati: {result.part_count}")

    risultato = []
    for entity in msp_in.query("LWPOLYLINE"):
        pts = [(x, y) for x, y, *_ in entity.get_points()]
        if len(pts) >= 3:
            pts = pts[::SUBSAMPLE] if len(pts) > SUBSAMPLE else pts
            risultato.append(pts)

    print(f"LWPOLYLINE lette: {len(risultato)}")
    return risultato


# ==========================
# Main
# ==========================

ext = Path(INPUT).suffix.lower()

if ext in (".jpg", ".jpeg", ".png"):
    tutti_i_contorni = punti_da_immagine(INPUT)
elif ext == ".dxf":
    tutti_i_contorni = punti_da_dxf(INPUT)
else:
    raise ValueError(f"Formato non supportato: {ext}")

doc = ezdxf.new()
msp = doc.modelspace()

totale_spline = 0
totale_line = 0

for points in tutti_i_contorni:
    spigoli = classifica_punti(points, SOGLIA_SPIGOLO)
    contatori = scrivi_contorno(msp, points, spigoli)
    totale_spline += contatori["spline"]
    totale_line += contatori["line"]

print(f"Contorni processati : {len(tutti_i_contorni)}")
print(f"Spline generate     : {totale_spline}")
print(f"Segmenti generati   : {totale_line}")

doc.saveas(DXF_OUT)
print("DXF creato:", DXF_OUT)