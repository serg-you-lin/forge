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
    è nata da due golden reali (`la_104`, `PROFILE_PART`) dove fondere
    esattamente 2 tratti — due caratteri di un'incisione allineati per caso,
    non un errore di disegno — sembrava aver rotto un pezzo vicino. Causa
    vera, trovata dopo: un bug di arrotondamento (sotto), non il numero di
    pezzi. Con quel bug corretto, fondere quelle stesse coppie non rompe più
    niente su nessun file della suite — l'unione di 2 intervalli è sempre
    corretta, il numero di pezzi non era mai stato la variabile giusta.

    Bug di arrotondamento (fisso, non riguarda "quanti pezzi"): il punto
    conservato come estremo del fuso dev'essere quello ARROTONDATO
    dell'Edge (`edge.start`/`edge.end` — l'identità del nodo nel grafo,
    l'adapter li produce arrotondando `segment_endpoints(segment)`, D18 /
    adapter.py `_append_edge`), non quello a piena precisione del segmento
    nativo. Su coordinate reali (mai numeri tondi) i due differiscono di una
    frazione di mm — un fuso costruito sulla precisione piena del segmento
    può non agganciarsi più esattamente al nodo del vicino reale (un ArcSeg
    che chiude l'angolo, un'altra LINE), e quel sub-mm di scarto spezza il
    contorno. La proiezione `_t` per ordinamento/sovrapposizione resta a
    piena precisione — è solo il punto conservato come estremo che dev'
    essere quello arrotondato.

    Esclusi a monte, mai candidati alla fusione:
      - segmenti non LineSeg (ARC/SPLINE non sono "collineari")
      - edge con `role` già diverso da UNKNOWN — un ruolo assegnato da
        label_map (bending/engrave/hole/...) è dato di dominio: quegli edge
        non entrano mai nel graph-building (`HealStep._split_labeled` li leva
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
    reale `PROFILE_PART`: una staffa di scarto a 3 lati duplicava
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
    `PROFILE_PART`, senza che una sola fusione fosse coinvolta.)
    """
    edges = list(edges)
    original_index = {id(e): i for i, e in enumerate(edges)}

    buckets: dict = {}
    for edge in edges:
        seg = edge.segment
        if not isinstance(seg, LineSeg) or edge.role != ContourRole.UNKNOWN:
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

        # Ogni span porta il punto ARROTONDATO dell'Edge (non quello a piena
        # precisione del segmento nativo) come estremo di lo/hi: è
        # `edge.start`/`edge.end` a essere l'identità del nodo nel grafo
        # (l'adapter arrotonda `segment_endpoints(segment)` per produrli, D18
        # / adapter.py `_append_edge`) — un fuso costruito sulla precisione
        # piena del segmento può risultare vicinissimo ma NON identico al
        # nodo del vicino reale (es. un ArcSeg che chiude l'angolo), e quel
        # sub-mm di scarto basta a spezzare l'aggancio. La proiezione `_t`
        # per l'ordinamento/sovrapposizione resta a piena precisione — è solo
        # il punto conservato come estremo che deve essere quello arrotondato.
        spans = []
        for e in group:
            t_start, t_end = _t(e.segment.start), _t(e.segment.end)
            if t_start <= t_end:
                spans.append((t_start, e.start, t_end, e.end, e))
            else:
                spans.append((t_end, e.end, t_start, e.start, e))
        spans.sort(key=lambda s: s[0])

        chains: List[list] = [[spans[0]]]
        cur_hi = spans[0][2]
        for span in spans[1:]:
            lo, hi = span[0], span[2]
            # Contatto (lo == cur_hi, due lati consecutivi di una polilinea
            # esplosa) O sovrapposizione vera (lo < cur_hi): in entrambi i
            # casi l'unione dei due intervalli è ben definita e corretta,
            # quindi in entrambi i casi si incatenano. `_CHAIN_GAP_EPS` è
            # solo rumore in virgola mobile (un contatto vero può risultare
            # `lo` di un pelo oltre `cur_hi` per errore di proiezione), non
            # una tolleranza geometrica dell'utente — un gap vero (i due
            # segmenti non si toccano affatto) resta fuori dalla catena.
            if lo <= cur_hi + _CHAIN_GAP_EPS:
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
    Una catena di 2+ span che si toccano/sovrappongono -> registra la
    fusione. Una catena di 1 (nessun altro membro tocca o si sovrappone)
    non fa nulla: non c'è niente da fondere.
    """
    if len(chain) < 2:
        return

    lo_start_pt = min(chain, key=lambda s: s[0])[1]
    hi_end_pt   = max(chain, key=lambda s: s[2])[3]

    members = [c[4] for c in chain]
    representative = min(members, key=lambda e: original_index[id(e)])

    merged_segment = LineSeg(start=lo_start_pt, end=hi_end_pt)
    # role/style del rappresentante (il primo membro in ordine di input, non
    # necessariamente il primo nella catena ordinata per t)
    replacement[id(representative)] = replace(
        representative, start=lo_start_pt, end=hi_end_pt, segment=merged_segment
    )
    for e in members:
        if e is not representative:
            drop.add(id(e))
