"""
debug_endpoints.py
------------------
Misura tutti gli endpoint di LINE e ARC nel file DXF
e trova coppie vicine che potrebbero essere lo stesso punto fisico.

Lancia:
    python debug_endpoints.py
"""

import math
import sys
from pathlib import Path
import ezdxf

INPUT_DXF = r"tests/examples/maniglia_no_raccordi.dxf"

# ---------------------------------------------------------------------------

def dist(a, b):
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)

def arc_endpoint(entity, which):
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    r = entity.dxf.radius
    angle = entity.dxf.start_angle if which == 'start' else entity.dxf.end_angle
    x = cx + r * math.cos(math.radians(angle))
    y = cy + r * math.sin(math.radians(angle))
    return (x, y)

# ---------------------------------------------------------------------------

doc = ezdxf.readfile(INPUT_DXF)
msp = doc.modelspace()

print(f"\nFile: {INPUT_DXF}")
print("=" * 70)

# Raccoglie tutti gli endpoint con info entità
endpoints = []

for i, entity in enumerate(msp.query('LINE')):
    s = (entity.dxf.start.x, entity.dxf.start.y)
    e = (entity.dxf.end.x,   entity.dxf.end.y)
    length = dist(s, e)
    print(f"\nLINE #{i+1}")
    print(f"  start  : ({s[0]:.6f}, {s[1]:.6f})")
    print(f"  end    : ({e[0]:.6f}, {e[1]:.6f})")
    print(f"  length : {length:.6f} mm")
    endpoints.append((s, f"LINE#{i+1}", 'start'))
    endpoints.append((e, f"LINE#{i+1}", 'end'))

for i, entity in enumerate(msp.query('ARC')):
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    r = entity.dxf.radius
    a0 = entity.dxf.start_angle
    a1 = entity.dxf.end_angle
    span = a1 - a0 if a1 > a0 else a1 - a0 + 360
    arc_len = math.radians(abs(span)) * r
    s = arc_endpoint(entity, 'start')
    e = arc_endpoint(entity, 'end')
    print(f"\nARC #{i+1}")
    print(f"  centro : ({cx:.6f}, {cy:.6f})")
    print(f"  raggio : {r:.6f} mm")
    print(f"  angoli : {a0:.6f}° → {a1:.6f}°  (span={span:.6f}°)")
    print(f"  length : {arc_len:.6f} mm")
    print(f"  start  : ({s[0]:.6f}, {s[1]:.6f})")
    print(f"  end    : ({e[0]:.6f}, {e[1]:.6f})")
    endpoints.append((s, f"ARC#{i+1}", 'start'))
    endpoints.append((e, f"ARC#{i+1}", 'end'))

# ---------------------------------------------------------------------------
# Trova tutte le coppie di endpoint vicini

print("\n" + "=" * 70)
print("DISTANZE TRA TUTTI GLI ENDPOINT (ordinate)")
print("=" * 70)

pairs = []
for i in range(len(endpoints)):
    for j in range(i+1, len(endpoints)):
        pt_a, name_a, role_a = endpoints[i]
        pt_b, name_b, role_b = endpoints[j]
        d = dist(pt_a, pt_b)
        pairs.append((d, name_a, role_a, pt_a, name_b, role_b, pt_b))

pairs.sort(key=lambda x: x[0])

for d, na, ra, pa, nb, rb, pb in pairs:
    marker = ""
    if d < 0.001:
        marker = "  ← COINCIDENTI"
    elif d < 1.0:
        marker = "  ← GAP SUB-MILLIMETRICO"
    elif d < 10.0:
        marker = "  ← gap piccolo"
    print(f"\n  {na} {ra} ↔ {nb} {rb}")
    print(f"    distanza : {d:.6f} mm{marker}")
    print(f"    punto A  : ({pa[0]:.6f}, {pa[1]:.6f})")
    print(f"    punto B  : ({pb[0]:.6f}, {pb[1]:.6f})")
    print(f"    delta x  : {abs(pa[0]-pb[0]):.6f}")
    print(f"    delta y  : {abs(pa[1]-pb[1]):.6f}")