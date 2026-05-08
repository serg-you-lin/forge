import ezdxf

def explode_all_blocks(input_file, output_file):
    doc = ezdxf.readfile(input_file)
    msp = doc.modelspace()

    inserts = list(msp.query('INSERT'))  # tutti i blocchi

    for insert in inserts:
        # Esplode il blocco in entità DXF
        exploded_entities = insert.explode()

        # Aggiunge le entità risultanti nel modelspace
        for entity in exploded_entities:
            msp.add_entity(entity)

        # Cancella il blocco originale
        msp.delete_entity(insert)

    doc.saveas(output_file)


# USO
explode_all_blocks("4_blocchi.dxf", "4_blocchi_esplosi.dxf")