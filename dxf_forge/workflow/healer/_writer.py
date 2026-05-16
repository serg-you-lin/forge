# from ...core.geometry import is_countersink_outer

# from ...core.virtual import _write_virtual_shape


# from ...rules.layers import (
#     LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
#     LAYER_BENDING, LAYER_MARKING, LAYER_ENGRAVE, LAYER_COUNTERSINK, LAYER_THREADED_HOLE,
#     COLOR_OUTER, COLOR_INNER, COLOR_HOLE,
#     COLOR_BENDING, COLOR_MARKING, COLOR_ENGRAVE, COLOR_COUNTERSINK, COLOR_TRASH, COLOR_THREADED_HOLE,
#     HOLE_DIAMETER_THRESHOLD, STRUCTURAL_LAYERS, TRASH_LAYER,
#     WORK_TYPE_TO_LAYER,
# )

# def _apply_to_msp(
#     msp,
#     virtual_shapes: list,
#     fathers: list,
#     entities_in_loops: set,
#     classified_entity_ids: set,
#     special_layers: dict,
#     keep_trash: bool,
#     countersink_ids: set = None,           # ← aggiunta
#     threaded_hole_ids: set = None,   
#     bend_line_ids: set = None,           # ← aggiunta
# ) -> None:
#     """
#     Materializza il risultato dell'healing nel modelspace.
 
#     Responsabilità:
#         - Scrive le VirtualShape come LWPOLYLINE nel msp
#         - Cancella LINE/ARC/SPLINE originali usati nei loop
#         - Assegna layer e colori alle entità reali
#         - Sposta le entità non classificate su Trash (o le cancella)
 
#     Non tocca il ForgeResult — è puro effetto collaterale sul msp.
#     """
#     # Entità nei loop con spline — NON vengono cancellate
#     spline_loop_entity_ids: set = set()
#     for vs in virtual_shapes:
#         if vs.has_spline:
#             for entity, _ in vs.loop:
#                 spline_loop_entity_ids.add(id(entity))
 
#     # Materializza VirtualShape nel msp
#     for vs in virtual_shapes:
#         entity = _write_virtual_shape(msp, vs)
#         if entity is not None:
#             vs.entity = entity
#             classified_entity_ids.add(id(entity))
#         else:
#             for orig_entity, _ in vs.loop:
#                 classified_entity_ids.add(id(orig_entity))
 
#     # Cancella LINE/ARC/SPLINE originali usati nei loop
#     # MA NON quelli nei loop con spline
#     for entity in list(msp.query('LINE ARC SPLINE')):
#         if id(entity) in entities_in_loops \
#            and id(entity) not in spline_loop_entity_ids:
#             msp.delete_entity(entity)
 
#     # if countersink_ids:
#     #     classified_entity_ids.update(countersink_ids) 
#     # if bend_line_ids:
#     #     classified_entity_ids.update(bend_line_ids)
#     # Assegna layer/colori alle entità reali
#     for father_obj, father_poly, father_tipo, children in fathers:
#         if father_tipo != 'VIRTUAL':
#             father_obj.dxf.layer = LAYER_OUTER
#             father_obj.dxf.color = COLOR_OUTER
 
#         for child_obj, child_poly, child_tipo in children:
#             if child_tipo == 'VIRTUAL':
#                 continue
#             if child_tipo == 'CIRCLE':
#                 #print(f"countersink_ids: {countersink_ids}")
#                 #print(f"child id: {id(child_obj)}")
#                 #print(f"is_countersink_outer: {is_countersink_outer(child_obj, children)}")
#                 if is_countersink_outer(child_obj, children):
#                     print(f"  → in countersink_ids: {id(child_obj) in countersink_ids}")
#                     print(f"  → countersink_ids bool: {bool(countersink_ids)}")
#                     if countersink_ids and id(child_obj) in countersink_ids:
#                         print("  → assegno LAYER_COUNTERSINK")
#                         child_obj.dxf.layer = LAYER_COUNTERSINK
#                     else:
#                         print("  → assegno TRASH_LAYER")
#                         child_obj.dxf.color = COLOR_TRASH
#                     continue
#                 diameter = child_obj.dxf.radius * 2
#                 if diameter < HOLE_DIAMETER_THRESHOLD:
#                     if threaded_hole_ids and id(child_obj) in threaded_hole_ids:
#                         layer = LAYER_THREADED_HOLE
#                         color = COLOR_THREADED_HOLE
#                     else:
#                         layer = LAYER_HOLE
#                         color = COLOR_HOLE
#                 else:
#                     layer = LAYER_INNER
#                     color = COLOR_INNER
    
#             else:
#                 layer = LAYER_INNER
#                 color = COLOR_INNER
#             child_obj.dxf.layer = layer
#             child_obj.dxf.color = color


#     # Trash — entità non classificate
#     for entity in list(msp):
#         if id(entity) in classified_entity_ids:
#             continue
#         layer = entity.dxf.layer if entity.dxf.hasattr("layer") else ""
#         if layer.upper() in STRUCTURAL_LAYERS:
#             continue
#         if special_layers and layer.lower() in {k.lower() for k in special_layers}:
#             work_type = next(
#                 v for k, v in special_layers.items()
#                 if k.lower() == layer.lower()
#             )
#             target_layer, target_color = WORK_TYPE_TO_LAYER.get(
#                 work_type, (TRASH_LAYER, COLOR_TRASH)
#             )
#             entity.dxf.layer = target_layer
#             entity.dxf.color = target_color
#             continue
 
#         if keep_trash:
#             entity.dxf.layer = TRASH_LAYER
#             entity.dxf.color = COLOR_TRASH
#         else:
#             msp.delete_entity(entity)



from ...core.geometry import is_countersink_outer
from ...core.virtual import _write_virtual_shape
from ...rules.layers import (
    LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
    LAYER_BENDING, LAYER_MARKING, LAYER_ENGRAVE, LAYER_COUNTERSINK, LAYER_THREADED_HOLE,
    COLOR_OUTER, COLOR_INNER, COLOR_HOLE,
    COLOR_BENDING, COLOR_MARKING, COLOR_ENGRAVE, COLOR_COUNTERSINK, COLOR_TRASH, COLOR_THREADED_HOLE,
    HOLE_DIAMETER_THRESHOLD, STRUCTURAL_LAYERS, TRASH_LAYER,
    WORK_TYPE_TO_LAYER,
)


def _apply_to_msp(
    msp,
    virtual_shapes:        list,
    fathers:               list,
    entities_in_loops:     set,
    classified_entity_ids: set,
    special_layers:        dict,
    keep_trash:            bool,
    countersink_ids:       set = None,
    threaded_hole_ids:     set = None,
    bend_line_ids:         set = None,
) -> None:
    """
    Materializza il risultato dell'healing nel modelspace.

    Responsabilità:
        - Scrive le VirtualShape come LWPOLYLINE nel msp
        - Cancella LINE/ARC/SPLINE originali usati nei loop
        - Assegna layer e colori alle entità reali
        - Sposta le entità non classificate su Trash (o le cancella)

    Non tocca il ForgeResult — è puro effetto collaterale sul msp.
    """
    # Entità nei loop con spline — NON vengono cancellate
    spline_loop_entity_ids: set = set()
    for vs in virtual_shapes:
        if vs.has_spline:
            for entity, _ in vs.loop:
                spline_loop_entity_ids.add(id(entity))

    # Materializza VirtualShape nel msp
    for vs in virtual_shapes:
        entity = _write_virtual_shape(msp, vs)
        if entity is not None:
            vs.entity = entity
            classified_entity_ids.add(id(entity))
        else:
            for orig_entity, _ in vs.loop:
                classified_entity_ids.add(id(orig_entity))

    # Cancella LINE/ARC/SPLINE originali usati nei loop
    # MA NON quelli nei loop con spline
    for entity in list(msp.query('LINE ARC SPLINE')):
        if id(entity) in entities_in_loops \
           and id(entity) not in spline_loop_entity_ids:
            msp.delete_entity(entity)

    # Assegna layer/colori alle entità reali
    for father_obj, father_poly, father_tipo, children in fathers:
        if father_tipo != 'VIRTUAL':
            father_obj.dxf.layer = LAYER_OUTER
            father_obj.dxf.color = COLOR_OUTER

        for child_obj, child_poly, child_tipo in children:
            if child_tipo == 'VIRTUAL':
                continue

            if child_tipo == 'CIRCLE':
                if is_countersink_outer(child_obj, children):
                    if countersink_ids and id(child_obj) in countersink_ids:
                        child_obj.dxf.layer = LAYER_COUNTERSINK
                        child_obj.dxf.color = COLOR_COUNTERSINK
                    else:
                        child_obj.dxf.layer = TRASH_LAYER
                        child_obj.dxf.color = COLOR_TRASH
                    # aggiunto a classified qui — dopo l'assegnazione layer,
                    # così il loop Trash non lo sovrascrive
                    classified_entity_ids.add(id(child_obj))
                    continue

                diameter = child_obj.dxf.radius * 2
                if diameter < HOLE_DIAMETER_THRESHOLD:
                    if threaded_hole_ids and id(child_obj) in threaded_hole_ids:
                        layer = LAYER_THREADED_HOLE
                        color = COLOR_THREADED_HOLE
                    else:
                        layer = LAYER_HOLE
                        color = COLOR_HOLE
                else:
                    layer = LAYER_INNER
                    color = COLOR_INNER
            else:
                layer = LAYER_INNER
                color = COLOR_INNER

            child_obj.dxf.layer = layer
            child_obj.dxf.color = color
            classified_entity_ids.add(id(child_obj))

    # Trash — entità non classificate
    for entity in list(msp):
        if id(entity) in classified_entity_ids:
            continue
        layer = entity.dxf.layer if entity.dxf.hasattr("layer") else ""
        if layer.upper() in STRUCTURAL_LAYERS:
            continue
        if special_layers and layer.lower() in {k.lower() for k in special_layers}:
            work_type = next(
                v for k, v in special_layers.items()
                if k.lower() == layer.lower()
            )
            target_layer, target_color = WORK_TYPE_TO_LAYER.get(
                work_type, (TRASH_LAYER, COLOR_TRASH)
            )
            entity.dxf.layer = target_layer
            entity.dxf.color = target_color
            continue

        if keep_trash:
            entity.dxf.layer = TRASH_LAYER
            entity.dxf.color = COLOR_TRASH
        else:
            msp.delete_entity(entity)