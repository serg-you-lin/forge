# Gestisce la conversione geometrica (punti in mm, flip asse Y, ecc.)

# 2. adapters/pdf/geometry_adapter.py
# Questo modulo contiene la logica matematica e di conversione. Non gli interessa se i dati arrivano da un PDF o da un file di testo.

# Costanti: PT_TO_MM = 25.4 / 72.0

# Funzioni: pdf_point_to_mm(x, y, page_height), convert_rect_to_polyline(), convert_bezier_to_points().

# Cosa fa: Applica il fattore di scala e corregge l'orientamento dell'asse Y (visto che il PDF ha l'origine in alto a sinistra e le coordinate cartesiane/DXF in genere ce l'hanno in basso a sinistra).


"""
adapters/pdf/geometry_adapter.py
---------------------------------
Funzioni matematiche e geometriche per la conversione dei dati PDF.

Gestisce la scala pt -> mm, il ribaltamento dell'asse Y e l'approssimazione
delle curve di Bezier in segmenti lineari.
"""

# FATTORE DI CONVERSIONE: da PDF punti (pt) a Millimetri (mm)
# 1 pollice = 72 punti = 25.4 mm -> 25.4 / 72
PT_TO_MM = 25.4 / 72.0


def transform_point(x: float, y: float, page_height: float) -> tuple[float, float]:
    """
    Converte un punto da punti PDF (pt) a millimetri (mm) 
    e inverte l'asse Y per portarlo nel sistema cartesiano standard (origine in basso a sinistra).
    """
    x_mm = x * PT_TO_MM
    y_mm = (page_height - y) * PT_TO_MM
    return (x_mm, y_mm)


def sample_bezier_cubic(p1: tuple, p2: tuple, p3: tuple, p4: tuple, num_segments: int = 16) -> list[tuple[float, float]]:
    """
    Campiona una curva di Bezier cubica in un set di punti lineari (poligonale).
    
    Parametri:
        p1: Punto iniziale (x, y) in mm
        p2: Primo punto di controllo (x, y) in mm
        p3: Secondo punto di controllo (x, y) in mm
        p4: Punto finale (x, y) in mm
        num_segments: Numero di segmenti in cui dividere la curva (default 16)
    """
    points = []
    for i in range(num_segments + 1):
        t = i / float(num_segments)
        
        # Formula polinomiale di Bezier cubica
        c_1 = (1 - t) ** 3
        c_2 = 3 * ((1 - t) ** 2) * t
        c_3 = 3 * (1 - t) * (t ** 2)
        c_4 = t ** 3
        
        x = c_1 * p1[0] + c_2 * p2[0] + c_3 * p3[0] + c_4 * p4[0]
        y = c_1 * p1[1] + c_2 * p2[1] + c_3 * p3[1] + c_4 * p4[1]
        
        points.append((x, y))
        
    return points