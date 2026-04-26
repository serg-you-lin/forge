import ezdxf
from ezdxf import path
import os

def esplodi_tutto(input_file):
    try:
        doc = ezdxf.readfile(input_file)
        msp = doc.modelspace()
        
        # 1. Gestione TEXT e MTEXT
        for el in msp.query('TEXT MTEXT'):
            # Trasforma in percorsi geometrici (usa font di sistema generico)
            paths = path.make_paths_from_entity(el)
            for p in paths:
                # Trasforma i percorsi in polilinee (linee e archi)
                path.render_lwpolylines(msp, [p], dxfattribs={'layer': el.dxf.layer, 'color': el.dxf.color})
            el.destroy()

        # 2. Gestione MULTILEADER
        # Nota: Un MLeader ha spesso un "Block" interno che contiene la sua geometria
        for ml in msp.query('MULTILEADER'):
            try:
                # Proviamo a creare un'istanza virtuale del contenuto per estrarre i path
                # Se l'MLeader ha testo, questo lo cattura
                paths = path.make_paths_from_entity(ml)
                for p in paths:
                    path.render_lwpolylines(msp, [p], dxfattribs={'layer': ml.dxf.layer, 'color': ml.dxf.color})
                ml.destroy()
            except Exception:
                # Se fallisce il path diretto, l'MLeader rimane lì (struttura troppo complessa)
                continue
            
        file_name = os.path.basename(nome_file)
        output = os.path.join(os.path.dirname(nome_file), f"{os.path.splitext(file_name)[0]}_esploso.dxf")
        doc.saveas(output)
        print(f"Fatto. Salvato in: {output}")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    nome_file = r'c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\ARC\6200012808 Sviluppo_da_espl.dxf' 


    esplodi_tutto(nome_file)