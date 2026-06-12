from dxf_forge.models import Edge
from dxf_forge.core.graph import build_node_graph, find_closed_loops
from shapely.geometry import LineString

edges = [
    Edge(entity=None, layer="0", start=(0,0), end=(100,0), geometry=LineString([(0,0),(100,0)])),
    Edge(entity=None, layer="0", start=(100,0), end=(100,50), geometry=LineString([(100,0),(100,50)])),
    Edge(entity=None, layer="0", start=(100,50), end=(0,50), geometry=LineString([(100,50),(0,50)])),
    Edge(entity=None, layer="0", start=(0,50), end=(0,0), geometry=LineString([(0,50),(0,0)])),
]
graph = build_node_graph(edges)
print("nodes:", len(graph))
loops = find_closed_loops(graph)
print("loops:", len(loops))