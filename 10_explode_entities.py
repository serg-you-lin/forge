"""
explode_entities_to_files.py
-----------------------------

Prende un DXF e salva ogni entità in un file separato **nella stessa cartella dell'originale**.

Uso:
    python explode_entities_to_files.py input.dxf
"""

import os
import sys
import ezdxf


def explode_dxf(input_file):

    input_file = os.path.abspath(input_file)

    if not os.path.exists(input_file):
        print("File non trovato:", input_file)
        return

    print("Apertura:", input_file)

    doc = ezdxf.readfile(input_file)
    msp = doc.modelspace()

    base_dir = os.path.dirname(input_file)
    base_name = os.path.splitext(os.path.basename(input_file))[0]

    counters = {}

    for entity in msp:

        etype = entity.dxftype()

        counters.setdefault(etype, 0)
        counters[etype] += 1
        index = counters[etype]

        # Salva nella stessa cartella dell'input
        filename = f"{base_name}_{etype}_{index:03d}.dxf"
        out_path = os.path.join(base_dir, filename)

        # nuovo DXF
        new_doc = ezdxf.new(doc.dxfversion)
        new_msp = new_doc.modelspace()

        # copia entità
        new_msp.add_entity(entity.copy())

        new_doc.saveas(out_path)
        print("Creato:", filename)

    print("\nTotale entità:", sum(counters.values()))
    print("Cartella output:", base_dir)


if __name__ == "__main__":

    if len(sys.argv) > 1:
        dxf_file = sys.argv[1]
    else:
        dxf_file = r"tests/examples/debug/maniglia_no_raccordi.dxf"  # default

    explode_dxf(dxf_file)