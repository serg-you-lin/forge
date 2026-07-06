"""
adapters/pdf/sanitize.py
-------------------------
Sanitizzazione geometrica dei dati estratti dal PDF prima della conversione in Edge.

Funzioni pubbliche:
    sanitize_pdf_geometries — esegue lo snap dei nodi vicini ed elimina i segmenti duplicati o degeneri
"""

from ...core.geometry import round_point


def sanitize_pdf_geometries(raw_items: list, page_height: float, snap_tolerance: float = 0.15) -> list:
    """
    Prende gli item geometrici grezzi estratti dall'extractor, applica la conversione 
    in mm con inversione dell'asse Y, esegue lo snap dei punti vicini entro una tolleranza,
    ed elimina i micro-segmenti degeneri (es. linee lunghe meno della tolleranza).

    Args:
        raw_items:       lista di tuple (cmd, ...) provenienti da extractor_adapter
        page_height:     altezza della pagina PDF in punti (pt)
        snap_tolerance:  distanza massima in mm sotto la quale due punti vengono fusi (default 0.15 mm)

    Returns:
        list — lista di item pronti, sanificati e già convertiti in coordinate float standard (mm)
    """
    from .geometry_adapter import transform_point, sample_bezier_cubic
    import math

    sanitized_items = []
    known_nodes = []

    def _get_snapped_point(pt_mm: tuple[float, float]) -> tuple[float, float]:
        """Trova un nodo esistente vicino entro la tolleranza, altrimenti lo registra."""
        for kn in known_nodes:
            dist = math.hypot(pt_mm[0] - kn[0], pt_mm[1] - kn[1])
            if dist <= snap_tolerance:
                return kn
        known_nodes.append(pt_mm)
        return pt_mm

    for item in raw_items:
        cmd = item[0]

        if cmd == "l":
            # 1. Converti in mm
            p1_raw = transform_point(item[1].x, item[1].y, page_height)
            p2_raw = transform_point(item[2].x, item[2].y, page_height)
            
            # 2. Applica lo snap ai nodi vicini
            p1 = _get_snapped_point(p1_raw)
            p2 = _get_snapped_point(p2_raw)
            
            # 3. Elimina segmenti degeneri (se i punti collassano sullo stesso nodo o sono troppo corti)
            if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) > snap_tolerance:
                sanitized_items.append(("l", p1, p2))

        elif cmd == "re":
            rect = item[1]
            p0 = _get_snapped_point(transform_point(rect.x0, rect.y0, page_height))
            p1 = _get_snapped_point(transform_point(rect.x1, rect.y0, page_height))
            p2 = _get_snapped_point(transform_point(rect.x1, rect.y1, page_height))
            p3 = _get_snapped_point(transform_point(rect.x0, rect.y1, page_height))
            
            # Evita rettangoli collassati a linee o punti
            if p0 != p1 and p1 != p2:
                sanitized_items.append(("re", [p0, p1, p2, p3]))

        elif cmd == "qu":
            quad = item[1]
            pts = [_get_snapped_point(transform_point(p.x, p.y, page_height)) for p in quad]
            if len(set(pts)) >= 3:  # Almeno 3 punti distinti per fare un quadrilatero valido
                sanitized_items.append(("qu", pts))

        elif cmd == "c":
            p1_raw = transform_point(item[1].x, item[1].y, page_height)
            p2_raw = transform_point(item[2].x, item[2].y, page_height)
            p3_raw = transform_point(item[3].x, item[3].y, page_height)
            p4_raw = transform_point(item[4].x, item[4].y, page_height)
            
            p1 = _get_snapped_point(p1_raw)
            p2 = _get_snapped_point(p2_raw)
            p3 = _get_snapped_point(p3_raw)
            p4 = _get_snapped_point(p4_raw)
            
            # Campioniamo direttamente la curva in una poligonale (punti discretizzati)
            pts_curve = sample_bezier_cubic(p1, p2, p3, p4, num_segments=16)
            
            # Applichiamo lo snap anche ai punti interni campionati della curva
            pts_curve_snapped = [_get_snapped_point(pt) for pt in pts_curve]
            
            # Pulizia da duplicati consecutivi generati dallo snapping
            cleaned_curve_pts = [pts_curve_snapped[0]]
            for pt in pts_curve_snapped[1:]:
                if pt != cleaned_curve_pts[-1]:
                    cleaned_curve_pts.append(pt)
            
            if len(cleaned_curve_pts) >= 2:
                sanitized_items.append(("c_poly", cleaned_curve_pts))

    return sanitized_items