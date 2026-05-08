import os
from pathlib import Path
import ezdxf
from dxf_forge.dxf_inspect import DxfInspector


class DxfAnalyzer:

    def __init__(self, inspector: DxfInspector | None = None):

        if inspector is None:
            inspector = DxfInspector(
                summary=True,
                lines=True,
                arcs=True,
                polylines=True,
                circles=True,
                splines=True,
                graph=False,
            )

        self.inspector = inspector
        self.files_data = []

    # ------------------------------------------------
    # ANALISI SINGOLO FILE
    # ------------------------------------------------

    def analyze_file(self, filepath: str):

        filepath = Path(filepath).resolve()

        try:
            doc = ezdxf.readfile(filepath)
        except IOError:
            print(f"File non trovato: {filepath}")
            return None
        except ezdxf.DXFStructureError:
            print(f"DXF non valido: {filepath}")
            return None

        msp = doc.modelspace()

        print(f"\nAnalisi: {filepath.name}")

        self.inspector.analyze(msp, title=str(filepath), doc=doc)

        info = self.get_file_info(doc, filepath)

        self.files_data.append(info)

        return info

    # ------------------------------------------------
    # ANALISI CARTELLA
    # ------------------------------------------------

    def analyze_folder(self, folder: str, recursive: bool = False):
        folder = Path(folder).resolve()

        if not folder.exists():
            print("Cartella non trovata")
            return

        pattern = "**/*" if recursive else "*"
        dxf_files = [
            f for f in folder.glob(pattern)
            if f.is_file() and f.suffix.lower() == ".dxf"
        ]

        print(f"\nTrovati {len(dxf_files)} DXF\n")

        for file in dxf_files:
            self.analyze_file(file)

        return self.summary_stats()

    # ------------------------------------------------
    # INFO SINGOLO FILE
    # ------------------------------------------------

    def get_file_info(self, doc, filepath):
        import json
        from collections import Counter

        msp = doc.modelspace()
        counts = Counter(e.dxftype() for e in msp)

        forge_meta = []
        for entity in msp:
            try:
                xdata = entity.get_xdata('FORGE')
                if xdata:
                    for tag in xdata:
                        if tag.code == 1000:
                            forge_meta.append(json.loads(tag.value))
            except Exception:
                pass

        return {
            "file":         filepath.name,
            "version":      doc.dxfversion,
            "entity_types": dict(counts),
            "has_xdata":    len(forge_meta) > 0,
            "forge_meta":   forge_meta,
        }

    # ------------------------------------------------
    # STATISTICHE GLOBALI
    # ------------------------------------------------

    def summary_stats(self):

        stats = {
            "total_files": len(self.files_data),
            "versions": {},
            "total_entities": 0,
        }

        for data in self.files_data:

            version = data["version"]

            stats["versions"].setdefault(version, 0)
            stats["versions"][version] += 1

            #stats["total_entities"] += data["entities"]
            stats["total_entities"] += sum(data["entity_types"].values())

        print("\n===== SUMMARY =====")

        print(f"Files analizzati: {stats['total_files']}")
        print(f"Entità totali: {stats['total_entities']}")

        print("\nVersioni DXF:")

        for v, count in stats["versions"].items():
            print(f"  {v}: {count}")

        xdata_count = sum(1 for d in self.files_data if d["has_xdata"])
        xdata_names = [d["file"] for d in self.files_data if d["has_xdata"]]
        print(f"File con XDATA FORGE: {xdata_count}/{stats['total_files']}")
        print(f"File con XDATA FORGE: {xdata_names}")

        return stats
    

if __name__ == "__main__":
    import sys
    DEFAULT_FILE = "tests/examples/archi_bastardi_healed.dxf"
    DEFAULT_FOLDER = r"C:\Users\FEDERICO\Documents\Python_Scripts\Projects\GitHub\dxf-forge-devs\tests\examples"

    analyzer = DxfAnalyzer()

    if len(sys.argv) > 1:

        path = sys.argv[1]

        if Path(path).is_file():
            analyzer.analyze_file(path)

        else:
            analyzer.analyze_folder(path)

    else:
        analyzer.analyze_folder(DEFAULT_FOLDER)
        #analyzer.summary_stats()