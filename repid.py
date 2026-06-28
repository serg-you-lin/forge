import struct

path = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\TON_25-06-2026\disegni\Otto INOX 2.dwg"

with open(path, 'rb') as f:
    version = f.read(6).decode('ascii')
print(version)