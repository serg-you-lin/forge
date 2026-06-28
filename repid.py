import struct

path = r"LOCAL_DRAWING.dxf"

with open(path, 'rb') as f:
    version = f.read(6).decode('ascii')
print(version)