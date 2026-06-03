import ezdxf

def _make_rounded_rect_msp():
    """
    Rettangolo con 4 angoli raggiati (r=10).
    Genera nodi degree 3: ogni angolo è condiviso tra 1 ARC e 2 LINE.
    """
    # Crea un nuovo disegno DXF (versione R2010 è ampiamente compatibile)
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    # Aggiunta delle linee e degli archi come da tua geometria
    msp.add_line((47, 50), (64, 50))          # top
    msp.add_line((74, 40), (74, 30))          # right bottom
    msp.add_line((74, 30), (37, 30))          # bottom
    msp.add_line((37, 30), (37, 40))          # left bottom
    msp.add_arc( (47, 40), 10,  90, 180)      # angolo top-left
    msp.add_arc( (64, 40), 10,   0,  90)      # angolo top-right
    msp.add_line((37, 40), (37, 50))          # left top  ← stub
    msp.add_line((37, 50), (47, 50))          # top-left connector
    msp.add_line((64, 50), (74, 50))          # top-right connector
    msp.add_line((74, 50), (74, 40))          # right top ← stub

    return doc  # Restituiamo il documento intero per poterlo salvare

if __name__ == "__main__":
    # 1. Genera il documento DXF
    doc_cad = _make_rounded_rect_msp()
    
    # 2. Definisci il nome del file di output
    nome_file = "rettangolo_raggiato.dxf"
    
    # 3. Salva il file
    try:
        doc_cad.saveas(nome_file)
        print(f"File '{nome_file}' generato con successo! Ora puoi aprirlo col tuo CAD.")
    except IOError:
        print(f"Errore: Impossibile salvare il file '{nome_file}'. Forse è aperto in un altro programma?")