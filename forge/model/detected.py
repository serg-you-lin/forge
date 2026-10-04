"""
forge/model/detected.py
-----------------------
L'overlay aperto di un cluster (MAP.md D44): `ForgeCluster.detected` è un
`DetectedFeatures`, un contenitore che si scrive per nome. forge non ci scrive
niente: lo riempie un consumatore (snapbend: fori, pieghe, incisioni; snapdraw;
un riconoscitore custom), tutti con lo stesso meccanismo. `cluster.detected is
None` finché nessuno ci ha scritto.

`DetectedFeature` è il contratto minimo dichiarato per chi vuole tipizzare —
non imposto a runtime (MAP.md D5: "convenzione, non gerarchia"). I renderer
leggono di ogni elemento solo `role` e la geometria (`contours`, oppure
`segments` + `polygon`) — MAP.md D90.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Protocol, runtime_checkable


@runtime_checkable
class DetectedFeature(Protocol):
    """
    Contratto minimo di un elemento attaccato a `DetectedFeatures`: la
    convenzione `source`/`confidence` (MAP.md D5). Un `Protocol`, non un
    `ABC`: un tipo custom lo soddisfa per forma, senza ereditare nulla.
    """
    source: str
    confidence: float


@dataclass
class DetectedFeatures:
    """
    Contenitore aperto per nome: ogni consumatore scrive sotto il nome che
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
        # dataclass, mai in loop. `cluster.detected.<nome>` per qualunque nome.
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
