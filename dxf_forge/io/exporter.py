"""
exporter.py
-----------
Esporta un ForgeResult in formati consumabili dall'esterno.
Punto di uscita unico per tutti i formati: JSON, XML, XDATA DXF, nester.

I nomi e i campi dei metadati sono gestiti ESCLUSIVAMENTE da metadata_schema.py.
Per aggiungere, rinominare o rimuovere un campo — modificare solo metadata_schema.py.
"""

import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from ..models import ForgeResult, ForgePart
from ..rules.metadata_schema import METADATA_FIELDS


# ---------------------------------------------------------------------------
# Unica fonte di verità per i metadati
# ---------------------------------------------------------------------------

def build_metadata(part: ForgePart, schema: dict = None) -> dict:
    """
    Costruisce il dict dei metadati per un ForgePart
    applicando lo schema definito in metadata_schema.py.

    Legge la sorgente da ogni campo dello schema:
        "part"       → attributo diretto di ForgePart (label, source_file)
        "custom"     → part.custom (material, thickness, quantity, ecc.)
        "calculated" → calcolato da Shapely (area, perimetri, bbox, holes_count)

    Args:
        part:   ForgePart da cui estrarre i dati
        schema: schema opzionale — se None usa METADATA_FIELDS da metadata_schema.py
    """
    if schema is None:
        schema = METADATA_FIELDS

    d = part.to_dict()
    custom = d.get("custom", {}) or {}

    outer_perimeter = 0.0
    inner_perimeter = 0.0
    try:
        outer_perimeter = round(part.outer.polygon.exterior.length, 4)
        inner_perimeter = round(
            sum(i.polygon.exterior.length for i in part.inners), 4
        )
    except Exception:
        pass

    calculated = {
        "area"            : d.get("area"),
        "holes_count"     : d.get("holes_count"),
        "inner_contours_count" : d.get("inner_contours_count"), 
        "bbox"            : d.get("bbox"),
        "outer_perimeter" : outer_perimeter,
        "inner_perimeter" : inner_perimeter,
        "total_perimeter" : round(outer_perimeter + inner_perimeter, 4),
    }

    part_fields = {
        "label"       : d.get("label", ""),
        "source_file" : d.get("source_file", ""),
    }

    meta = {}
    for forge_key, (output_name, default, source) in schema.items():
        if source == "calculated":
            value = calculated.get(forge_key)
        elif source == "custom":
            value = custom.get(forge_key)
        elif source == "part":
            value = part_fields.get(forge_key)
        else:
            value = None

        if value is not None:
            meta[output_name] = value
        elif default is not None:
            meta[output_name] = default

    return meta


def set_schema(schema: dict):
    """
    Imposta uno schema esterno come schema attivo.
    Usare quando la libreria è installata con pip e non si può
    modificare metadata_schema.py direttamente.

    Args:
        schema: dict con struttura {chiave: (nome_output, default, sorgente)}
    """
    global METADATA_FIELDS
    METADATA_FIELDS = schema


# ---------------------------------------------------------------------------
# Export JSON
# ---------------------------------------------------------------------------

def save_json(result: ForgeResult, path: str, indent: int = 2):
    """
    Salva i metadati in JSON secondo lo schema di metadata_schema.py.
    Le coordinate non vengono incluse.
    """
    output = {
        "source_file" : result.source_file,
        "is_valid"    : result.is_valid,
        "part_count"  : result.part_count,
        "warnings"    : result.warnings,
        "errors"      : result.errors,
        "parts"       : [build_metadata(part) for part in result.parts],
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=indent, ensure_ascii=False)
    print(f"[forge] JSON salvato in {path}")


def to_json(result: ForgeResult, indent: int = 2) -> str:
    """Restituisce i metadati come stringa JSON secondo schema."""
    output = {
        "source_file" : result.source_file,
        "is_valid"    : result.is_valid,
        "part_count"  : result.part_count,
        "warnings"    : result.warnings,
        "errors"      : result.errors,
        "parts"       : [build_metadata(part) for part in result.parts],
    }
    return json.dumps(output, indent=indent, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Export XML
# ---------------------------------------------------------------------------

def save_xml(result: ForgeResult, path: str):
    """
    Salva i metadati in XML secondo lo schema di metadata_schema.py.
    Struttura:
        <forge>
            <source_file>...</source_file>
            <is_valid>true</is_valid>
            <parts>
                <part>
                    <label>...</label>
                    <area_mm2>...</area_mm2>
                    <bbox>
                        <minx>...</minx>
                        ...
                    </bbox>
                </part>
            </parts>
        </forge>
    """
    root = ET.Element("forge")

    ET.SubElement(root, "source_file").text = result.source_file
    ET.SubElement(root, "is_valid").text    = str(result.is_valid).lower()
    ET.SubElement(root, "part_count").text  = str(result.part_count)

    if result.warnings:
        warnings_el = ET.SubElement(root, "warnings")
        for w in result.warnings:
            ET.SubElement(warnings_el, "warning").text = w

    if result.errors:
        errors_el = ET.SubElement(root, "errors")
        for e in result.errors:
            ET.SubElement(errors_el, "error").text = e

    parts_el = ET.SubElement(root, "parts")
    for part in result.parts:
        meta = build_metadata(part)
        part_el = ET.SubElement(parts_el, "part")
        _dict_to_xml(meta, part_el)

    xml_str = minidom.parseString(
        ET.tostring(root, encoding='unicode')
    ).toprettyxml(indent="  ")

    lines = xml_str.splitlines()
    if lines[0].startswith("<?xml"):
        xml_str = "\n".join(lines[1:])

    with open(path, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write(xml_str)

    print(f"[forge] XML salvato in {path}")


def _dict_to_xml(d: dict, parent: ET.Element):
    """Converte ricorsivamente un dict in sotto-elementi XML."""
    for key, value in d.items():
        child = ET.SubElement(parent, str(key))
        if isinstance(value, dict):
            _dict_to_xml(value, child)
        else:
            child.text = str(value)


# ---------------------------------------------------------------------------
# Export nester (coordinate grezze — non usa schema)
# ---------------------------------------------------------------------------

def to_nester_input(result: ForgeResult) -> list:
    """
    Produce l'input per il nester: coordinate grezze + metadati base.
    Non usa metadata_schema — il nester ha bisogno delle coordinate, non dei nomi.
    """
    parts = []
    for part in result.parts:
        parts.append({
            "label"       : part.label,
            "source_file" : part.source_file,
            "area"        : part.area,
            "bbox"        : part.bbox,
            "outer_coords": list(part.outer.polygon.exterior.coords),
            "holes_coords": [list(h.polygon.exterior.coords) for h in part.inners],
        })
    return parts


# ---------------------------------------------------------------------------
# XDATA DXF
# ---------------------------------------------------------------------------

def write_metadata_to_dxf(doc, part: ForgePart):
    """
    Scrive i metadati come XDATA sull'entità OuterContour.
    I campi seguono metadata_schema.py — stessa fonte di save_json e save_xml.
    Supporta LWPOLYLINE, POLYLINE e CIRCLE su layer OuterContour.
    """
    try:
        from ..rules.layers import LAYER_OUTER
        msp = doc.modelspace()

        outer_entity = None

        for pline in msp.query('LWPOLYLINE POLYLINE'):
            if pline.dxf.layer == LAYER_OUTER:
                outer_entity = pline
                break

        if outer_entity is None:
            for circle in msp.query('CIRCLE'):
                if circle.dxf.layer == LAYER_OUTER:
                    outer_entity = circle
                    break

        if outer_entity is None:
            print("  [WARN] write_metadata_to_dxf: nessuna entità su OuterContour.")
            return

        app_id = 'FORGE'
        if app_id not in doc.appids:
            doc.appids.add(app_id)

        meta = build_metadata(part)

        outer_entity.set_xdata(app_id, [
            (1000, json.dumps(meta, ensure_ascii=False)),
        ])

    except Exception as ex:
        print(f"  [WARN] write_metadata_to_dxf: {ex}")


def read_metadata_from_dxf(doc) -> dict:
    """
    Legge i metadati FORGE XDATA dall'entità OuterContour.
    Cerca su LWPOLYLINE, POLYLINE e CIRCLE.

    Returns:
        dict con i metadati secondo schema — o dict vuoto.
    """
    try:
        from ..rules.layers import LAYER_OUTER
        msp = doc.modelspace()

        outer_entity = None

        for pline in msp.query('LWPOLYLINE POLYLINE'):
            if pline.dxf.layer == LAYER_OUTER:
                outer_entity = pline
                break

        if outer_entity is None:
            for circle in msp.query('CIRCLE'):
                if circle.dxf.layer == LAYER_OUTER:
                    outer_entity = circle
                    break

        if outer_entity is None:
            return {}

        xdata = outer_entity.get_xdata('FORGE')
        if not xdata:
            return {}

        for tag in xdata:
            if tag.code == 1000:
                return json.loads(tag.value)

        return {}

    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Upgrade R12 → R2010
# ---------------------------------------------------------------------------

def upgrade_to_r2010(doc) -> object:
    """
    Converte un documento DXF (qualsiasi versione) in R2010.
    Ricopia tutte le entità del modelspace nel nuovo documento.
    Utile per file R12 che non supportano XDATA.

    Le POLYLINE R12 (anche con bulge/archi) vengono esplose in LINE/ARC
    prima della copia — così heal() le gestisce correttamente.
    """
    if doc.dxfversion >= 'AC1015':
        return doc  # già R2010+, nessuna operazione
    
    import ezdxf

    new_doc = ezdxf.new('R2010')
    new_msp = new_doc.modelspace()
    old_msp = doc.modelspace()

    # --- Passo 0: esplodi INSERT in place ---
    for entity in list(old_msp.query('INSERT')):
        try:
            entity.explode()
        except Exception as ex:
            print(f"  [WARN] upgrade_to_r2010: explode INSERT fallito — {ex}")

    # --- Passo 1: esplodi tutte le POLYLINE in place ---
    # entity.explode() aggiunge LINE/ARC al old_msp e rimuove la POLYLINE
    for entity in list(old_msp.query('POLYLINE')):
        try:
            entity.explode()
        except Exception as ex:
            print(f"  [WARN] upgrade_to_r2010: explode POLYLINE fallito — {ex}")

    # --- Passo 2: copia tutto nel nuovo doc ---
    copied = 0
    skipped = 0

    for entity in old_msp:
        dxftype = entity.dxftype()
        attribs = entity.dxfattribs()
        attribs.pop('handle', None)
        attribs.pop('owner', None)

        try:
            if dxftype == 'LINE':
                new_msp.add_line(entity.dxf.start, entity.dxf.end,
                                 dxfattribs=attribs)

            elif dxftype == 'ARC':
                new_msp.add_arc(
                    entity.dxf.center, entity.dxf.radius,
                    entity.dxf.start_angle, entity.dxf.end_angle,
                    dxfattribs=attribs,
                )

            elif dxftype == 'CIRCLE':
                new_msp.add_circle(entity.dxf.center, entity.dxf.radius,
                                   dxfattribs=attribs)

            elif dxftype == 'LWPOLYLINE':
                pts = list(entity.get_points(format='xyseb'))
                new_msp.add_lwpolyline(
                    pts, format='xyseb',
                    dxfattribs=attribs,
                    close=entity.closed,
                )

            elif dxftype == 'SPLINE':
                new_msp.add_spline(entity.control_points, dxfattribs=attribs)

            elif dxftype == 'TEXT':
                new_msp.add_text(entity.dxf.text, dxfattribs=attribs)

            elif dxftype == 'MTEXT':
                new_msp.add_mtext(entity.text, dxfattribs=attribs)

            # elif dxftype == 'INSERT':
            #     new_msp.add_blockref(entity.dxf.name, entity.dxf.insert,
            #                          dxfattribs=attribs)

            else:
                skipped += 1
                continue

            copied += 1

        except Exception as ex:
            print(f"  [WARN] upgrade_to_r2010: skip {dxftype} — {ex}")
            skipped += 1

    print(f"  [upgrade] {copied} entità copiate, {skipped} skippate → R2010")
    return new_doc