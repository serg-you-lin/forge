import ezdxf
doc = ezdxf.readfile(r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\ARC - Copia\ARC.6200012803 Sviluppo\6200012803 Sviluppo\6200012803_2.dxf")
msp = doc.modelspace()
for e in msp:
    print(e.dxftype(), e.dxf.layer)