"""
core/healing/normalizer.py
---------------------------
Normalizzazione geometrica format-agnostic.

Zero dipendenze da ezdxf, PDF, SVG o qualsiasi formato.

Due normalizzazioni distinte, entrambe sotto "due entità non dovrebbero
contare come due":
    find_duplicates       — uguaglianza esatta di chiave opaca (l'adapter
                             decide come calcolare la chiave dal formato
                             nativo). Colpisce solo la copia identica.
    merge_collinear_overlaps — sovrapposizione geometrica reale: due o più
                             LineSeg sulla stessa retta infinita che si
                             coprono almeno in parte (anche a catena — il
                             primo non deve toccare l'ultimo, basta una
                             sequenza di sovrapposizioni intermedie) sono la
                             stessa riga tracciata più volte a spezzoni.
                             Lavora su `Edge` (già format-agnostic, D18),
                             non su chiavi opache: deve calcolare proiezioni
                             reali per produrre il segmento unico che
                             sostituisce il gruppo, non solo confrontare due
                             valori.

merge_cocircular_overlaps — stesso principio, sugli ArcSeg co-circolari
                             invece dei LineSeg collineari (v. MAP.md D52).

weld_degenerate_linesegs — non sovrapposizione ma degenerazione: un LineSeg
                             più corto di 0.05mm è solo rumore nel grafo,
                             i suoi due estremi vengono saldati in un nodo
                             (v. MAP.md D56).

refit_tessellations      — una catena di tanti LineSeg corti è una curva scritta
                             a punti: rifittata come arco/cerchio/spline
                             (fitting.simplify_points).

Funzioni pubbliche:
    find_duplicates           — dato un iterabile di (key, ref), i ref duplicati
    merge_collinear_overlaps  — dato un iterabile di Edge, i gruppi LineSeg da fondere
    merge_cocircular_overlaps — dato un iterabile di Edge, i gruppi ArcSeg da fondere
    weld_degenerate_linesegs  — dato un iterabile di Edge, i LineSeg degeneri da saldare
    refit_tessellations       — dato un iterabile di Edge, le catene tassellate rifittate
"""

from __future__ import annotations
import math
from dataclasses import dataclass, replace
from typing import Any, Callable, Hashable, Iterable, List, Tuple

from ..primitives.segments import LineSeg, ArcSeg, CircleSeg, Point, segment_endpoints
from ..primitives.fitting import simplify_points
from ..topology.graph import build_node_graph
from ..topology.edge import Edge
from ...model.role import ContourRole


def find_duplicates(
    keyed_entities: Iterable[Tuple[Hashable, Any]],
) -> List[Any]:
    """
    Restituisce i ref delle entità duplicate (seconda occorrenza in poi).

    Parametri:
        keyed_entities : iterabile di (key, ref) — l'adapter produce le chiavi,
                         ref è opaco (l'adapter sa come eliminarlo)

    Restituisce:
        Lista di ref da eliminare. L'ordine riflette l'ordine di input.
    """
    seen:      set       = set()
    to_delete: List[Any] = []

    for key, ref in keyed_entities:
        if key is None:
            continue
        if key in seen:
            to_delete.append(ref)
        else:
            seen.add(key)

    return to_delete


# ---------------------------------------------------------------------------
# merge_collinear_overlaps
# ---------------------------------------------------------------------------

_ANGLE_DECIMALS  = 7  # direzione: quasi-esatta per costruzione, non tollerante
_OFFSET_DECIMALS = 3  # 0.001mm — "stessa retta", non "retta vicina"
_CHAIN_GAP_EPS   = 1e-6  # guardia da rumore in virgola mobile, non tolleranza utente


def _line_key(p1, p2) -> Tuple[float, float]:
    """
    Chiave della retta infinita per p1->p2: (angolo canonico, offset).

    L'angolo è canonico in [0, pi) — una retta e il suo verso opposto sono la
    stessa retta. L'offset è la distanza con segno dall'origine lungo la
    normale, arrotondata a una precisione FISSA (`_OFFSET_DECIMALS`) — non
    alla tolleranza di heal del chiamante: "sono la stessa retta" è una
    domanda di precisione geometrica (rumore in virgola mobile fra spezzoni
    nati identici), non "sono abbastanza vicine da chiudere un gap". Usare
    la tolleranza di heal qui (provato, poi tolto) arrotonda troppo grossolano
    a tolleranze larghe (es. 0.5 -> offset all'intero) e fonde rette parallele
    ma **reali e distinte** — un pattern di denti/asole a 0.5mm l'una
    dall'altra è scomparso così in un golden reale (`fa_che_non_mi_incazzi`).
    """
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    if dx < 0 or (dx == 0 and dy < 0):
        dx, dy = -dx, -dy
    length = math.hypot(dx, dy)
    if length == 0:
        return (0.0, 0.0)
    ux, uy = dx / length, dy / length
    angle  = round(math.atan2(uy, ux), _ANGLE_DECIMALS)
    offset = ux * p1[1] - uy * p1[0]  # distanza con segno origine-retta
    return (angle, round(offset, _OFFSET_DECIMALS))


def merge_collinear_overlaps(edges: Iterable[Edge]) -> List[Edge]:
    """
    Fonde gruppi di LineSeg collineari (stessa retta infinita, `_line_key`)
    che si toccano o si sovrappongono in un solo Edge ciascuno — a catena: il
    primo membro non deve toccare/sovrapporsi all'ultimo, basta una sequenza
    di contatti/sovrapposizioni intermedi, esattamente come un fascio di
    segmenti che insieme disegnano una riga sola. Bastano 2 membri: l'unione
    di due intervalli 1D che si toccano o si sovrappongono è sempre e
    comunque ben definita (il segmento più lungo, se uno contiene l'altro;
    l'estensione totale, altrimenti) — non c'è modo di "sbagliare" a fondere
    solo 2 pezzi collineari, la domanda semmai è se DEVONO restare due
    feature distinte a valle (v. sotto).

    Storia della soglia minima che c'era qui prima (rimossa): un'ipotesi di
    "servono almeno 3 pezzi indipendenti, una coppia può essere coincidenza"
    è nata da due golden reali (`la_104`, `staffa_scarto_doppia`) dove fondere
    esattamente 2 tratti — due caratteri di un'incisione allineati per caso,
    non un errore di disegno — sembrava aver rotto un pezzo vicino. Causa
    vera, trovata dopo: un bug di arrotondamento (sotto), non il numero di
    pezzi. Con quel bug corretto, fondere quelle stesse coppie non rompe più
    niente su nessun file della suite — l'unione di 2 intervalli è sempre
    corretta, il numero di pezzi non era mai stato la variabile giusta.

    Due estremi, due scopi, mai mischiati (stesso principio già in
    `gap_solver.apply_gap_fixes`: "il segmento conserva il punto reale, solo
    il nodo topologico dell'Edge viene arrotondato"): `Edge.start`/`Edge.end`
    del fuso portano il punto ARROTONDATO (l'identità del nodo nel grafo,
    l'adapter li produce arrotondando `segment_endpoints(segment)`, D18 /
    adapter.py `_append_edge`) — quello serve a riagganciarsi esattamente al
    nodo del vicino reale (un ArcSeg che chiude l'angolo, un'altra LINE): un
    fuso il cui Edge.start/end fosse a piena precisione del segmento nativo
    può risultare vicinissimo ma non identico a quel nodo, e il sub-mm di
    scarto spezza il contorno. Il `LineSeg` fuso (`edge.segment`), invece,
    porta SEMPRE il punto reale a piena precisione — mai quello arrotondato:
    è quello che l'export legge per costruire la geometria in output (area,
    lunghezza, poligono scritto), e un fuso il cui segmento porta il punto
    arrotondato produce, appena affianca nello stesso contorno un lato
    nativo mai toccato dal merge, uno scalino visibile nel punto che
    dovrebbe essere lo stesso angolo — due fonti di verità diverse cucite
    insieme (trovato su un caso reale: un lato "verticale" con dx=0.031
    invece di 0, lunghezza 0.97 invece di 1). La proiezione `_t` per
    ordinamento/sovrapposizione resta a piena precisione in entrambi i casi.

    Esclusi a monte, mai candidati alla fusione:
      - segmenti non LineSeg (ARC/SPLINE non sono "collineari")
      - edge con `role` già diverso da UNKNOWN — un ruolo assegnato da
        role_rules (bending/engrave/hole/...) è dato di dominio: quegli edge
        non entrano mai nel graph-building (`steps.split_labeled` li leva
        prima), quindi fonderli non aiuta a chiudere niente e rischia di
        alterare geometria intenzionale — trovato su un golden reale
        (`la_104`): due tratti di un'incisione/testo si sovrappongono per
        disegno (font vettoriale), non per errore, e fonderli cambiava la
        feature attesa

    Niente qui guarda da dove viene l'edge nel formato sorgente (una
    polilinea già chiusa contro linee sciolte, un layer, un tipo di
    entità): una versione precedente escludeva gli edge di un percorso già
    chiuso per analogia con `NonContourEdgeDetector` (dove un'esclusione
    simile ha un significato diverso: un edge di un anello chiuso non può
    ANCHE essere una piega che lo attraversa), ma qui non proteggeva niente
    di reale — un lato vero disegnato come polilinea e un doppione
    disegnato come LINE sciolte sono la stessa identica situazione di
    qualunque altra coppia, e l'esclusione impediva di vederlo (golden
    reale `staffa_scarto_doppia`: una staffa di scarto a 3 lati duplicava
    esattamente un lato di una polilinea chiusa). Rimossa: `Edge` non porta
    più quel dato, per lo stesso motivo (MAP.md, seguito D50).

    Il segmento sostituto usa i due estremi reali più lontani lungo la retta
    (le proiezioni minima e massima) — mai un punto fabbricato — e conserva
    `style` del primo edge del gruppo in ordine di input (lo stile può
    differire leggermente fra spezzoni, si tiene quello del primo; `role` è
    UNKNOWN per ogni membro per costruzione).

    Restituisce una nuova lista di Edge della STESSA lunghezza relativa e nel
    MEDESIMO ordine di input per tutto ciò che non fonde: un pre-pass di
    pulizia non deve riordinare edge che non tocca. Un gruppo fuso occupa la
    posizione del suo primo membro in ordine di input; gli altri membri del
    gruppo spariscono (assorbiti), il resto della lista resta tale e quale.
    (Trovato per necessità, non per eleganza: raggruppare-per-retta-poi-
    riconcatenare cambiava l'ordine anche a zero fusioni effettive, e quel
    solo riordino bastava a far scegliere al loop-finder un percorso diverso
    a un bivio — probabilmente paritario — in un golden reale,
    `staffa_scarto_doppia`, senza che una sola fusione fosse coinvolta.)
    """
    return _merge_on_carrier(edges, LineSeg, lambda seg: _line_key(seg.start, seg.end),
                             _line_spans, _merged_line)


def _line_spans(group: List[Edge]) -> List[_Span]:
    """Span lungo la retta comune: `t` è la proiezione sulla direzione del
    primo edge, canonica come in `_line_key`, quindi confrontabile fra edge."""
    s0, e0 = group[0].segment.start, group[0].segment.end
    ux, uy = e0[0] - s0[0], e0[1] - s0[1]
    length0 = math.hypot(ux, uy)
    ux, uy = (ux / length0, uy / length0) if length0 else (1.0, 0.0)
    if ux < 0 or (ux == 0 and uy < 0):
        ux, uy = -ux, -uy

    def _t(point):
        return (point[0] - s0[0]) * ux + (point[1] - s0[1]) * uy

    spans = []
    for e in group:
        seg = e.segment
        t_start, t_end = _t(seg.start), _t(seg.end)
        if t_start <= t_end:
            spans.append(_Span(t_start, e.start, t_end, e.end, e, (seg.start, seg.end)))
        else:
            spans.append(_Span(t_end, e.end, t_start, e.start, e, (seg.end, seg.start)))
    return _chain(spans)


def _merged_line(lo: _Span, hi: _Span):
    """Il fuso di una catena collineare: nodi arrotondati, segmento a piena
    precisione (v. docstring di `merge_collinear_overlaps`)."""
    return lo.lo_node, hi.hi_node, LineSeg(start=lo.extra[0], end=hi.extra[1])


# ---------------------------------------------------------------------------
# Motore comune: unione di intervalli 1D su un supporto (retta o cerchio)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Span:
    """
    Un edge come intervallo [lo, hi] sul suo supporto (posizione lungo la
    retta, o angolo sul cerchio). `lo_node`/`hi_node` sono gli estremi
    arrotondati dell'Edge — l'identità del nodo nel grafo, che il fuso riusa
    per riagganciarsi al vicino; `extra` è ciò che serve al chiamante per
    costruire il segmento fuso a piena precisione.
    """
    lo:      float
    lo_node: Point
    hi:      float
    hi_node: Point
    edge:    Edge
    extra:   Any


def _chain(spans: List[_Span]) -> List[List[_Span]]:
    """
    Ordina per `lo` e incatena gli span che si toccano o si sovrappongono:
    l'unione di intervalli 1D che si toccano è sempre ben definita.
    `_CHAIN_GAP_EPS` è rumore in virgola mobile, non una tolleranza: un gap
    vero resta fuori dalla catena.
    """
    spans = sorted(spans, key=lambda s: s.lo)
    chains: List[List[_Span]] = [[spans[0]]]
    cur_hi = spans[0].hi
    for span in spans[1:]:
        if span.lo <= cur_hi + _CHAIN_GAP_EPS:
            chains[-1].append(span)
            cur_hi = max(cur_hi, span.hi)
        else:
            chains.append([span])
            cur_hi = span.hi
    return chains


def _merge_on_carrier(
    edges: Iterable[Edge],
    segment_type: type,
    key: Callable[[Any], Hashable],
    chains_of: Callable[[List[Edge]], List[List[_Span]]],
    merged: Callable[[_Span, _Span], Tuple[Point, Point, Any]],
) -> List[Edge]:
    """
    Raggruppa per supporto (`key`) gli edge di `segment_type` con ruolo
    UNKNOWN, divide ogni gruppo in catene (`chains_of`) e sostituisce ogni
    catena di 2+ con un Edge solo: (start, end, segmento) da `merged(lo, hi)`,
    role/style del membro che viene prima in input. Il resto della lista
    resta nell'ordine di input.
    """
    edges = list(edges)
    original_index = {id(e): i for i, e in enumerate(edges)}

    buckets: dict = {}
    for edge in edges:
        seg = edge.segment
        if not isinstance(seg, segment_type) or edge.role != ContourRole.UNKNOWN:
            continue
        buckets.setdefault(key(seg), []).append(edge)

    replacement: dict = {}  # id(rappresentante) -> Edge fuso
    drop: set = set()       # id(edge) assorbiti da una fusione
    for group in buckets.values():
        if len(group) < 2:
            continue
        for chain in chains_of(group):
            if len(chain) < 2:
                continue
            lo = min(chain, key=lambda s: s.lo)
            hi = max(chain, key=lambda s: s.hi)
            start, end, segment = merged(lo, hi)
            members = [s.edge for s in chain]
            representative = min(members, key=lambda e: original_index[id(e)])
            replacement[id(representative)] = replace(
                representative, start=start, end=end, segment=segment)
            drop.update(id(e) for e in members if e is not representative)

    return [replacement.get(id(e), e) for e in edges if id(e) not in drop]


# ---------------------------------------------------------------------------
# merge_cocircular_overlaps
# ---------------------------------------------------------------------------

_TWO_PI = 2.0 * math.pi


def _arc_key(center, radius) -> Tuple[float, float, float]:
    """Chiave del cerchio (centro+raggio) a precisione fissa — v. `_line_key`."""
    return (
        round(center[0], _OFFSET_DECIMALS),
        round(center[1], _OFFSET_DECIMALS),
        round(radius, _OFFSET_DECIMALS),
    )


def merge_cocircular_overlaps(edges: Iterable[Edge]) -> List[Edge]:
    """
    `merge_collinear_overlaps` per gli ArcSeg: fonde gruppi co-circolari
    (stesso centro+raggio, `_arc_key`) che si toccano/sovrappongono
    angolarmente in un solo Edge ciascuno, incatenando a catena sul dominio
    circolare [0, 2*pi) (srotolando oltre il taglio 0/2*pi quando serve).
    Se la copertura totale chiude un giro intero, il fuso ha
    Edge.start == Edge.end (loop degenere, v. MAP.md D52).

    Stesse regole di `merge_collinear_overlaps`: esclude segmenti non ArcSeg
    e `role != UNKNOWN`; usa `edge.start`/`edge.end` (arrotondati) come
    estremi conservati, mai il punto ricalcolato a piena precisione;
    preserva l'ordine di input per tutto ciò che non fonde.
    """
    return _merge_on_carrier(edges, ArcSeg, lambda seg: _arc_key(seg.center, seg.radius),
                             _arc_chains, _merged_arc)


def _arc_chains(group: List[Edge]) -> List[List[_Span]]:
    """
    Catene angolari di un gruppo sullo stesso cerchio. Se l'ultima catena
    chiude il giro nella prima, le unisce: la prima viene srotolata di +2*pi
    (solo l'angolo usato per ordinare; i nodi restano quelli reali).
    """
    spans = []
    for e in group:
        seg = e.segment
        if seg.ccw:
            lo, lo_node, hi_node = seg.start_angle % _TWO_PI, e.start, e.end
        else:
            lo, lo_node, hi_node = seg.end_angle % _TWO_PI, e.end, e.start
        spans.append(_Span(lo, lo_node, lo + seg._sweep(), hi_node, e, (seg.center, seg.radius)))
    chains = _chain(spans)

    if len(chains) > 1:
        first_lo = chains[0][0].lo
        last_hi = max(s.hi for s in chains[-1])
        if last_hi >= first_lo + _TWO_PI - _CHAIN_GAP_EPS:
            shifted = [replace(s, lo=s.lo + _TWO_PI, hi=s.hi + _TWO_PI) for s in chains[0]]
            chains[-1] = chains[-1] + shifted
            chains.pop(0)
    return chains


def _merged_arc(lo: _Span, hi: _Span):
    """Il fuso di una catena cocircolare: un arco, o un cerchio se chiude il
    giro — stesso primitivo di un CIRCLE nativo, nessuna traccia di quale
    frammento fosse il primo."""
    center, radius = lo.extra
    if hi.hi - lo.lo >= _TWO_PI - _CHAIN_GAP_EPS:
        circle = CircleSeg(center=center, radius=radius)
        point = segment_endpoints(circle)[0]
        return point, point, circle
    arc = ArcSeg(center=center, radius=radius, start_angle=lo.lo, end_angle=hi.hi, ccw=True)
    return lo.lo_node, hi.hi_node, arc


# ---------------------------------------------------------------------------
# weld_degenerate_linesegs
# ---------------------------------------------------------------------------

_DEGENERATE_LENGTH_EPS = 0.05  # mm — fisso, non la tolerance del chiamante (v. MAP.md D56)


def weld_degenerate_linesegs(edges: Iterable[Edge]) -> List[Edge]:
    """
    Salda (non cancella) i LineSeg `role == UNKNOWN` di lunghezza reale
    sotto `_DEGENERATE_LENGTH_EPS`: l'Edge sparisce, i suoi due nodi
    diventano uno e ogni altro Edge che li toccava viene rimappato lì — la
    catena resta connessa. Solo i nodi (Edge.start/end) si spostano, il
    `segment` conserva il punto reale. Ordine di input preservato.
    """
    edges = list(edges)
    parent: dict = {}

    def find(p):
        root = p
        while parent.get(root, root) != root:
            root = parent[root]
        while parent.get(p, p) != root:
            parent[p], p = root, parent.get(p, p)
        return root

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    degenerate_ids: set = set()
    for edge in edges:
        seg = edge.segment
        if isinstance(seg, LineSeg) and edge.role == ContourRole.UNKNOWN:
            dx = seg.end[0] - seg.start[0]
            dy = seg.end[1] - seg.start[1]
            if math.hypot(dx, dy) < _DEGENERATE_LENGTH_EPS:
                union(edge.start, edge.end)
                degenerate_ids.add(id(edge))

    if not degenerate_ids:
        return edges

    result: List[Edge] = []
    for edge in edges:
        if id(edge) in degenerate_ids:
            continue
        new_start, new_end = find(edge.start), find(edge.end)
        if new_start != edge.start or new_end != edge.end:
            edge = replace(edge, start=new_start, end=new_end)
        result.append(edge)
    return result


# ---------------------------------------------------------------------------
# refit_tessellations
# ---------------------------------------------------------------------------

def refit_tessellations(
    edges: Iterable[Edge],
    max_segment: float = 0.1,
    min_run: int = 10,
    arc_fit_tolerance: float = 0.02,
    node_decimals: int = 3,
) -> List[Edge]:
    """
    Una catena di almeno `min_run` LineSeg (`role == UNKNOWN`) più corti di
    `max_segment`, collegati uno dopo l'altro, è una curva scritta a punti:
    diventa le primitive di `simplify_points` (arco/cerchio entro
    `arc_fit_tolerance`, se no spline). Gli estremi della catena tengono i
    nodi originali, così resta attaccata ai vicini. Il resto non si tocca.
    """
    edges = list(edges)
    short = [e for e in edges
             if isinstance(e.segment, LineSeg) and e.role == ContourRole.UNKNOWN
             and e.start != e.end
             and math.dist(e.segment.start, e.segment.end) < max_segment]
    replaced, new_edges = set(), []
    for path, closed in _short_runs(short):
        if len(path) < min_run:
            continue
        pts = []
        for edge, rev in path:
            a, b = (edge.segment.end, edge.segment.start) if rev else (edge.segment.start, edge.segment.end)
            if not pts:
                pts.append(a)
            pts.append(b)
        if closed:
            pts = pts[:-1]
        prims = simplify_points(pts, closed=closed, arc_fit_tolerance=arc_fit_tolerance)
        if not prims:
            continue
        first, last = path[0], path[-1]
        start_node = first[0].end if first[1] else first[0].start
        end_node = last[0].start if last[1] else last[0].end
        for k, prim in enumerate(prims):
            s, e = segment_endpoints(prim)
            edge = replace(first[0], segment=prim,
                           start=(round(s[0], node_decimals), round(s[1], node_decimals)),
                           end=(round(e[0], node_decimals), round(e[1], node_decimals)))
            if not closed:
                edge = replace(edge, start=start_node if k == 0 else edge.start,
                               end=end_node if k == len(prims) - 1 else edge.end)
            new_edges.append(edge)
        replaced |= {id(edge) for edge, _ in path}
    if not replaced:
        return edges
    return [e for e in edges if id(e) not in replaced] + new_edges


def _short_runs(short_edges: List[Edge]) -> list:
    """Catene massimali: percorsi fra nodi di grado != 2, o anelli.
    [( [(edge, percorso_al_contrario)], chiusa )]."""
    graph = build_node_graph(short_edges)
    used: set = set()
    runs = []

    def walk(start, first_edge, first_other):
        path, node, edge, other = [], start, first_edge, first_other
        while True:
            used.add(id(edge))
            path.append((edge, graph.canonical(edge.start) != node))
            node = other
            nxt = [(e, o) for e, o in graph[node] if id(e) not in used]
            if len(graph[node]) != 2 or not nxt:
                return path, node
            edge, other = nxt[0]

    for n in [n for n in graph if len(graph[n]) != 2]:
        for e, o in graph[n]:
            if id(e) not in used:
                path, _ = walk(n, e, o)
                runs.append((path, False))
    for n in graph:
        for e, o in graph[n]:
            if id(e) not in used:
                path, last = walk(n, e, o)
                runs.append((path, last == n))
    return runs
