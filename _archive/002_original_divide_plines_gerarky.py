import ezdxf
from shapely.geometry import Polygon, Point, MultiPoint
import os
import re
import snapmark as sm


def extract_base_name(file_path):
    """
    Estrae la parte del nome fino a 'Nxx pz' compreso.
    """
    file_name = os.path.basename(file_path)
    match = re.search(r".*N°\d+\s*pz", file_name)
    if match:
        return match.group(0)
    else:
        return file_name.rsplit('.', 1)[0]


def polyline_to_shapely(pline):
    """Converte una LWPOLYLINE in un Polygon Shapely."""
    pts = [(p[0], p[1]) for p in pline.get_points()]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return Polygon(pts)


def get_entity_representative_point(entity):
    """
    Restituisce un punto rappresentativo dell'entità per il test point-in-polygon.
    Per le polilinee usa representative_point() di Shapely: garantito interno
    anche per forme concave (es. L dentro L).
    """
    dxftype = entity.dxftype()

    try:
        if dxftype == 'LINE':
            s = entity.dxf.start
            e = entity.dxf.end
            return Point((s.x + e.x) / 2, (s.y + e.y) / 2)

        elif dxftype in ('CIRCLE', 'ARC', 'ELLIPSE'):
            c = entity.dxf.center
            return Point(c.x, c.y)

        elif dxftype in ('TEXT', 'MTEXT'):
            p = entity.dxf.insert
            return Point(p.x, p.y)

        elif dxftype == 'INSERT':
            p = entity.dxf.insert
            return Point(p.x, p.y)

        elif dxftype == 'LWPOLYLINE':
            pts = [(p[0], p[1]) for p in entity.get_points()]
            # representative_point() garantisce un punto interno anche per forme concave
            return MultiPoint(pts).convex_hull.representative_point()

        elif dxftype == 'SPLINE':
            pts = [(p[0], p[1]) for p in entity.control_points]
            return MultiPoint(pts).convex_hull.representative_point()

        elif dxftype == 'HATCH':
            if entity.seeds:
                s = entity.seeds[0]
                return Point(s[0], s[1])
            return None

        elif dxftype == 'DIMENSION':
            p = entity.dxf.defpoint
            return Point(p.x, p.y)

        else:
            for attr in ('insert', 'start', 'center'):
                if entity.dxf.hasattr(attr):
                    p = getattr(entity.dxf, attr)
                    return Point(p.x, p.y)
            return None

    except Exception:
        return None


def build_polyline_hierarchy(polylines):
    """
    Costruisce la gerarchia padre-figlio tra polilinee.
    
    Analogo a: albero genealogico dove i padri sono i contorni esterni
    e i figli sono i fori o i sottocontorni interni.

    Returns:
        Lista di tuple (pline_padre, shape_padre, [figlie])
        dove figlie è lista di (pline_figlia, shape_figlia)
    """
    shapes = []
    for pline in polylines:
        pts = [(p[0], p[1]) for p in pline.get_points()]
        if len(pts) < 3:
            continue
        try:
            shape = Polygon(pts)
            if not shape.is_valid:
                shape = shape.buffer(0)  # fix geometrie self-intersecting
            shapes.append((pline, shape))
        except Exception as ex:
            print(f"  [WARN] Polilinea ignorata nella gerarchia: {ex}")
            continue

    # Ordina per area decrescente: i padri vengono prima
    shapes.sort(key=lambda x: x[1].area, reverse=True)

    fathers = []  # lista di (pline_padre, shape_padre, [figlie])

    for pline, shape in shapes:
        placed = False
        for father_pline, father_shape, children in fathers:
            if father_shape.contains(shape):
                children.append((pline, shape))
                placed = True
                break
        if not placed:
            # Non sta dentro nessun padre esistente: è un padre
            fathers.append((pline, shape, []))

    return fathers


def _copy_entity_to_msp(entity, target_msp):
    """
    Copia un'entità nel target modelspace.
    Ricostruzione per tipo, estendibile progressivamente.
    """
    dxftype = entity.dxftype()
    attribs = entity.dxfattribs()
    attribs.pop('handle', None)
    attribs.pop('owner', None)

    try:
        if dxftype == 'LINE':
            target_msp.add_line(entity.dxf.start, entity.dxf.end, dxfattribs=attribs)

        elif dxftype == 'CIRCLE':
            target_msp.add_circle(entity.dxf.center, entity.dxf.radius, dxfattribs=attribs)

        elif dxftype == 'ARC':
            target_msp.add_arc(
                entity.dxf.center, entity.dxf.radius,
                entity.dxf.start_angle, entity.dxf.end_angle,
                dxfattribs=attribs
            )

        elif dxftype == 'ELLIPSE':
            target_msp.add_ellipse(
                center=entity.dxf.center,
                major_axis=entity.dxf.major_axis,
                ratio=entity.dxf.ratio,
                start_param=entity.dxf.start_param,
                end_param=entity.dxf.end_param,
                dxfattribs=attribs
            )

        elif dxftype == 'TEXT':
            target_msp.add_text(entity.dxf.text, dxfattribs=attribs)

        elif dxftype == 'MTEXT':
            target_msp.add_mtext(entity.text, dxfattribs=attribs)

        elif dxftype == 'INSERT':
            target_msp.add_blockref(entity.dxf.name, entity.dxf.insert, dxfattribs=attribs)

        elif dxftype == 'LWPOLYLINE':
            pts = [(p[0], p[1]) for p in entity.get_points()]
            target_msp.add_lwpolyline(pts, dxfattribs=attribs)

        elif dxftype == 'SPLINE':
            target_msp.add_spline(entity.control_points, dxfattribs=attribs)

        else:
            print(f"  [SKIP] Tipo non gestito: {dxftype}")

    except Exception as ex:
        print(f"  [ERRORE] Copia {dxftype}: {ex}")


def split_polylines_with_contents(dxf_path, output_folder):
    """
    Splitta un DXF con più polilinee in tanti file quanti sono i "padri".
    
    Logica:
    - Le polilinee vengono ordinate per area (gerarchia padre-figlio)
    - Le polilinee figlie (interne a un padre) NON generano un file nuovo
      ma vengono copiate nel file del padre
    - Le entità non-polilinea vengono assegnate al padre che le contiene

    Args:
        dxf_path (str): Percorso al file DXF originale.
        output_folder (str): Cartella in cui salvare i DXF separati.
    """
    name = extract_base_name(dxf_path)
    print(f"Elaborazione: {name}")

    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    polylines = list(msp.query('LWPOLYLINE POLYLINE'))

    if len(polylines) <= 1:
        print("Una o nessuna polilinea trovata, nulla da fare.")
        return

    # Costruisce la gerarchia padre-figlio
    hierarchy = build_polyline_hierarchy(polylines)
    print(f"Trovati {len(hierarchy)} contorni padre, "
          f"{sum(len(c) for _, _, c in hierarchy)} polilinee figlie")

    # Tutte le entità non-polilinea
    all_entities = [e for e in msp if e.dxftype() not in ('LWPOLYLINE', 'POLYLINE')]

    os.makedirs(output_folder, exist_ok=True)

    for i, (father_pline, father_shape, children) in enumerate(hierarchy, start=1):

        new_doc = ezdxf.new()
        new_msp = new_doc.modelspace()

        # 1. Aggiungi la polilinea padre
        pts = [(p[0], p[1]) for p in father_pline.get_points()]
        if pts[0] != pts[-1]:
            pts.append(pts[0])
        new_msp.add_lwpolyline(pts, dxfattribs=father_pline.dxfattribs(), close=True)

        # 2. Aggiungi le polilinee figlie (fori, sottocontorni interni)
        for child_pline, child_shape in children:
            child_pts = [(p[0], p[1]) for p in child_pline.get_points()]
            new_msp.add_lwpolyline(child_pts, dxfattribs=child_pline.dxfattribs(), close=True)

        # 3. Aggiungi le entità non-polilinea interne al padre
        copied = 0
        for entity in all_entities:
            pt = get_entity_representative_point(entity)
            if pt is not None and father_shape.contains(pt):
                _copy_entity_to_msp(entity, new_msp)
                copied += 1

        filename = os.path.join(output_folder, f"{name}_P{i}.dxf")
        new_doc.saveas(filename)
        print(f"  -> {name}_P{i}.dxf | figlie: {len(children)} | entità interne: {copied}")

    print(f"Completato: {len(hierarchy)} file generati in '{output_folder}'")


# Esempio di utilizzo
if __name__ == "__main__":
    input_dxf = r"tests/examples/Polylines.dxf"
    output_dir = "tests/examples/output_polylines"
    split_polylines_with_contents(input_dxf, output_dir)

    def extract_part(output_dir, filename):
        match = re.search(r'_P(\d+)', filename)
        return f"P{match.group(1)}" if match else "P1"

    seq = (sm.SequenceBuilder()
        .file_part(separator='_', part_index=0)
        .custom(extract_part)
        .build())


    #sm.mark_by_splitted_text(output_dir, min_char=10, max_char=20)
    sm.mark_with_sequence(output_dir, seq, min_char=10, max_char=20, down_to=3)