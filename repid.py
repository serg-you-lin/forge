import ezdxf
doc = ezdxf.readfile(r"LOCAL_DRAWING.dxf")
msp = doc.modelspace()
for e in msp:
    print(e.dxftype(), e.dxf.layer)