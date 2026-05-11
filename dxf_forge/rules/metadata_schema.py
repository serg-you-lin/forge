"""
metadata_schema.py
------------------
Schema configurabile dei metadati esportati da dxf-forge.

L'UTENTE MODIFICA QUESTO FILE per adattare i nomi dei campi
al proprio CAM o sistema gestionale.

Struttura METADATA_FIELDS:
    chiave interna forge → (nome nel output, valore default)

    - chiave interna: non modificare, è usata da exporter.py
    - nome output: cambia questo per adattarti al tuo CAM
    - valore default: usato se il campo non è calcolabile o non è fornito
                      None = calcolato automaticamente da ForgeResult

Campi calcolati automaticamente (default None):
    area, holes_count, bbox, outer_perimeter, inner_perimeter, total_perimeter

Campi che l'utente deve fornire (o restano al default):
    label, source_file, quantity, material, thickness
"""


METADATA_FIELDS = {
    "label"                   : ("label",                    "",       "part"),
    "source_file"             : ("source_file",              "",       "part"),
    "quantity"                : ("quantity",                 1,        "custom"),
    "material"                : ("material",                 "S275JR", "custom"),
    "thickness"               : ("thickness_mm",             0.0,      "custom"),
    # --- lavorazioni ---
    "bending_lines"           : ("bending_lines",            0,        "custom"),
    "countersink_count"       : ("countersink_count",        0,        "custom"),  
    "threaded_holes_count"    : ("threaded_holes_count",     0,        "custom"),  
    "total_engrave_length"    : ("total_engrave_length_mm",  0.0,      "custom"),
    # --- geometria ---
    "area"                    : ("area_mm2",                 None,     "calculated"),
    "holes_count"             : ("holes_count",              None,     "calculated"),  
    "inner_contours_count"    : ("inner_contours_count",     None,     "calculated"),  
    "outer_perimeter"         : ("outer_perimeter_mm",       None,     "calculated"),
    "inner_perimeter"         : ("inner_perimeter_mm",       None,     "calculated"),
    "total_perimeter"         : ("total_perimeter_mm",       None,     "calculated"),
    "bbox"                    : ("bbox",                     None,     "calculated"),
}