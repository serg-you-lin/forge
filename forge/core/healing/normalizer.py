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

Funzioni pubbliche:
    find_duplicates          — dato un iterabile di (key, ref), i ref duplicati
    merge_collinear_overlaps — dato un iterabile di Edge, i gruppi da fondere
"""

from __future__ import annotations
import math
from dataclasses import replace
from typing import Any, Hashable, Iterable, List, Tuple

from ..primitives.segments import LineSeg
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
_OVERLAP_EPS     = 1e-6  # guardia da rumore in virgola mobile, non tolleranza utente
_MIN_CHAIN_TO_MERGE = 3  # sotto, la sovrapposizione può essere coincidenza (v. _merge_chain)


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
    Fonde gruppi di LineSeg collineari e sovrapposti in un solo Edge ciascuno.

    Una riga tracciata a spezzoni sovrapposti (linetype esploso, ridisegno
    per errore, congiunzione di quotatura) produce nodi spuri ad ogni
    estremo interno di spezzone — il grafo topologico li vede come angoli
    veri e non chiude il contorno. Qui si riconosce il pattern PRIMA che
    quei nodi esistano: stessa retta infinita (vedi `_line_key`) + intervalli
    che si sovrappongono per una lunghezza positiva lungo quella retta, a
    catena (il primo spezzone non deve sovrapporsi all'ultimo, basta una
    sequenza di sovrapposizioni intermedie — esattamente come un fascio di
    segmenti che insieme disegnano una riga sola) — e solo se la catena ha
    almeno `_MIN_CHAIN_TO_MERGE` (3) membri: vedi `_merge_chain` per perché
    una catena di 2 non basta.

    Il semplice contatto punta-coda (un segmento finisce esattamente dove
    inizia il successivo, sovrapposizione di lunghezza zero) NON basta e non
    va fuso: è la geometria normalissima di due lati consecutivi di una
    polilinea esplosa in LINE separate — un vertice vero, non una riga
    ridisegnata due volte. Confuso con l'overlap una volta (v. golden
    `fa_che_non_mi_incazzi`): un piccolo intaglio reale spariva perché i suoi
    due lati, collineari con l'edge esterno su cui si affacciano, venivano
    fusi dentro di esso.

    Esclusi a monte, mai candidati alla fusione:
      - segmenti non LineSeg (ARC/SPLINE non sono "collineari")
      - edge con `closed_path=True` — provengono da un anello già chiuso,
        contorno per definizione (stessa esclusione di NonContourEdgeDetector)
      - edge con `role` già diverso da UNKNOWN — un ruolo assegnato da
        label_map (bending/engrave/hole/...) è dato di dominio: quegli edge
        non entrano mai nel graph-building (`HealStep._split_labeled` li leva
        prima), quindi fonderli non aiuta a chiudere niente e rischia di
        alterare geometria intenzionale — trovato su un golden reale
        (`la_104`): due tratti di un'incisione/testo si sovrappongono per
        disegno (font vettoriale), non per errore, e fonderli cambiava la
        feature attesa

    Il segmento sostituto usa i due estremi reali più lontani lungo la retta
    (le proiezioni minima e massima) — mai un punto fabbricato — e conserva
    `style`/`closed_path` del primo edge del gruppo in ordine di input (lo
    stile può differire leggermente fra spezzoni, si tiene quello del primo;
    `role` è UNKNOWN per ogni membro per costruzione).

    Restituisce una nuova lista di Edge della STESSA lunghezza relativa e nel
    MEDESIMO ordine di input per tutto ciò che non fonde: un pre-pass di
    pulizia non deve riordinare edge che non tocca. Un gruppo fuso occupa la
    posizione del suo primo membro in ordine di input; gli altri membri del
    gruppo spariscono (assorbiti), il resto della lista resta tale e quale.
    (Trovato per necessità, non per eleganza: raggruppare-per-retta-poi-
    riconcatenare cambiava l'ordine anche a zero fusioni effettive, e quel
    solo riordino bastava a far scegliere al loop-finder un percorso diverso
    a un bivio — probabilmente paritario — in un golden reale,
    `PROFILE_PART`, senza che una sola fusione fosse coinvolta.)
    """
    edges = list(edges)
    original_index = {id(e): i for i, e in enumerate(edges)}

    buckets: dict = {}
    for edge in edges:
        seg = edge.segment
        if not isinstance(seg, LineSeg) or edge.closed_path or edge.role != ContourRole.UNKNOWN:
            continue
        buckets.setdefault(_line_key(seg.start, seg.end), []).append(edge)

    replacement: dict = {}  # id(rappresentante) -> Edge fuso
    drop: set = set()       # id(edge) assorbiti da una fusione

    for group in buckets.values():
        if len(group) < 2:
            continue

        # Direzione unitaria canonica del gruppo, presa dal primo edge —
        # coerente con `_line_key` (stessa retta = stessa direzione a meno
        # del verso). Ogni punto del gruppo si proietta su questa unica
        # retta di riferimento, quindi min/max fra edge diversi sono
        # confrontabili direttamente.
        s0, e0 = group[0].segment.start, group[0].segment.end
        ux, uy = e0[0] - s0[0], e0[1] - s0[1]
        length0 = math.hypot(ux, uy)
        ux, uy = (ux / length0, uy / length0) if length0 else (1.0, 0.0)
        if ux < 0 or (ux == 0 and uy < 0):
            ux, uy = -ux, -uy

        def _t(point, _ux=ux, _uy=uy, _origin=s0):
            return (point[0] - _origin[0]) * _ux + (point[1] - _origin[1]) * _uy

        # Ogni span porta già i punti reali (non solo i valori t) che
        # realizzano lo e hi, in modo che fondere non debba mai
        # ricalcolare/indovinare quale estremo dell'edge era quello giusto.
        spans = []
        for e in group:
            t_start, t_end = _t(e.segment.start), _t(e.segment.end)
            if t_start <= t_end:
                spans.append((t_start, e.segment.start, t_end, e.segment.end, e))
            else:
                spans.append((t_end, e.segment.end, t_start, e.segment.start, e))
        spans.sort(key=lambda s: s[0])

        chains: List[list] = [[spans[0]]]
        cur_hi = spans[0][2]
        for span in spans[1:]:
            lo, hi = span[0], span[2]
            # Sovrapposizione VERA (intervallo condiviso di lunghezza
            # positiva), non il semplice contatto punta-coda: due lati
            # consecutivi di una polilinea esplosa toccano allo stesso punto
            # (lo == cur_hi) ed è geometria legittima — un vertice reale, non
            # una riga ridisegnata due volte. `_OVERLAP_EPS` è solo rumore
            # in virgola mobile, non una tolleranza geometrica dell'utente.
            if lo < cur_hi - _OVERLAP_EPS:
                chains[-1].append(span)
                cur_hi = max(cur_hi, hi)
            else:
                chains.append([span])
                cur_hi = hi

        for chain in chains:
            _register_merge(chain, original_index, replacement, drop)

    result: List[Edge] = []
    for edge in edges:
        if id(edge) in drop:
            continue
        result.append(replacement.get(id(edge), edge))
    return result


def _register_merge(chain: List[tuple], original_index: dict, replacement: dict, drop: set) -> None:
    """
    Una catena di span sovrapposti -> registra la fusione, o non fa nulla se
    la catena è troppo corta per fidarsene.

    Una catena di 2 può capitare per coincidenza — due tratti indipendenti
    (spesso lettere/marcature disegnate a segmenti: cifre e lettere hanno
    aste verticali/orizzontali che si allineano per caso) che si sovrappongono
    senza essere la stessa riga ridisegnata. Trovato su un golden reale
    (`PROFILE_PART`): due aste di caratteri diversi, stessa x, si
    sovrappongono in y — fondendole si è distrutta la forma di entrambi i
    pezzi vicini. Tre o più segmenti indipendenti allineati e sovrapposti
    sulla stessa retta sono una coincidenza molto più rara: sotto quella
    soglia non si fonde, sopra sì.
    """
    if len(chain) < _MIN_CHAIN_TO_MERGE:
        return

    lo_start_pt = min(chain, key=lambda s: s[0])[1]
    hi_end_pt   = max(chain, key=lambda s: s[2])[3]

    members = [c[4] for c in chain]
    representative = min(members, key=lambda e: original_index[id(e)])

    merged_segment = LineSeg(start=lo_start_pt, end=hi_end_pt)
    # role/style/closed_path del rappresentante (il primo membro in ordine di
    # input, non necessariamente il primo nella catena ordinata per t)
    replacement[id(representative)] = replace(
        representative, start=lo_start_pt, end=hi_end_pt, segment=merged_segment
    )
    for e in members:
        if e is not representative:
            drop.add(id(e))
