"""
snapmark_ops.py
---------------
Classi Operation-compatibili per usare dxf-forge dentro le pipeline snapmark.

Ereditano dall'interfaccia Operation di snapmark, quindi si usano
esattamente come qualsiasi altra operazione snapmark:

    from dxf_forge.snapmark_ops import ForgeHeal, ForgeSplit
    from snapmark import IterationManager

    manager = IterationManager("cartella/")
    manager.add_operation(ForgeHeal(), ForgeSplit(output_folder="output/"))
    manager.execute()

NOTA: questo modulo importa da snapmark solo a runtime (try/except),
quindi dxf-forge funziona anche senza snapmark installato.
"""

from .healer import heal
from .splitter import split_to_files
from ..rules.validator import validate


try:
    from snapmark.core import Operation
    _SNAPMARK_AVAILABLE = True
except ImportError:
    # Se snapmark non è installato, definiamo uno stub
    # così il modulo è importabile comunque
    class Operation:
        def execute(self, doc, folder, file_name):
            raise NotImplementedError
        def message(self, file_name):
            pass
    _SNAPMARK_AVAILABLE = False


class ForgeHeal(Operation):
    """
    Operation snapmark che ripara la geometria del DXF.
    LINE + ARC → LWPOLYLINE chiuse sui layer OuterContour e HEALED_HOLE.

    Esempio:
        manager.add_operation(ForgeHeal(tolerance=0.1))
    """

    def __init__(self, tolerance: float = 0.05, write_to_msp: bool = True):
        super().__init__()
        self.tolerance = tolerance
        self.write_to_msp = write_to_msp
        self.message_text = None  # usa il default di Operation

    def execute(self, doc, folder, file_name):
        msp = doc.modelspace()
        result = heal(msp, tolerance=self.tolerance, write_to_msp=self.write_to_msp)

        if result.errors:
            for err in result.errors:
                print(f"  [FORGE ERROR] {err}")
        if result.warnings:
            for w in result.warnings:
                print(f"  [FORGE WARN] {w}")

        self.message_text = (
            f"ForgeHeal: {result.part_count} contorni trovati in {file_name}"
        )
        # Restituisce True se ha modificato il msp (per triggherare il save in snapmark)
        return self.write_to_msp and result.part_count > 0


class ForgeSplit(Operation):
    """
    Operation snapmark che divide un DXF multi-pezzo in file separati.

    Esempio:
        manager.add_operation(ForgeSplit(output_folder="output/parti/"))
    """

    def __init__(self, output_folder: str = None):
        super().__init__()
        self.output_folder = output_folder
        self.modifies_files = False  # non modifica il file originale

    def execute(self, doc, folder, file_name):
        import os
        msp = doc.modelspace()
        label = os.path.splitext(file_name)[0]
        out_folder = self.output_folder or os.path.join(folder, "split_output")

        result = split_to_files(msp, output_folder=out_folder,
                                label=label, source_file=file_name)

        self.message_text = (
            f"ForgeSplit: {result.part_count} parti generate da {file_name}"
        )
        return False  # non modifica il file originale
