"""
14_style_classification.py — classificare dal linetype/colore, non solo dal layer
==================================================================================

API forge usate:
    load_dxf(..., linetype_map=..., color_map=...)   seconda lane di classificazione

label_map assegna il ruolo di un'entità dal NOME LAYER. Quando il disegno usa
invece lo stile della linea per portare intenzione ("le tratteggiate sono
pieghe", "il ciano è incisione"), linetype_map / color_map fanno lo stesso
lavoro sull'aspetto grezzo dell'entità (Edge.style, Cluster E):

    linetype_map = {"DASHED": "bending", "CENTER": "bending"}
    color_map    = {"cyan": "engrave"}      # nome ACI standard, o intero/stringa "4"

Stesso vocabolario work_type di label_map (WORK_TYPE_TO_ROLE). label_map resta
la lane AUTORITATIVA: linetype_map/color_map decidono solo dove il layer non
ha già deciso — un'entità il cui layer è già in label_map non viene mai
riclassificata dallo stile. Una volta assegnato, il ruolo entra nelle stesse
lane di sempre (_split_labeled / _detect_labeled): per detect() non c'è
differenza fra un ruolo arrivato dal layer o dallo stile.

    python 14_style_classification.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import os

import forge

# --- CONFIG ------------------------------------------------------------
INPUT     = r"tests/examples/lynetype-color-maps.dxf"
TOLERANCE = 0.5
LABEL_MAP    = {"MARK": "engrave"}     # come negli altri script — layer noto
LINETYPE_MAP = {"DOT": "bending"}   # le 64 linee assiali tratteggiate, trash oggi
COLOR_MAP    = {"cyan": "engrave"}     # entità colorate ciano non su un layer noto
OUTDIR       = "pipeline_output"       # come negli altri script — ignorato da git
# -------------------------------------------------------------------------

os.makedirs(OUTDIR, exist_ok=True)


def show(tag, result):
    p = result.clusters[0]
    print(f"{tag:<24} bending={len(p.bending_lines):<3} engrave={len(p.engrave_lines):<3} "
          f"trash={len(result.trash_entities):<3}")


# Ogni file isola UN classificatore aggiuntivo rispetto al solo label_map —
# mai cumulativi fra loro, altrimenti un effetto visto nel file "color" può
# in realtà venire dal linetype_map di uno step precedente (bug di questo
# stesso script, segnalato da Federico: v1 passava linetype_map anche allo
# step "+ color_map", quindi Bend/DOT restava classificato bending per il
# linetype ancora attivo, non per il colore — non era il colore a decidere.

# 1. solo label_map (layer) — comportamento di sempre
doc = forge.load_dxf(INPUT, tolerance=TOLERANCE, label_map=LABEL_MAP)
r = forge.heal(doc, tolerance=TOLERANCE)
forge.detect(r)
show("solo label_map", r)
forge.to_dxf(r, doc, include_trash=True).saveas(os.path.join(OUTDIR, "14_style_classification_1_label_only.dxf"))

# 2. SOLO linetype_map (isolato, niente color_map)
doc = forge.load_dxf(
    INPUT, tolerance=TOLERANCE,
    linetype_map=LINETYPE_MAP,
)
r_linetype = forge.heal(doc, tolerance=TOLERANCE)
forge.detect(r_linetype)
show("solo linetype_map", r_linetype)
forge.to_dxf(r_linetype, doc, include_trash=True).saveas(
    os.path.join(OUTDIR, "14_style_classification_2_linetype_only.dxf")
)

# 3. SOLO color_map (isolato, niente linetype_map)
doc = forge.load_dxf(
    INPUT, tolerance=TOLERANCE,
    color_map=COLOR_MAP,
)
r_color = forge.heal(doc, tolerance=TOLERANCE)
forge.detect(r_color)
show("solo color_map", r_color)
forge.to_dxf(r_color, doc, include_trash=True).saveas(
    os.path.join(OUTDIR, "14_style_classification_3_color_only.dxf")
)

print("\nBending lines promosse da linetype_map (source='labeled' anche se il")
print("ruolo viene dallo stile, non dal layer — stessa lane di label_map, solo")
print("un altro segnale in ingresso):")
for bl in r_linetype.clusters[0].bending_lines[:5]:
    print(f"   len={bl.length:6.1f}  angle={bl.angle_deg:6.1f}  source={bl.source}")
print(f"   ... {len(r_linetype.clusters[0].bending_lines)} totali")

print("\ncolor_map su questo file (cyan -> engrave) è ridondante: le uniche")
print("entità cyan sono già su MARK, già coperto da label_map — infatti")
print(f"bending={len(r_color.clusters[0].bending_lines)} qui, non {len(r_linetype.clusters[0].bending_lines)}: "
      f"conferma che era linetype_map, non color_map, a classificare Bend/DOT.")
