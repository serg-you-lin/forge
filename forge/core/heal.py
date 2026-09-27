import sys
from pathlib import Path

if __package__:
    from ..model.result import ForgeResult
    from ..model.document import ForgeDocument
    from .topology.graph import build_node_graph
    from .geometry import node_decimals_for
    from .primitives.segments import ArcSeg, SplineSeg
    from .healing.gap_solver import (
        free_endpoints_from_edges, compute_gap_fixes, apply_gap_fixes,
        gap_endpoints_at_nodes,
    )
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from forge.model.result import ForgeResult
    from forge.model.document import ForgeDocument
    from forge.core.topology.graph import build_node_graph
    from forge.core.geometry import node_decimals_for
    from forge.core.primitives.segments import ArcSeg, SplineSeg
    from forge.core.healing.gap_solver import (
        free_endpoints_from_edges, compute_gap_fixes, apply_gap_fixes,
        gap_endpoints_at_nodes,
    )


class HealStep:
    """
    Esegue l'healing su un ForgeDocument — zero ezdxf.

    Lavora su doc.edges: gap closing (puro), esclusione degli edge non di
    contorno, ricerca loop, costruzione gerarchia.
    """

    def __init__(
        self,
        doc: ForgeDocument,
        tolerance,
        label="",
        source_file="",
        is_structural=None,
    ):
        self.doc             = doc
        self.tolerance       = tolerance
        self.label           = label
        self.source_file     = source_file
        # Predicato strutturale iniettato dal chiamante (tipicamente
        # heal_and_detect(), che passa tools.manufacturing_role.is_structural)
        # — il motore non sa cosa sia un foro o una piega, sa solo eseguire
        # un predicato che riceve. Senza iniezione, solo outer/inner sono
        # strutturali (vedi self._structural sotto).
        self._is_structural_fn = is_structural

        self.node_decimals = node_decimals_for(tolerance)
        self.result        = ForgeResult(source_file=source_file)

        label_map = doc.source_meta.get("label_map") or {}
        if label_map:
            self.result.label_map = label_map

        self.result.annotations = list(doc.annotations)

        self.non_contour_edge_ids  = set()
        self.loop_edge_ids         = set()
        self.entities_in_loops     = set()

        self.proxies = []
        self.closed_shapes = []
        self.labeled_edges = []

        self.edges = list(doc.edges)

    def run(self):
        self._load()
        if not self.result.is_valid:
            return self.result
        self._merge_collinear_overlaps()
        self._merge_cocircular_overlaps()
        self._weld_degenerate_linesegs()
        self._split_labeled()
        self._preprocess()
        self.result.all_arcs = [
            e.segment for e in self.edges if isinstance(e.segment, ArcSeg)
        ]
        self._find_non_contour_edges()
        self._find_loops()
        self._build_hierarchy()
        return self.result

    def _build_graph(self, exclude_ids=None, epsilon: float = 0.0):
        edges = self.edges
        if exclude_ids:
            edges = [e for e in edges if id(e) not in exclude_ids]
        return build_node_graph(edges, epsilon=epsilon)


    def _load(self):
        if not self.edges:
            self.result.errors.append("Modelspace vuoto: nessuna geometria trovata.")
            self.result.is_valid = False
            return

    def _structural(self, role) -> bool:
        """
        Un ruolo è strutturale (resta nel grafo, partecipa alla ricerca loop)
        secondo il predicato iniettato dal chiamante, se c'è — altrimenti solo
        outer/inner lo sono (`model.role.is_structural_role`, il minimo che il
        motore conosce da solo). Vedi `_is_structural_fn` in `__init__`.
        """
        from ..model.role import is_structural_role
        if self._is_structural_fn is not None:
            return self._is_structural_fn(role)
        return is_structural_role(role)

    def _merge_collinear_overlaps(self):
        """
        Fonde a monte di tutto il resto le rette tracciate a spezzoni
        sovrapposti (linetype esploso, ridisegno per errore, congiunzioni di
        quotatura quasi coincidenti col contorno) — vedi
        `normalizer.merge_collinear_overlaps`. Senza, ogni estremo interno di
        spezzone è un nodo spurio nel grafo topologico: il contorno vero non
        chiude più, a qualunque tolleranza (trovato su un disegno reale dove
        un trapezio con tre pieghe interne, tracciato a spezzoni, andava
        tutto in trash — non un gap, proprio nodi in più che non c'erano).
        """
        from .healing.normalizer import merge_collinear_overlaps
        merged = merge_collinear_overlaps(self.edges)
        n_merged = len(self.edges) - len(merged)
        if n_merged:
            self.result.warnings.append(
                f"{n_merged} segmenti collineari sovrapposti fusi prima della ricerca loop."
            )
        self.edges = merged

    def _merge_cocircular_overlaps(self):
        """
        Stesso motivo di `_merge_collinear_overlaps`, sugli archi: un arco
        tracciato a spezzoni che si toccano/sovrappongono (o due semicirchi
        che insieme fanno un foro pieno) sono nodi spuri nel grafo —
        `normalizer.merge_cocircular_overlaps`.
        """
        from .healing.normalizer import merge_cocircular_overlaps
        merged = merge_cocircular_overlaps(self.edges)
        n_merged = len(self.edges) - len(merged)
        if n_merged:
            self.result.warnings.append(
                f"{n_merged} archi co-circolari sovrapposti fusi prima della ricerca loop."
            )
        self.edges = merged

    def _weld_degenerate_linesegs(self):
        """
        Salda i LineSeg sotto 0.05mm in un nodo solo —
        `normalizer.weld_degenerate_linesegs` (MAP.md D56).
        """
        from .healing.normalizer import weld_degenerate_linesegs
        welded = weld_degenerate_linesegs(self.edges)
        n_welded = len(self.edges) - len(welded)
        if n_welded:
            self.result.warnings.append(
                f"{n_welded} LineSeg degeneri (sub-tolleranza) saldati prima della ricerca loop."
            )
        self.edges = welded

    def _split_labeled(self):
        """
        Estrae dal flusso topologico gli Edge il cui ruolo è già stato deciso
        (da label_map o da un consumatore) e non è strutturale per
        `self._structural` — marcatura, arredo del disegno, o un ruolo
        manifatturiero se nessuno ha iniettato il predicato che lo riconosce
        (vedi `_structural`).

        Questi non entrano nel grafo né nella ricerca loop — niente gap solving,
        niente riparazione angoli, niente detection dei non-contorno. L'unico
        calcolo che li riguarda è il contenimento, fatto da detect(): dentro un
        cluster → feature del cluster, fuori → trash, esattamente come ogni
        entità che non sta dentro un outer. La geometria non si perde: finisce
        in trash_entities col ruolo intatto e l'output la riscrive nativa.

        È il punto d'aggancio per un consumatore che marca la geometria PRIMA
        di heal (Framer: cornice / cartiglio) — vedi D30.
        """
        from .healing.steps import split_labeled
        self.edges, self.labeled_edges = split_labeled(self.edges, self._is_structural_fn)
        if self.labeled_edges:
            if self._is_structural_fn is None:
                self.result.warnings.append(
                    f"{len(self.labeled_edges)} edge con un ruolo diverso da "
                    "outer/inner/unknown, trattati come non strutturali di "
                    "default (heal() chiamato senza is_structural=...): un "
                    "ruolo manifatturiero come 'hole' non viene riconosciuto "
                    "come contorno di pezzo qui e finisce in trash. Passa "
                    "is_structural=tools.manufacturing_role.is_structural, o "
                    "chiama heal_and_detect() che lo fa automaticamente."
                )

    def _preprocess(self):
        from .healing.steps import close_free_gaps, dangling_splines
        self.edges = close_free_gaps(self.edges, self.tolerance)
        if dangling_splines(self.edges):
            self.result.warnings.append(
                "SPLINE con endpoint non connesso trovata — "
                "gap tra SPLINE e altre entità gestito con una linea di congiunzione. "
                "Verificare manualmente la correttezza del file."
            )


    def _find_non_contour_edges(self):
        from .healing.steps import find_non_contour_edges
        self.non_contour_edge_ids = find_non_contour_edges(self.edges, self.tolerance)

        if self.non_contour_edge_ids:
            self.result.warnings.append(
                f"{len(self.non_contour_edge_ids)} edge non di contorno "
                f"esclusi dal grafo (entrambi gli endpoint su nodi di branching)."
            )


    def _find_loops(self):
        from .healing.steps import (
            find_loops, structural_loops, loops_to_features,
            polygonize_edges, polygons_to_features,
        )
        search = find_loops(self.edges, self.non_contour_edge_ids, self.tolerance)
        self.edges = search.edges
        if search.repaired:
            self.result.all_arcs = [
                e.segment for e in self.edges if isinstance(e.segment, ArcSeg)
            ]
            self.result.warnings.append(
                f"{search.repaired} angoli chiusi all'intersezione reale dopo "
                f"detection via clustering (epsilon={self.tolerance})."
            )
        if search.method == "tolerant":
            self.result.warnings.append(
                "Loop trovati solo dopo clustering tollerante "
                f"(epsilon={self.tolerance}); angoli non riparati: "
                f"{search.unrepaired_corners[:8]}. La discrepanza sopravvive nell'output."
            )
        if not search.loops:
            if not self.edges:
                return
            if search.open_nodes:
                self.result.warnings.append(
                    f"Grafo con {len(search.open_nodes)} estremi liberi dopo "
                    f"clustering (prime coordinate: {search.open_nodes[:8]})."
                )
            self.result.warnings.append("Nessun loop trovato via grafo, uso polygonize come fallback.")
            polygons = polygonize_edges(self.edges, self.tolerance)
            if polygons:
                self.result.warnings.append(
                    f"Geometria ricostruita via fallback polygonize "
                    f"({len(polygons)} poligoni). Verificare il risultato."
                )
                self.closed_shapes.extend(polygons_to_features(polygons))
            else:
                self.result.warnings.append(
                    "LINE/ARC non formano loop chiusi — "
                    "potrebbero essere marcature o geometria aperta."
                )
            return

        kept = structural_loops(search.loops, self._structural)
        self.loop_edge_ids = {id(edge) for loop in kept for edge, _ in loop}
        self.closed_shapes.extend(loops_to_features(kept))

    def _build_hierarchy(self):
        from .topology.loop_finder import edges_to_open_features
        from .healing.hierarchy import HierarchyBuilder

        open_proxies = edges_to_open_features(
            self.edges,
            exclude_ids=self.loop_edge_ids,
            label_map=self.result.label_map,
        )

        all_proxies = self.closed_shapes + open_proxies

        if not all_proxies:
            self.result.errors.append("Nessuna geometria chiusa trovata dopo healing.")
            self.result.is_valid = False
            return

        builder = HierarchyBuilder(
            label=self.label,
            source_file=self.source_file,
            label_map=self.result.label_map,
            entities_in_loops=self.entities_in_loops,
            is_structural=self._structural,
        )

        clusters, trash = builder.build(all_proxies)

        self.result.clusters          = clusters
        self.result.trash_entities = trash + self._labeled_proxies()

        if not clusters:
            # La geometria non compone nessun contorno esterno chiuso: il
            # prolungamento dei segmenti (anche via ponte retto) non arriva a
            # un loop. Il risultato NON è un pezzo — è un file non lavorabile.
            # Va dichiarato invalido, come quando il modelspace è vuoto: la
            # trash resta popolata per la diagnostica, ma to_dxf() si rifiuta
            # di materializzare un output di sola spazzatura.
            self.result.errors.append(
                "Nessun contorno esterno chiuso: nessuna parte generabile dal file. "
                "Gli endpoint liberi non si congiungono entro la tolleranza richiesta."
            )
            self.result.is_valid = False

    def _labeled_proxies(self):
        """
        Converte gli Edge estratti da _split_labeled() in proxy (OpenFeature o,
        per tracce già degeneri come CIRCLE / SPLINE chiusa, ClosedFeature).

        Restano portatori del loro `role` autoritativo: detect() li smista per
        contenimento senza mai rimetterli in discussione.
        """
        from ..model.feature import OpenFeature, ClosedFeature
        from .primitives.polygon_builder import build_polygon
        from .primitives.segments import DEFAULT_TOLERANCE
        from .geometry import track_points

        proxies = []
        for edge in self.labeled_edges:
            seg = edge.segment
            if seg is None:
                continue

            if edge.start == edge.end:
                polygon = build_polygon([seg], DEFAULT_TOLERANCE)
                if polygon is None:
                    continue
                proxies.append(ClosedFeature(
                    role=edge.role,
                    polygon=polygon,
                    segments=[seg],
                    styles=[edge.style],
                ))
                continue

            if len(track_points([seg])) < 2:
                continue

            proxies.append(OpenFeature(role=edge.role, segments=[seg], styles=[edge.style]))

        return proxies


# ---------------------------------------------------------------------------
# Funzioni module-level
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def heal(doc: ForgeDocument, tolerance=None, label="", source_file="",
         is_structural=None) -> ForgeResult:
    """
    Esegue l'healing su un ForgeDocument prodotto da forge.load_dxf().

    tolerance: se None viene ripresa da doc.source_meta['tolerance']
               (quella usata per arrotondare i nodi in load_dxf).
    label_map: NON è un parametro — va passato a load_dxf(), che assegna
               i ruoli agli Edge in fase di traduzione.
    is_structural: predicato `Callable[[str], bool]` — "questo ruolo è
               topologia di contorno di pezzo?" — usato per decidere quali
               Edge già etichettati restano nel grafo prima della ricerca
               loop. Il motore da solo conosce solo outer/inner; passa
               `tools.manufacturing_role.is_structural` per riconoscere anche
               hole/countersink/threaded_hole (quello che fa
               `heal_and_detect()` automaticamente). Senza, un edge etichettato
               "hole" viene trattato come non strutturale e heal() lo segnala
               con un warning.
    """
    if not isinstance(doc, ForgeDocument):
        raise TypeError(
            "forge.heal() richiede un ForgeDocument da forge.load_dxf(); "
            f"ricevuto {type(doc).__name__}"
        )

    tol = tolerance if tolerance is not None else doc.source_meta.get("tolerance", 0.05)
    result = HealStep(doc, tol, label=label, source_file=source_file,
                       is_structural=is_structural).run()

    if result.is_valid and result.clusters:
        from ..rules.validator import validate_result
        validate_result(result)

    return result
