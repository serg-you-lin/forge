import ezdxf
import dxf_forge as forge

doc = ezdxf.readfile(r"LOCAL_DRAWING.dxf")
msp = doc.modelspace()
result = forge.heal(msp)
for i, part in enumerate(result.parts):
    print(f"part {i}: area={part.outer.polygon.area:.4f}")