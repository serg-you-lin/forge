import ezdxf
import math

doc = ezdxf.readfile(r"tests/examples/rect_with_threaded_holes_geometric.dxf")
msp = doc.modelspace()

circles = list(msp.query("CIRCLE"))
arcs    = list(msp.query("ARC"))

for c in circles:
    print(f"CIRCLE  center=({c.dxf.center.x:.2f}, {c.dxf.center.y:.2f})  r={c.dxf.radius:.2f}")

for a in arcs:
    cx, cy = a.dxf.center.x, a.dxf.center.y
    r      = a.dxf.radius
    start  = a.dxf.start_angle
    end    = a.dxf.end_angle
    # swept convenzionale ezdxf (CCW)
    swept  = (end - start) % 360
    print(f"ARC     center=({cx:.2f}, {cy:.2f})  r={r:.2f}  start={start:.1f}°  end={end:.1f}°  swept={swept:.1f}°")