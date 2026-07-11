"""
adapters/pdf/loader.py
-----------------------
Punto di ingresso unico per aprire, estrarre e convertire geometrie da un file PDF.

Funzioni pubbliche:
    load_pdf — apre il PDF, estrae i disegni, li sanifica tramite snap geometrico 
               e restituisce una lista di Edge per il core.
"""

import os
try:
    import fitz
except ImportError:
    fitz = None

from .extractor_adapter import extract_drawings_from_page
from .sanitize import sanitize_pdf_geometries
from .graph_adapter import map_sanitized_item_to_edge


def load_pdf(path: str, node_decimals: int = 3, snap_tolerance: float = 0.15) -> list:
    """
    Apre un documento PDF, estrae le geometrie vettoriali da tutte le pagine,
    applica una sanificazione pesante (snap geometrico dei nodi vicini),
    le converte in scala reale (mm) con l'asse Y cartesiano corretto,
    e restituisce una lista di Edge topologici pronti per il core del grafo.

    Args:
        path:           percorso del file .pdf
        node_decimals:  cifre decimali per l'arrotondamento dei nodi del grafo
        snap_tolerance: distanza massima in mm sotto la quale due nodi vicini vengono fusi

    Returns:
        list[Edge] — pronti per essere passati a build_node_graph() o inseriti in un msp virtuale
    """
    # 1. Verifica preliminare dell'esistenza del file
    if not os.path.isfile(path):
        raise FileNotFoundError(f"[pdf/loader] File PDF non trovato: {path}")

    all_edges = []

    try:
        # 2. Apertura del file tramite PyMuPDF
        doc = fitz.open(path)
        print(f"[pdf/loader] Aperto PDF: {path} ({len(doc)} pagine)")

        # 3. Iterazione su ogni pagina del documento
        for page_idx, page in enumerate(doc):
            page_height = page.rect.height
            page_edges_count = 0  # Resetta il contatore per la pagina corrente

            # Estrazione dei pacchetti grafici grezzi (isole di dati Python nativi)
            drawings_packages = extract_drawings_from_page(page)

            # Srotoliamo tutti i singoli item grezzi presenti nei vari pacchetti della pagina
            raw_items = []
            for package in drawings_packages:
                raw_items.extend(package["items"])

            # 4. Sanificazione pesante e Snap Geometrico (elimina le micro-disconnessioni)
            sanitized_items = sanitize_pdf_geometries(
                raw_items=raw_items, 
                page_height=page_height, 
                snap_tolerance=snap_tolerance
            )

            # 5. Mappatura finale degli elementi puliti in Edge topologici
            for item in sanitized_items:
                edge = map_sanitized_item_to_edge(item, node_decimals, page_idx)
                
                if edge is not None:
                    all_edges.append(edge)
                    page_edges_count += 1

            print(f"  [page {page_idx}] Estratti e sanificati {page_edges_count} elementi grafici convertiti in mm")

        # 6. Chiusura del file e restituzione dei dati strutturati
        doc.close()
        return all_edges

    except Exception as ex:
        raise RuntimeError(f"[pdf/loader] Errore critico durante il caricamento del PDF: {ex}")