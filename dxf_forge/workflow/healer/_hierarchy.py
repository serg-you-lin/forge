from ...core.models import (
    ForgePart,
    ForgeContour,
    GeometryHints,
    Hole,
    HOLE_TYPE_UNKNOWN,
)
from ...adapters.dxf.geometry_adapter import (
    entity_to_polygon,
)
from ._helpers import _spline_to_polygon
from ...rules.layers import (
    LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
    COLOR_INNER,
    HOLE_DIAMETER_THRESHOLD, STRUCTURAL_LAYERS,
)


def _build_hierarchy(self):
    shapes = []
    for vs in self.result._virtual_shapes:
        shapes.append((vs, vs.polygon, "VIRTUAL"))
    for pline in self.all_plines:
        poly = entity_to_polygon(pline)
        if poly:
            shapes.append((pline, poly, "LWPOLYLINE"))
    for circle in self.all_circles:
        poly = entity_to_polygon(circle)
        if poly:
            shapes.append((circle, poly, "CIRCLE"))
    for spline in self.closed_splines:
        poly = _spline_to_polygon(spline)
        if poly:
            shapes.append((spline, poly, "SPLINE"))

    if not shapes:
        self.result.errors.append("Nessuna geometria chiusa trovata dopo healing.")
        self.result.is_valid = False
        return

    shapes.sort(key=lambda x: x[1].area, reverse=True)

    def _place(obj, poly, tipo, nodes):
        for node in nodes:
            if node[1].contains(poly):
                if not _place(obj, poly, tipo, node[3]):
                    node[3].append([obj, poly, tipo, []])
                return True
        return False

    fathers = []
    for obj, poly, tipo in shapes:
        if not _place(obj, poly, tipo, fathers):
            fathers.append([obj, poly, tipo, []])

    for node in fathers:
        for child in node[3]:
            if child[2] == "VIRTUAL":
                child[0].layer = LAYER_INNER
                child[0].color = COLOR_INNER

    for father in fathers:
        father_obj, father_poly, father_tipo, children = father

        outer = ForgeContour(
            polygon=father_poly,
            is_inner=False,
            layer=LAYER_OUTER,
            entity=father_obj if father_tipo != "VIRTUAL" else None,
        )

        if father_tipo == "VIRTUAL":
            self.classified_virtual_ids.add(id(father_obj))
        else:
            self.classified_entity_ids.add(id(father_obj))

        holes  = []
        inners = []

        for child in children:
            child_obj, child_poly, child_tipo, grandchildren = child

            if grandchildren:
                if child_tipo == "VIRTUAL":
                    self.classified_virtual_ids.add(id(child_obj))
                else:
                    self.classified_entity_ids.add(id(child_obj))
                    self.result.trash_entities.append(child_obj)

                outer_diameter = child_obj.dxf.radius * 2 if child_tipo == "CIRCLE" else None

                for gc in grandchildren:
                    gc_obj, gc_poly, gc_tipo, _ = gc

                    if gc_tipo == "CIRCLE":
                        diameter = gc_obj.dxf.radius * 2
                        center   = (gc_obj.dxf.center.x, gc_obj.dxf.center.y)
                        layer    = LAYER_HOLE if diameter < HOLE_DIAMETER_THRESHOLD else LAYER_INNER
                        holes.append(Hole(
                            polygon=gc_poly,
                            diameter=diameter,
                            center=center,
                            hole_type=HOLE_TYPE_UNKNOWN,
                            geometric_hint="countersink",
                            layer=layer,
                            source_layer=(
                                gc_obj.source_layer if gc_tipo == "VIRTUAL"
                                else gc_obj.dxf.layer if gc_obj.dxf.hasattr("layer")
                                else ""
                            ),
                            entity=gc_obj,
                            outer_diameter=outer_diameter,
                            outer_entity=child_obj if child_tipo != "VIRTUAL" else None,
                        ))
                    else:
                        inners.append(ForgeContour(
                            polygon=gc_poly,
                            is_inner=True,
                            layer=LAYER_INNER,
                            is_hole=False,
                            entity=gc_obj if gc_tipo != "VIRTUAL" else None,
                            source_layer=(
                                gc_obj.source_layer if gc_tipo == "VIRTUAL"
                                else gc_obj.dxf.layer if gc_obj.dxf.hasattr("layer")
                                else ""
                            ),
                        ))

                    if gc_tipo == "VIRTUAL":
                        self.classified_virtual_ids.add(id(gc_obj))
                    else:
                        self.classified_entity_ids.add(id(gc_obj))

            else:
                if child_tipo == "CIRCLE":
                    diameter = child_obj.dxf.radius * 2
                    center   = (child_obj.dxf.center.x, child_obj.dxf.center.y)
                    layer    = LAYER_HOLE if diameter < HOLE_DIAMETER_THRESHOLD else LAYER_INNER
                    holes.append(Hole(
                        polygon=child_poly,
                        diameter=diameter,
                        center=center,
                        hole_type=HOLE_TYPE_UNKNOWN,
                        geometric_hint="",
                        layer=layer,
                        source_layer=(
                            child_obj.dxf.layer if child_obj.dxf.hasattr("layer") else ""
                        ),
                        entity=child_obj,
                    ))
                else:
                    inners.append(ForgeContour(
                        polygon=child_poly,
                        is_inner=True,
                        layer=LAYER_INNER,
                        is_hole=False,
                        entity=child_obj if child_tipo != "VIRTUAL" else None,
                        source_layer=(
                            child_obj.source_layer if child_tipo == "VIRTUAL"
                            else child_obj.dxf.layer if child_obj.dxf.hasattr("layer")
                            else ""
                        ),
                        vs_id=id(child_obj) if child_tipo == "VIRTUAL" else None,
                    ))

                if child_tipo == "VIRTUAL":
                    self.classified_virtual_ids.add(id(child_obj))
                else:
                    self.classified_entity_ids.add(id(child_obj))

        entity_ids = set()
        entity_ids.add(id(father_obj))

        for child in children:
            child_obj, _, child_tipo, grandchildren = child
            entity_ids.add(id(child_obj))
            for gc in grandchildren:
                gc_obj, _, gc_tipo, _ = gc
                entity_ids.add(id(gc_obj))

        for hole in holes:
            if hole.entity is not None:
                entity_ids.add(id(hole.entity))
            if hole.outer_entity is not None:
                entity_ids.add(id(hole.outer_entity))

        for inner in inners:
            if inner.entity is not None:
                entity_ids.add(id(inner.entity))

        part = ForgePart(
            outer=outer,
            holes=holes,
            inners=inners,
            label=self.label,
            source_file=self.source_file,
            custom={},
            geometry_hints=GeometryHints(),
            entity_ids=entity_ids,
        )

        if father_tipo == "VIRTUAL":
            self.result._vs_to_part[id(father_obj)] = part

        for child in children:
            child_obj, _, child_tipo, grandchildren = child
            if child_tipo == "VIRTUAL":
                self.result._vs_to_part[id(child_obj)] = part
            for gc in grandchildren:
                gc_obj, _, gc_tipo, _ = gc
                if gc_tipo == "VIRTUAL":
                    self.result._vs_to_part[id(gc_obj)] = part

        self.result.parts.append(part)


def _build_trash(self):
    self.result.trash_entities += [
        e for e in self.msp
        if id(e) not in self.classified_entity_ids
        and id(e) not in self.classified_virtual_ids
        and e.dxf.hasattr("layer")
        and e.dxf.layer.upper() not in STRUCTURAL_LAYERS
        and (
            id(e) not in self.entities_in_loops
            or e.dxf.layer.lower() in self.special_layer_names
        )
    ]

    self.result.parts.sort(key=lambda p: p.outer.polygon.area, reverse=True)