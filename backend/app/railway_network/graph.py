import networkx as nx
from app.core.data import STATIONS, EDGES

def build_graph():
    g=nx.Graph()
    for s in STATIONS: g.add_node(s['code'], **s)
    for a,b,km,tracks in EDGES: g.add_edge(a,b,distance_km=km, travel_min=km/85*60, tracks=tracks, capacity=tracks*4, congestion=0.0)
    return g

GRAPH=build_graph()

def route_options(origin: str, destination: str):
    if origin not in GRAPH or destination not in GRAPH: raise ValueError('Unknown station code')
    paths=list(nx.shortest_simple_paths(GRAPH,origin,destination,weight='travel_min'))[:3]
    out=[]
    for p in paths:
        cost=sum(GRAPH[a][b]['travel_min'] for a,b in zip(p,p[1:]))
        congestion=sum(GRAPH[a][b]['congestion']*15 for a,b in zip(p,p[1:]))
        out.append({'stations':p,'travel_minutes':round(cost,1),'congestion_penalty':round(congestion,1),'score':round(cost+congestion,1)})
    return sorted(out,key=lambda x:x['score'])
