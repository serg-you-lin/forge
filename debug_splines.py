import ezdxf
import matplotlib.pyplot as plt
from pathlib import Path
import sys

project_root = Path(".").resolve()
sys.path.insert(0, str(project_root))

import dxf_forge as forge

input_dxf = r"tests/examples/spline_line.dxf"
doc = ezdxf.readfile(input_dxf)
msp = doc.modelspace()

result = forge.heal(msp, tolerance=0.05, write_to_msp=False)
part = result.parts[0]

fig, ax = plt.subplots(figsize=(10, 8))
x, y = part.outer.polygon.exterior.xy
ax.fill(x, y, alpha=0.3, color='blue')
ax.plot(x, y, 'b-', linewidth=2)
ax.set_aspect('equal')
ax.set_title(f"spline_line.dxf — area={part.outer.area:.2f}")
plt.savefig("debug_spline_line.png", dpi=150)
plt.show()
print(f"Area: {part.outer.area:.4f}")