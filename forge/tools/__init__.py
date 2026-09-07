"""
forge/tools/
------------
Stadi opzionali e componibili su un ``ForgeResult`` già prodotto da
``forge.heal``. Ognuno lo arricchisce in-place e lo ritorna; il chiamante
sceglie quali eseguire e in che ordine.

- ``detect``               — classifica le feature dentro i cluster
- ``interpret_annotations`` — àncora ogni annotazione al cluster che la contiene
- ``inject``               — passa i testi di un cluster a un data_injector esterno

È il pattern che un interprete di disegno (progetto separato) generalizza e
orchestra dall'alto (vedi ``INTERPRETER.md``).
"""

from .detect import detect, ALL_FEATURES
from .interpret import interpret_annotations
from .inject import inject

__all__ = ["detect", "ALL_FEATURES", "interpret_annotations", "inject"]
