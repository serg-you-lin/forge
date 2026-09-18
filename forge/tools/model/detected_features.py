"""
tools/model/detected_features.py
---------------------------------
L'overlay di detect() — vocabolario aperto per nome, stessa mossa già fatta
per `role` in D27 (branch refactor/detect-overlay, MAP.md D44).

`ForgeCluster.detected` non ha più campi fissi (`holes`/`bending_lines`/
`engrave_lines`): è un `DetectedFeatures`, un contenitore che si scrive per
nome — `detect()` di forge e un tool esterno (un domani framer, bendly, o un
riconoscitore custom come "quante flange in su") usano lo stesso identico
meccanismo, nessuno dei due è privilegiato nello schema. `cluster.detected is
None` finché nessuno ci ha scritto: distingue "non ho ancora fatto detect" da
"ho fatto detect e non c'è nessuna feature" — l'ambiguità che i 3 campi fissi
di prima non permettevano di distinguere.

`DetectedFeature` è il contratto minimo che un valore attaccato dovrebbe
rispettare — non imposto a runtime (MAP.md D5: "convenzione, non gerarchia"),
solo dichiarato per chi vuole tipizzare. `Hole`/`BendingLine`/`Engraving`/
`ClassifiedEntity` lo soddisfano già così come sono.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Protocol, runtime_checkable


@runtime_checkable
class DetectedFeature(Protocol):
    """
    Contratto minimo di un elemento attaccato a `DetectedFeatures`: la stessa
    convenzione `source`/`confidence` che `Hole`/`BendingLine`/`Engraving`/
    `ClassifiedEntity` portano già (MAP.md D5). Un `Protocol`, non un `ABC`:
    un tipo custom lo soddisfa per forma, senza dover ereditare nulla di forge.
    """
    source: str
    confidence: float


@dataclass
class DetectedFeatures:
    """
    Contenitore aperto per nome. `detect()` scrive sotto `holes`/
    `bending_lines`/`engrave_lines`; chiunque altro scrive sotto il nome che
    vuole, con lo stesso metodo.
    """
    _store: Dict[str, List[Any]] = field(default_factory=dict)

    def attach(self, name: str, items: Iterable[Any]) -> None:
        """Sostituisce (o crea) la collezione `name` con `items`."""
        self._store[name] = list(items)

    def add(self, name: str, item: Any) -> None:
        """Aggiunge un elemento alla collezione `name`, creandola se manca."""
        self._store.setdefault(name, []).append(item)

    def get(self, name: str, default: List[Any] = None) -> List[Any]:
        """Collezione `name`, o `default` (`[]` se non specificato) se assente."""
        return self._store.get(name, [] if default is None else default)

    def items(self):
        """`(nome, collezione)` per ogni nome attaccato — per chi vuole iterare tutto."""
        return self._store.items()

    def names(self) -> List[str]:
        return list(self._store.keys())

    def __getattr__(self, name: str) -> List[Any]:
        # Scatta solo per attributi assenti: `_store` è un campo vero del
        # dataclass, mai in loop. `cluster.detected.holes`,
        # `cluster.detected.flange_view_hint` — stesso accesso per entrambi.
        store = self.__dict__.get("_store", {})
        try:
            return store[name]
        except KeyError:
            raise AttributeError(
                f"{name!r} non è stato attaccato a questo DetectedFeatures "
                f"(nomi presenti: {list(store)})"
            )

    def __repr__(self) -> str:
        counts = {k: len(v) for k, v in self._store.items()}
        return f"DetectedFeatures({counts})"
