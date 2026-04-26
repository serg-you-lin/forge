import ezdxf
from shapely.geometry import Polygon
import math

doc = ezdxf.readfile(r"tests/examples/flangia_scantonata.DXF")
msp = doc.modelspace()

for pline in msp.query('LWPOLYLINE'):
    pts = list(pline.get_points('xy'))
    poly = Polygon(pts)
    print(f"layer={pline.dxf.layer} area={poly.area:.1f} valid={poly.is_valid} pts={len(pts)}")

for pline in msp.query('LWPOLYLINE'):
    print(f"metodi disponibili: {[m for m in dir(pline) if 'point' in m.lower() or 'flat' in m.lower()]}")
    print(f"vertici raw: {list(pline.get_points('xyb'))}")

for circle in msp.query('CIRCLE'):
    r = circle.dxf.radius
    c = circle.dxf.center
    print(f"CIRCLE layer={circle.dxf.layer} area={math.pi*r**2:.1f} centro=({c.x:.1f}, {c.y:.1f})")


for entity in msp.query('ARC'):
    print(f"start={entity.dxf.start_angle} end={entity.dxf.end_angle}")
for entity in msp.query('LINE'):
    print(f"start={entity.dxf.start} end={entity.dxf.end}")





from collections import defaultdict
import numpy as np

def round_pt(pt, d=1):
    return (round(pt[0], d), round(pt[1], d))

graph = defaultdict(list)
for entity in msp.query('LINE'):
    s = round_pt((entity.dxf.start.x, entity.dxf.start.y))
    e = round_pt((entity.dxf.end.x, entity.dxf.end.y))
    print(f"LINE: {s} -> {e}")
    graph[s].append(e)
    graph[e].append(s)

for entity in msp.query('ARC'):
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    r = entity.dxf.radius
    start = entity.dxf.start_angle
    end = entity.dxf.end_angle
    s = round_pt((cx + r*np.cos(np.radians(start)), cy + r*np.sin(np.radians(start))))
    e = round_pt((cx + r*np.cos(np.radians(end)), cy + r*np.sin(np.radians(end))))
    print(f"ARC: {s} -> {e}")
    graph[s].append(e)
    graph[e].append(s)

print("\nNodi:")
for node, neighbors in graph.items():
    print(f"  {node} -> {neighbors}")



import numpy as np
from shapely.geometry import Polygon

points = [(np.float64(-150.0), np.float64(-99.5), np.float64(3.31662479035757)),
          (np.float64(-150.0), np.float64(99.5), np.float64(0.0))]

pts = []
n = len(points)
for i in range(n):
    x1, y1, bulge = points[i]
    x2, y2, _ = points[(i + 1) % n]
    pts.append((x1, y1))
    if abs(bulge) > 1e-6:
        angle = 4 * np.arctan(bulge)
        cx = ((x1+x2)/2) - (y2-y1)/(2*bulge)
        cy = ((y1+y2)/2) + (x2-x1)/(2*bulge)
        r = np.sqrt((x1-cx)**2 + (y1-cy)**2)
        a1 = np.arctan2(y1-cy, x1-cx)
        num_seg = max(8, int(abs(angle)/np.pi*32))
        for j in range(1, num_seg):
            a = a1 + angle * j / num_seg
            pts.append((cx + r*np.cos(a), cy + r*np.sin(a)))

print(f"punti generati: {len(pts)}")
print(f"primi 3: {pts[:3]}")
poly = Polygon(pts)
print(f"area: {poly.area:.1f}")


doc2 = ezdxf.readfile("tests/examples/flangia_scantonata.DXF_healed.dxf")
msp2 = doc2.modelspace()
for pline in msp2.query('LWPOLYLINE'):
    pts_raw = list(pline.get_points('xyb'))
    print(f"vertici raw con bulge: {pts_raw}")
    from shapely.geometry import Polygon
    pts = [(p[0], p[1]) for p in pts_raw]
    poly = Polygon(pts)
    print(f"area senza archi: {poly.area:.1f}")