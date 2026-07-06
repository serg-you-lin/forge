"""
dxf_inspect.py
--------------
Ispezione e logging configurabile di file DXF.

Uso nei tuoi script di test:
    from dxf_inspect import DxfInspector

    inspector = DxfInspector(
        lines=True,
        arcs=True,
        polylines=True,
        circles=False,
        graph=True,
        splines=False,
    )
    inspector.analyze(msp)
    inspector.print_graph(msp)

Oppure tutto:
    inspector = DxfInspector.all()
    inspector.analyze(msp)

Oppure niente (solo summary):
    inspector = DxfInspector()
    inspector.analyze(msp)
"""

import logging
# from pydoc import doc
# import numpy as np
from collections import defaultdict, Counter
from forge.io.text_utils import extract_texts_from_msp, extract_texts
from forge.core.graph import build_node_graph
from forge.adapters.dxf.graph_adapter import entity_endpoints

# ---------------------------------------------------------------------------
# Setup logger
# ---------------------------------------------------------------------------

logger = logging.getLogger("dxf_inspect")

def setup_logging(level=logging.DEBUG):
    """
    Configura il logger dxf_inspect su stdout.
    Chiamare una volta sola all'inizio dello script.
    """
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(level)


# ---------------------------------------------------------------------------
# Inspector
# ---------------------------------------------------------------------------

class DxfInspector:
    """
    Ispeziona un modelspace ezdxf con logging configurabile per categoria.

    Parametri (tutti False di default — accendi solo quello che ti serve):
        lines      : stampa ogni LINE con start/end/layer/colore
        arcs       : stampa ogni ARC con centro/raggio/angoli/layer/colore
        polylines  : stampa ogni LWPOLYLINE/POLYLINE con vertici e bulge
        circles    : stampa ogni CIRCLE con centro/raggio/layer/colore
        splines    : stampa ogni SPLINE con flattening e endpoint
        other      : stampa le entità non gestite sopra
        graph      : stampa il grafo nodi (endpoint LINE+ARC+SPLINE)
        summary    : stampa sempre il conteggio per tipo (default True)
    """

    def __init__(
        self,
        lines:     bool = False,
        arcs:      bool = False,
        polylines: bool = False,
        circles:   bool = False,
        splines:   bool = False,
        dimensions: bool = False,
        text:      bool = False,
        other:     bool = False,
        graph:     bool = False,
        summary:   bool = True,
        decimals:  int  = 1,
    ):
        self.lines     = lines
        self.arcs      = arcs
        self.polylines = polylines
        self.circles   = circles
        self.splines   = splines
        self.dimensions = dimensions
        self.text      = text
        self.other     = other
        self.graph     = graph
        self.summary   = summary
        self.decimals  = decimals
        setup_logging()

    @classmethod
    def all(cls, decimals: int = 1) -> "DxfInspector":
        """Factory: accende tutto."""
        return cls(
            lines=True, arcs=True, polylines=True,
            circles=True, splines=True, other=True,
            graph=True, summary=True, decimals=decimals,
        )

    @classmethod
    def geometry_only(cls) -> "DxfInspector":
        """Factory: solo entità geometriche strutturali, no graph."""
        return cls(lines=True, arcs=True, polylines=True, circles=True)

    # ---------------------------------------------------------------------------
    # Metodo principale
    # ---------------------------------------------------------------------------

    def analyze(self, msp, title: str = "", doc=None):
        """
        Analizza il modelspace e logga secondo la configurazione.

        Args:
            msp: modelspace ezdxf
            title: titolo opzionale stampato in cima
        """
        sep = "-" * 50
        if title:
            logger.debug(f"\n{sep}")
            logger.debug(f"Analisi: {title}")
            logger.debug(sep)

        if self.summary:
            self._log_summary(msp, doc=doc)

        for entity in msp:
            dxftype = entity.dxftype()

            if dxftype == "LINE" and self.lines:
                self._log_line(entity)
            elif dxftype == "ARC" and self.arcs:
                self._log_arc(entity)
            elif dxftype in ("LWPOLYLINE", "POLYLINE") and self.polylines:
                self._log_polyline(entity)
            elif dxftype == "CIRCLE" and self.circles:
                self._log_circle(entity)
            elif dxftype == "SPLINE" and self.splines:
                self._log_spline(entity)
            elif dxftype == "DIMENSION" and self.dimensions:
                self._log_dimension(entity)
            elif dxftype == "INSERT":
                pass
                # self._log_inserts(entity)
            elif dxftype not in ("LINE", "ARC", "LWPOLYLINE", "POLYLINE", "CIRCLE", "SPLINE") and self.other:
                self._log_other(entity)

        if self.text and doc is not None:
            self._log_all_texts(msp, doc)
    
        if self.graph:
            self._log_graph(msp)

    # ---------------------------------------------------------------------------
    # Log per tipo
    # ---------------------------------------------------------------------------

    def _attribs(self, entity) -> str:
        """Restituisce layer e colore come stringa."""
        layer = entity.dxf.layer if entity.dxf.hasattr("layer") else "?"
        color = entity.dxf.color if entity.dxf.hasattr("color") else "?"
        return f"layer={layer!r}  color={color}"

    def _log_summary(self, msp, doc=None):
        # Versione DXF
        if doc is not None:
            logger.debug(f"\n--- FILE INFO ---")
            logger.debug(f"  Versione DXF : {doc.dxfversion}")
            # XREF
            xrefs = [b for b in doc.blocks if b.name not in ('*Model_Space', '*Paper_Space') 
                    and b.block.dxf.flags & 4]
            if xrefs:
                logger.debug(f"  XREF ({len(xrefs)}): {[x.name for x in xrefs]}")
            else:
                logger.debug(f"  XREF: nessuna")
            # XDATA FORGE
            xdata_count = 0
            for entity in msp:
                try:
                    if entity.get_xdata('FORGE'):
                        xdata_count += 1
                except Exception:
                    pass
            logger.debug(f"  XDATA FORGE  : {xdata_count} entità")

        counts = Counter(e.dxftype() for e in msp)
        logger.debug("\n--- ENTITÀ ---")
        for t, n in sorted(counts.items()):
            logger.debug(f"  {t}: {n}")

    def _log_line(self, entity):
        logger.debug(f"\nLINE  {self._attribs(entity)}")
        logger.debug(f"  start : {entity.dxf.start}")
        logger.debug(f"  end   : {entity.dxf.end}")

    def _log_arc(self, entity):
        logger.debug(f"\nARC  {self._attribs(entity)}")
        logger.debug(f"  centro       : {entity.dxf.center}")
        logger.debug(f"  raggio       : {entity.dxf.radius}")
        logger.debug(f"  angolo start : {entity.dxf.start_angle}")
        logger.debug(f"  angolo end   : {entity.dxf.end_angle}")

    def _log_circle(self, entity):
        logger.debug(f"\nCIRCLE  {self._attribs(entity)}")
        logger.debug(f"  centro : {entity.dxf.center}")
        logger.debug(f"  raggio : {entity.dxf.radius}")

    def _log_polyline(self, entity):
        dxftype = entity.dxftype()
        logger.debug(f"\n{dxftype}  {self._attribs(entity)}")

        if dxftype == "LWPOLYLINE":
            points = list(entity.get_points("xyb"))
            logger.debug(f"  vertici : {len(points)}  chiusa: {entity.closed}")
            for i, (x, y, bulge) in enumerate(points):
                seg = "LINEA" if bulge == 0 else f"ARCO (bulge={bulge:.4f})"
                logger.debug(f"    [{i+1}] ({x:.4f}, {y:.4f})  → {seg}")
        else:
            vertices = list(entity.vertices)
            logger.debug(f"  vertici : {len(vertices)}")
            for i, v in enumerate(vertices):
                logger.debug(f"    [{i+1}] {v.dxf.location}")

    def _log_spline(self, entity):
        logger.debug(f"\nSPLINE  {self._attribs(entity)}")
        try:
            pts = list(entity.flattening(distance=0.01))
            logger.debug(f"  punti flattening : {len(pts)}")
            logger.debug(f"  start : ({pts[0][0]:.4f}, {pts[0][1]:.4f})")
            logger.debug(f"  end   : ({pts[-1][0]:.4f}, {pts[-1][1]:.4f})")
        except Exception as ex:
            logger.debug(f"  flattening fallito: {ex}")
            try:
                pts = list(entity.fit_points)
                logger.debug(f"  fit_points: {len(pts)}")
            except Exception:
                pass

    def _log_dimension(self, entity):
        logger.debug(f"\nDIMENSION  {self._attribs(entity)}")
        logger.debug(f"  testo : {entity.dxf.text}")
        logger.debug(f"  punto di inserimento testo : {entity.dxf.text_midpoint}")
        # Altri attributi dimensione possono essere aggiunti qui

    def _log_all_texts(self, msp, doc):
        logger.debug("\n--- TESTI (estratti) ---")

        texts = extract_texts_from_msp(msp)

        if not texts:
            logger.debug("  Nessun testo trovato.")
            return

        for i, t in enumerate(texts, 1):
            logger.debug(f"  [{i}] '{t}' (len={len(t)})")

    # def _log_inserts(self, entity):
    #     try:
    #         block = doc.blocks.get(entity.dxf.name)
    #         inner = Counter(sub.dxftype() for sub in block)
    #         print(f"  INSERT '{entity.dxf.name}' contiene: {dict(inner)}")
    #     except Exception as ex:
    #         print(f"  INSERT error: {ex}")

    def _log_other(self, entity):
        logger.debug(f"\n{entity.dxftype()}  {self._attribs(entity)}")

    # ---------------------------------------------------------------------------
    # Grafo nodi
    # ---------------------------------------------------------------------------

    def _log_graph(self, msp):
        from dxf_forge.adapters.dxf.graph_adapter import edges_from_msp
        from dxf_forge.core.graph import build_node_graph

        logger.debug("\n--- GRAFO NODI ---")
        edges = edges_from_msp(msp, node_decimals=self.decimals)
        graph = build_node_graph(edges)

        branching = []
        for node, connections in sorted(graph.items()):
            degree = len(connections)
            flag = "  ← AMBIGUO" if degree > 2 else ""
            logger.debug(f"    {node}  grado={degree}{flag}")
            for edge, neighbor in connections:
                logger.debug(f"      [{edge.layer}] -> {neighbor}")
            if degree > 2:
                branching.append(node)

        if branching:
            logger.debug(f"\n  Nodi ambigui ({len(branching)}): {branching}")
        else:
            logger.debug("\n  Nessun nodo ambiguo.")
            
    def _round(self, pt):
        return (round(pt[0], self.decimals), round(pt[1], self.decimals))

