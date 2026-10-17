"""
topo/model/__init__.py
----------------------
I tipi del modello, pubblici (MAP.md D120): documento, risultato, cluster,
contorni, curve, annotazioni, stili, feature rilevate, ruoli e `Edge`.
Si scrive `topo.model.<Nome>`; i quattro più usati (`Document`, `Result`,
`Cluster`, `Contour`) stanno anche in `topo.<Nome>`.
"""
from .annotation import (
    Annotation, Note, Dimension, Leader, RenderedGeometry, RenderedText,
)
from .document import Document
from .contour import Contour
from .cluster import Cluster
from .result import Result
from .curve import Curve, ClosedCurve, OpenCurve
from .style import EdgeStyle
from .detected import DetectedFeature, DetectedFeatures
from .role import ContourRole, role_str, normalize_role, is_structural_role

__all__ = [
    "Document",
    "Annotation",
    "Note",
    "Dimension",
    "Leader",
    "RenderedGeometry",
    "RenderedText",
    "Contour",
    "Cluster",
    "Result",
    "Curve",
    "ClosedCurve",
    "OpenCurve",
    "EdgeStyle",
    "DetectedFeature",
    "DetectedFeatures",
    "ContourRole",
    "role_str",
    "normalize_role",
    "is_structural_role",
    "Edge",
]


def __getattr__(name):
    # Edge vive in core/topology (lo usa il grafo) e importa model.style:
    # caricato al primo accesso per non chiudere un import circolare.
    if name == "Edge":
        from ..core.topology.edge import Edge
        return Edge
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
