# Legge PyMuPDF e mappa i comandi nativi ("l", "re", "qu", "c")# 1. adapters/pdf/extractor_adapter.py
# Questo modulo è l'unico che sa dell'esistenza di fitz (PyMuPDF). Mappa l'estrazione grezza degli elementi geometrici della pagina.

# Funzioni: extract_drawings_from_page(page)

# Cosa fa: Cicla su page.get_drawings(), isola i comandi (l, re, qu, c) e restituisce dizionari o strutture dati pulite, isolate dalle dipendenze di PyMuPDF.

"""
adapters/pdf/extractor_adapter.py
----------------------------------
Estrae elementi grafici vettoriali grezzi da una pagina PDF usando PyMuPDF.

Questo modulo è l'unico (insieme a loader.py) a conoscere 'fitz'.
Isola la struttura interna del PDF e restituisce dati puliti.

Funzioni pubbliche:
    extract_drawings_from_page — estrae i comandi vettoriali mappandoli in tipi primitivi
"""

from typing import Any, Dict, List


def extract_drawings_from_page(page: Any) -> List[Dict[str, Any]]:
    """
    Estrae i disegni vettoriali dalla pagina PDF e normalizza l'output.
    Risolve le incongruenze di PyMuPDF e filtra solo i comandi geometrici validi.

    Args:
        page: l'oggetto pagina di PyMuPDF (fitz.Page)

    Returns:
        Una lista di dizionari contenenti i comandi grafici normalizzati.
    """
    extracted_drawings = []
    
    try:
        # Recupera i paths grafici nativi della pagina
        raw_drawings = page.get_drawings()
    except Exception as ex:
        print(f"  [WARN] Estrazione disegni fallita sulla pagina: {ex}")
        return []

    for drawing in raw_drawings:
        # Isoliamo le proprietà del tratto/riempimento se ti serviranno in futuro per i layer
        normalized_drawing = {
            "layer_hint": drawing.get("layer", ""),
            "color": drawing.get("color", None),
            "fill": drawing.get("fill", None),
            "width": drawing.get("width", 1.0),
            "items": []
        }

        for item in drawing.get("items", []):
            cmd = item[0]

            # 1. LINEA ("l") -> (cmd, point1, point2)
            if cmd == "l":
                p1, p2 = item[1], item[2]
                normalized_drawing["items"].append(("l", p1, p2))

            # 2. RETTANGOLO ("re") -> (cmd, rect_object)
            elif cmd == "re":
                rect = item[1]
                # Verifichiamo che il rettangolo sia valido e non degenere
                if rect.x0 != rect.x1 and rect.y0 != rect.y1:
                    normalized_drawing["items"].append(("re", rect))

            # 3. QUADRILATERO ("qu") -> (cmd, list_of_4_points)
            elif cmd == "qu":
                quad = item[1]
                if len(quad) == 4:
                    normalized_drawing["items"].append(("qu", quad))

            # 4. CURVA DI BEZIER ("c") -> (cmd, p1, p2, p3, p4)
            elif cmd == "c":
                p1, p2, p3, p4 = item[1], item[2], item[3], item[4]
                normalized_drawing["items"].append(("c", p1, p2, p3, p4))
                
            # Note: Eventuali comandi di tipo "s" (stroke) o "f" (fill) intermedi 
            # vengono ignorati perché gestiamo la geometria atomica degli elementi.

        # Aggiungiamo il disegno solo se contiene effettivamente elementi geometrici
        if normalized_drawing["items"]:
            extracted_drawings.append(normalized_drawing)

    return extracted_drawings