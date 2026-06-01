import ezdxf
import dxf_forge as forge
import copy

input_file = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\TON_06_05_2026\6200012912 Esplosi.dxf"

doc = ezdxf.readfile(input_file)
msp = doc.modelspace()

def snapshot(result, tag):
    print(f"\n--- SNAPSHOT {tag} ---")
    for i, p in enumerate(result.parts):
        print(
            i,
            p.label,
            "bending:",
            len(p.geometry_hints.bend_line_ids),
            "custom_keys:",
            list(p.custom.keys())
        )

# -------------------------
# HEAL + DETECT BASE
# -------------------------

result = forge.heal(msp)
forge.detect(result, msp)

snapshot(result, "AFTER DETECT")

# deep copy per isolare split
result_before_split = copy.deepcopy(result)

# -------------------------
# SPLIT
# -------------------------

output_dir = "./_split_debug"

forge.split(
    msp,
    result,
    output_folder=output_dir,
    namer=lambda i, part: f"PART_{i}"
)

snapshot(result, "AFTER SPLIT")

# -------------------------
# COMPARAZIONE
# -------------------------

print("\n--- DIFF CHECK ---")

for i in range(len(result.parts)):
    a = result_before_split.parts[i]
    b = result.parts[i]

    print(
        i,
        "bend diff:",
        len(a.geometry_hints.bend_line_ids),
        "->",
        len(b.geometry_hints.bend_line_ids),
    )




# import ezdxf
# import dxf_forge as forge

# input_file = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\TON_06_05_2026\6200012912 Esplosi.dxf"

# doc = ezdxf.readfile(input_file)
# msp = doc.modelspace()

# def snapshot(result, tag):
#     print(f"\n--- {tag} ---")
#     for i, p in enumerate(result.parts):
#         print(
#             i,
#             "bending:",
#             len(p.geometry_hints.bend_line_ids)
#         )

# # -------------------------
# # HEAL + DETECT
# # -------------------------

# result = forge.heal(msp)
# forge.detect(result, msp)

# snapshot(result, "BEFORE WRITE")

# # -------------------------
# # WRITE ONLY
# # -------------------------

# forge.write(msp, result)

# snapshot(result, "AFTER WRITE")