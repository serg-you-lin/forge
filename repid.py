import ezdxf
import dxf_forge as forge

doc = ezdxf.readfile(r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\ProTest\Ostici\fa_che_non_mi_incazzi.dxf")
msp = doc.modelspace()
result = forge.heal(msp)
for i, part in enumerate(result.parts):
    print(f"part {i}: area={part.outer.polygon.area:.4f}")