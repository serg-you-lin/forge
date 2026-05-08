# import snapmark as sm
# #print(dir(sm))

# print(sm.FixSeq.__doc__)
# print(sm.TextBuilder.__doc__)


from tests.test_collinear import make_line


a = make_line(0.0, -39.628, 45.0, -39.628)
b = make_line(0.0,  21.114,  5.2,  21.114)

from dxf_forge.core.geometry import _line_direction, _point_to_line_distance

print("dir_a:", _line_direction(a))
print("dir_b:", _line_direction(b))
print("cross:", abs(_line_direction(a)[0] * _line_direction(b)[1] - _line_direction(a)[1] * _line_direction(b)[0]))
print("dist:", _point_to_line_distance(b.dxf.start.x, b.dxf.start.y, a))



from dxf_forge.core.geometry import are_collinear

lines = [
    make_line(125.0, -39.628, 170.0, -39.628),
    make_line(0.0,   -39.628,  45.0, -39.628),
    make_line(125.0,  21.114, 130.2,  21.114),
    make_line(164.8,  21.114, 170.0,  21.114),
    make_line(0.0,    21.114,   5.2,  21.114),
    make_line(39.8,   21.114,  45.0,  21.114),
]

for i, a in enumerate(lines):
    for j, b in enumerate(lines):
        if i != j:
            print(f"  {i} vs {j}: {are_collinear(a, b)}")