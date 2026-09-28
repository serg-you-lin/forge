"""
forge/model/annotation.py
-------------------------
Le annotazioni come contenuto di dominio: forge le legge, le interpreta e le
riscrive. Un solo modello tipato per testi, quote e direttrici — ha sostituito
il vecchio ``Annotation(data=dict)`` e il separato ``ForgeText``.

Divisione dei compiti:
    - adapter (annotation_extractor / exporter) → read/write formato ↔ modello,
      solo conoscenza di formato (dove sta il testo, come si appiattisce il
      blocco di una quota).
    - fase di pipeline ``anchor_annotations()`` → collega l'annotazione alla
      geometria: popola ``cluster_ref`` (indice della parte che la contiene) e, in
      futuro, i riferimenti alle feature per quote e direttrici.
    - agente → legge e modifica questi oggetti (aggiunge una nota, cambia
      l'override di una quota, ri-punta un leader); ``write()`` li riemette.

``cluster_ref`` è l'indice in ``result.clusters`` (stessa convenzione dei file split
``__000``/``__001``), non un ``id()`` — così resta valido dopo serializzazione.
``Leader.target`` (percorso dell'elemento puntato, es. ``"clusters[0].inners[3]"``)
e ``Dimension.references`` (percorsi degli elementi quotati) li popola
``anchor_annotations()``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

Point = Tuple[float, float]

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass
class RenderedText:
    """Un testo dentro l'immagine appiattita di una quota/direttrice."""
    content:  str
    position: Point
    height:   float = 2.5
    rotation: float = 0.0


@dataclass
class RenderedGeometry:
    """
    Immagine di una quota/direttrice già appiattita in primitive pure.

    Serve all'output fedele: DIMENSION e LEADER non hanno una geometria propria
    nei campi DXF (sta in un blocco anonimo), quindi la conserviamo qui e
    ``write()`` la ri-materializza invece di piazzare un numero a caso.
    """
    strokes: List[List[Point]]  = field(default_factory=list)  # polilinee aperte
    fills:   List[List[Point]]  = field(default_factory=list)  # polilinee chiuse
    texts:   List[RenderedText] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.strokes and not self.fills and not self.texts


@dataclass
class Annotation:
    """
    Base di ogni annotazione. ``position`` è il punto d'ancoraggio XY — dove
    ``write()`` posiziona il testo e su cui gira il containment check.

    ``source_kind`` conserva il tipo entità nel formato sorgente
    ("TEXT" | "MTEXT" | "DIMENSION" | "LEADER" | "MULTILEADER"): guida la
    riscrittura e resta l'etichetta che i consumatori usano via ``kind``.

    ``width_factor`` è lo stretch orizzontale del testo rispetto alla sua
    altezza nominale (1.0 = nessuno) — concetto neutro, non specifico DXF: un
    domani un adapter PDF lo popolerebbe dalla propria matrice di testo,
    esattamente come l'adapter DXF lo legge dallo stile assegnato all'entità.
    Senza, un consumatore che riscrive il testo su uno stile generico perde la
    condensazione dell'originale e il testo sborda dalla sua cella (caso
    reale: cartigli SolidWorks, stile a 0.6, riscritti su "Standard" a 1.0).
    """
    position:    Point
    layer:       str           = "0"
    origin:      Optional[str]  = None   # provenienza nella sorgente — diagnostica
    cluster_ref:    Optional[int]  = None   # indice in result.clusters della parte che la contiene (fase anchor)
    source_kind: str            = ""
    width_factor: float         = 1.0

    @property
    def kind(self) -> str:
        """Tipo entità sorgente — etichetta stabile per i consumatori."""
        return self.source_kind

    @property
    def display_text(self) -> str:
        """Testo visualizzato dell'annotazione (vuoto se non ne ha)."""
        return ""


@dataclass
class Note(Annotation):
    """Testo libero: TEXT o MTEXT."""
    text:     str   = ""
    height:   float = 2.5
    rotation: float = 0.0

    @property
    def display_text(self) -> str:
        return self.text


@dataclass
class Dimension(Annotation):
    """
    Quota. Versione minimale: valore misurato + tipo + eventuale override del
    testo. Tolleranze e GD&T si aggiungono quando un caso reale li richiede.

    ``measured_points``: i punti sulla geometria fra cui la quota misura —
    lineare: i due estremi; diametro: due punti opposti sul cerchio; raggio:
    il punto sull'arco. ``text_override``: testo scritto dall'autore, ``<>`` =
    la misura.
    """
    measured_value:  Optional[float]  = None
    dim_type:        str              = "linear"  # linear|aligned|angular|diameter|radius|ordinate
    text_override:   Optional[str]    = None
    rendered:        RenderedGeometry = field(default_factory=RenderedGeometry)
    measured_points: List[Point]      = field(default_factory=list)
    references:      List[str]        = field(default_factory=list)  # percorsi degli elementi quotati (anchor_annotations, D69)

    @property
    def display_text(self) -> str:
        if self.text_override is not None:
            return self.text_override.replace("<>", self._shown_value())
        if self.rendered.texts:
            return "".join(t.content for t in self.rendered.texts)
        return self._shown_value()

    def _shown_value(self) -> str:
        """La misura come la mostra il disegno (precisione, virgola), o calcolata."""
        for t in self.rendered.texts:
            if _NUMBER.fullmatch(t.content.strip()):
                return t.content.strip()
        if self.measured_value is not None:
            return f"{self.measured_value:.2f}".rstrip("0").rstrip(".")
        return ""


@dataclass
class Leader(Annotation):
    """Direttrice con testo che punta a una feature."""
    text:     str              = ""
    vertices: List[Point]      = field(default_factory=list)
    target:   Optional[str]    = None   # elemento puntato da vertices[0], es. "clusters[0].inners[3]" (anchor_annotations, D66)
    rendered: RenderedGeometry = field(default_factory=RenderedGeometry)

    @property
    def display_text(self) -> str:
        return self.text or (self.rendered.texts[0].content if self.rendered.texts else "")
