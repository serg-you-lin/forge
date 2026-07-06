
"""
frame_detector.py — core/frame_detector.py

Rileva e filtra la cornice-cartiglio nei disegni tecnici impaginati.

Strategia:
    1. Trova tutti i rettangoli nel msp (LWPOLYLINE chiuse a 4 punti, o 4 LINE che si chiudono)
    2. Filtra quelli con ratio ≈ √2 (formati ISO)
    3. Tra i candidati, tieni solo quelli che "contengono" la maggior parte della geometria restante
    4. Prendi il più grande — quello è la cornice
    5. Conservativo: se non trova match convincente, non filtra niente

Non sa niente di DXF, PDF, SVG — quello è compito degli adapter.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence


# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

ISO_RATIO = math.sqrt(2)        # ≈ 1.41421
RATIO_TOLERANCE = 0.05          # ±5% sulla ratio
RECT_ANGLE_TOLERANCE = 5.0      # gradi — tolleranza per considerare un angolo retto
ENDPOINT_TOLERANCE_FACTOR = 0.005  # 0.5% del lato lungo per chiusura LINE
CONTAINMENT_THRESHOLD = 0.80    # almeno 80% della geometria deve stare dentro


# ---------------------------------------------------------------------------
# Strutture dati
# ---------------------------------------------------------------------------

@dataclass
class RawPoint:
    x: float
    y: float


@dataclass
class RawSegment:
    """
    Rappresentazione agnostica di un segmento geometrico.
    handle: identificatore opaco restituito dall'adapter
    points: lista di punti (2 per LINE, N per LWPOLYLINE)
    is_closed: True se la geometria è un loop chiuso
    """
    handle: str
    points: list[RawPoint]
    is_closed: bool = False


@dataclass
class BBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        return self.ymax - self.ymin

    @property
    def long_side(self) -> float:
        return max(self.width, self.height)

    @property
    def short_side(self) -> float:
        return min(self.width, self.height)

    @property
    def ratio(self) -> float:
        if self.short_side == 0:
            return 0.0
        return self.long_side / self.short_side

    @property
    def area(self) -> float:
        return self.width * self.height

    def contains_point(self, pt: RawPoint, margin: float = 0.0) -> bool:
        return (
            self.xmin - margin <= pt.x <= self.xmax + margin
            and self.ymin - margin <= pt.y <= self.ymax + margin
        )


@dataclass
class RectCandidate:
    """Un rettangolo candidato cornice con i suoi handle."""
    bbox: BBox
    handles: set[str]


@dataclass
class FrameDetectionResult:
    found: bool
    frame_bbox: BBox | None = None
    excluded_handles: set[str] = field(default_factory=set)
    containment: float = 0.0        # 0.0..1.0 — % geometria contenuta
    confidence: str = "none"        # "none" | "low" | "high"


# ---------------------------------------------------------------------------
# Rilevamento rettangoli
# ---------------------------------------------------------------------------

def _is_iso_ratio(bbox: BBox) -> bool:
    return abs(bbox.ratio - ISO_RATIO) <= RATIO_TOLERANCE


def _bbox_from_points(points: list[RawPoint]) -> BBox:
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return BBox(min(xs), min(ys), max(xs), max(ys))


def _is_rect_bbox(points: list[RawPoint], angle_tol: float) -> bool:
    """
    Verifica se una sequenza di 4 punti forma un rettangolo
    (angoli tutti ≈ 90°, lati paralleli agli assi o ruotati).
    Per semplicità accettiamo anche rettangoli axis-aligned puri:
    basta che le coordinate siano degeneri in due valori distinti per asse.
    """
    xs = sorted(set(round(p.x, 1) for p in points))
    ys = sorted(set(round(p.y, 1) for p in points))
    # rettangolo axis-aligned: esattamente 2 valori x e 2 valori y
    return len(xs) == 2 and len(ys) == 2


def _find_rect_candidates_lwpoly(segments: Sequence[RawSegment]) -> list[RectCandidate]:
    """LWPOLYLINE chiusa a 4 punti con ratio ISO."""
    candidates = []
    for seg in segments:
        if not seg.is_closed:
            continue
        pts = seg.points
        # 4 punti (o 5 se il primo è ripetuto alla fine)
        unique_pts = pts[:-1] if (len(pts) == 5 and
            abs(pts[0].x - pts[-1].x) < 1e-6 and
            abs(pts[0].y - pts[-1].y) < 1e-6) else pts
        if len(unique_pts) != 4:
            continue
        if not _is_rect_bbox(unique_pts, RECT_ANGLE_TOLERANCE):
            continue
        bbox = _bbox_from_points(unique_pts)
        if not _is_iso_ratio(bbox):
            continue
        candidates.append(RectCandidate(bbox=bbox, handles={seg.handle}))
    return candidates


def _pts_close(a: RawPoint, b: RawPoint, tol: float) -> bool:
    return math.hypot(a.x - b.x, a.y - b.y) <= tol


def _find_rect_candidates_lines(segments: Sequence[RawSegment]) -> list[RectCandidate]:
    """
    Gruppi di 4 LINE axis-aligned che si chiudono a formare un rettangolo ISO.
    Strategia: cerca 4 LINE i cui endpoint si toccano e formano un rettangolo.
    """
    lines = [s for s in segments if not s.is_closed and len(s.points) == 2]
    if len(lines) < 4:
        return []

    # stima tolleranza dal lato lungo medio delle line più grandi
    lengths = [math.hypot(s.points[1].x - s.points[0].x,
                          s.points[1].y - s.points[0].y) for s in lines]
    max_len = max(lengths) if lengths else 1.0
    tol = max_len * ENDPOINT_TOLERANCE_FACTOR

    # raggruppa per endpoint — cerca quadruplet che formano rettangolo chiuso
    # approccio semplificato: raccogli tutti i punti estremi e cerca cluster
    # che formano 4 angoli di un rettangolo
    candidates = []
    paired = sorted(zip(lengths, lines), key=lambda x: x[0], reverse=True)
    lines = [l for _, l in paired[:20]]
    n = len(lines)

    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                for l in range(k + 1, n):
                    quad = [lines[i], lines[j], lines[k], lines[l]]
                    all_pts = [p for s in quad for p in s.points]
                    # deve formare un rettangolo axis-aligned
                    xs = sorted(set(round(p.x, 0) for p in all_pts))
                    ys = sorted(set(round(p.y, 0) for p in all_pts))
                    if len(xs) != 2 or len(ys) != 2:
                        continue
                    bbox = BBox(min(xs), min(ys), max(xs), max(ys))
                    if not _is_iso_ratio(bbox):
                        continue
                    handles = {s.handle for s in quad}
                    candidates.append(RectCandidate(bbox=bbox, handles=handles))

    return candidates


# ---------------------------------------------------------------------------
# Check di contenimento
# ---------------------------------------------------------------------------

def _compute_containment(
    candidate: RectCandidate,
    all_segments: Sequence[RawSegment],
    margin_factor: float = 0.02,
) -> float:
    """
    Calcola la frazione di segmenti (esclusi quelli del candidato)
    i cui punti stanno tutti dentro la bbox del candidato.
    """
    margin = candidate.bbox.short_side * margin_factor
    other = [s for s in all_segments if s.handle not in candidate.handles]

    if not other:
        return 0.0

    inside = sum(
        1 for s in other
        if all(candidate.bbox.contains_point(p, margin) for p in s.points)
    )
    return inside / len(other)


# ---------------------------------------------------------------------------
# Entry point pubblico
# ---------------------------------------------------------------------------

def detect_frame(
    segments: Sequence[RawSegment],
    ratio_tolerance: float = RATIO_TOLERANCE,
    containment_threshold: float = CONTAINMENT_THRESHOLD,
) -> FrameDetectionResult:
    """
    Rileva la cornice-cartiglio nell'insieme di segmenti fornito.

    Args:
        segments: geometria grezza estratta dall'adapter
        ratio_tolerance: tolleranza sulla ratio ISO (default ±5%)
        containment_threshold: % minima di geometria contenuta per confermare

    Returns:
        FrameDetectionResult con gli handle da escludere (vuoto se non trovata)
    """
    if not segments:
        return FrameDetectionResult(found=False)

    # Trova candidati rettangoli ISO
    candidates: list[RectCandidate] = []
    candidates += _find_rect_candidates_lwpoly(segments)
    candidates += _find_rect_candidates_lines(segments)

    print(f"DEBUG segmenti totali: {len(segments)}")
    print(f"DEBUG candidati trovati: {len(candidates)}")

    if not candidates:
        return FrameDetectionResult(found=False)

    # Per ogni candidato calcola il containment
    scored = [
        (c, _compute_containment(c, segments))
        for c in candidates
    ]

    # Filtra per soglia e ordina per area (più grande prima)
    valid = [(c, score) for c, score in scored if score >= containment_threshold]

    if not valid:
        # nessun candidato supera la soglia — conservativo
        best_c, best_score = max(scored, key=lambda x: x[1])
        return FrameDetectionResult(
            found=False,
            frame_bbox=best_c.bbox,
            containment=best_score,
            confidence="low",
        )

    largest_c, largest_score = max(valid, key=lambda x: x[0].bbox.area)
    max_area = largest_c.bbox.area

    AREA_THRESHOLD = 0.50
    all_handles: set[str] = set()
    for c, score in valid:
        if c.bbox.area >= max_area * AREA_THRESHOLD:
            all_handles |= c.handles

    return FrameDetectionResult(
        found=True,
        frame_bbox=largest_c.bbox,
        excluded_handles=all_handles,
        containment=largest_score,
        confidence="high",
    )