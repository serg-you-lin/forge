# """
# rules/classifier.py
# -------------------
# Logica pura di classificazione geometrica.

# Contiene solo GeometricInterpreter — nessuna orchestrazione,
# nessuna scrittura su part.custom, nessuna dipendenza da special_layers.

# L'orchestrazione è in workflow/classifier.py.
# """

# from __future__ import annotations

# from typing import List
# from shapely.geometry import Point, LineString
# import math

# from ..core.models import (
#     BaseInterpreter,
#     ClassifiedEntity,
#     BendingLine,
# )


# class GeometricInterpreter(BaseInterpreter):
#     """
#     Interpreter geometrico — classifica entità tramite geometria e hints.

#     Riceve gli hints da classify() (che li ha letti da part.geometry_hints)
#     e restituisce una lista di ClassifiedEntity.

#     Le BendingLine trovate sono esposte via self.bend_lines —
#     workflow/classifier.py le legge e le scrive su part.custom
#     solo se special_layers non ha già coperto il bending.

#     Hints attesi:
#         countersink_ids   : set di id() entità CIRCLE svasature
#         threaded_hole_ids : set di id() entità CIRCLE filettati
#         bend_line_ids     : set di id() entità LINE di piega
#     """

#     def classify(
#         self,
#         entities,
#         outer_poly,
#         inner_polys,
#         msp,
#         hints: dict = None,
#     ) -> List[ClassifiedEntity]:
#         hints = hints or {}
#         countersink_ids   = hints.get("countersink_ids",   set())
#         threaded_hole_ids = hints.get("threaded_hole_ids", set())
#         bend_line_ids     = hints.get("bend_line_ids",     set())

#         classified:      List[ClassifiedEntity] = []
#         self.bend_lines: List[BendingLine]      = []  # reset per ogni chiamata

#         for entity in entities:
#             eid = id(entity)

#             if eid in countersink_ids:
#                 classified.append(ClassifiedEntity(
#                     entity=entity,
#                     work_type="countersink",
#                     confidence=1.0,
#                     source="geometric",
#                 ))
#                 continue

#             if eid in threaded_hole_ids:
#                 classified.append(ClassifiedEntity(
#                     entity=entity,
#                     work_type="threaded_hole",
#                     confidence=1.0,
#                     source="geometric",
#                 ))
#                 continue

#             if eid in bend_line_ids:
#                 s = entity.dxf.start
#                 midpoint = Point(
#                     (s.x + entity.dxf.end.x) / 2,
#                     (s.y + entity.dxf.end.y) / 2,
#                 )
#                 if outer_poly.contains(midpoint) or \
#                    outer_poly.boundary.distance(midpoint) < 1.0:
#                     bl = bending_line_from_entity(entity)
#                     self.bend_lines.append(bl)
#                     classified.append(ClassifiedEntity(
#                         entity=entity,
#                         work_type="bending",
#                         confidence=1.0,
#                         source="geometric",
#                     ))
#                 continue

#         return classified
    
# ######################################################################
# # - Helpers di interpretazione geometrica
# ######################################################################

# def bending_line_from_entity(entity, part_label: str = "") -> "BendingLine":
#     """
#     Factory: LINE ezdxf → BendingLine.
#     Calcola geometria, lunghezza e angolo automaticamente.
#     """
#     s      = entity.dxf.start
#     e      = entity.dxf.end
#     geom   = LineString([(s.x, s.y), (e.x, e.y)])
#     length = geom.length
#     dx     = e.x - s.x
#     dy     = e.y - s.y
#     angle  = math.degrees(math.atan2(dy, dx)) % 180.0  # 0–180°, direzione non conta

#     return BendingLine(
#         entity=entity,
#         geometry=geom,
#         length=length,
#         layer=entity.dxf.layer if entity.dxf.hasattr("layer") else "",
#         angle_deg=angle,
#         part_label=part_label,
#     )



