#!/usr/bin/env python3
"""Patch: regenerate report using graphify's generate() with total_words fixed."""
import json, time, shutil
from pathlib import Path
from collections import defaultdict
import networkx as nx

ROOT = Path("/home/wangyc/Documents/工作/法规指导原则/安评")
OUT  = ROOT / "graphify-out"
CONV = OUT / "converted"
ts = "20260420_045432"  # from previous run

# Load graph
GRAPH_JSON_PATH = OUT / f"anshang_graphify_semantic_cron_20260420_045432_graph.json"
with open(GRAPH_JSON_PATH) as f:
    graph_data = json.load(f)

G = nx.Graph()
for nd in graph_data['nodes']:
    nid = nd['id']
    attrs = {k: v for k, v in nd.items() if k not in ('id', 'community', 'degree')}
    G.add_node(nid, **attrs)
for ed in graph_data['edges']:
    src, tgt = ed['source'], ed['target']
    attrs = {k: v for k, v in ed.items() if k not in ('source', 'target')}
    if src not in G: G.add_node(src)
    if tgt not in G: G.add_node(tgt)
    G.add_edge(src, tgt, **attrs)

print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# Estimate total_words
total_words = 11811 * 70
detect_result = {
    "total_files": 71,
    "total_words": total_words,
    "timestamp": ts,
}

# Cluster
try:
    from networkx.algorithms.community import louvain_communities
    communities = louvain_communities(G, resolution=1.0, seed=42)
    communities = [list(c) for c in communities]
except Exception as e:
    communities = [list(c) for c in nx.connected_components(G)]
communities_dict = {i: list(c) for i, c in enumerate(communities)}

node_community = {}
for i, comm in enumerate(communities):
    for node in comm:
        node_community[node] = i

cohesion_scores = {}
for i, comm in enumerate(communities):
    if len(comm) < 2:
        cohesion_scores[i] = 0.0
    else:
        sub = G.subgraph(comm)
        if sub.number_of_edges() > 0:
            cohesion_scores[i] = round(2*sub.number_of_edges()/(len(comm)*(len(comm)-1)), 4)
        else:
            cohesion_scores[i] = 0.0

def node_label(nid):
    return G.nodes[nid].get('label', G.nodes[nid].get('name', nid))
def node_type(nid):
    return G.nodes[nid].get('type', G.nodes[nid].get('entity_type', 'concept'))

degree_dict = dict(G.degree())
top_by_degree = sorted(degree_dict.items(), key=lambda x: x[1], reverse=True)[:20]

comm_summaries = []
for i, comm in enumerate(communities):
    sub = G.subgraph(comm)
    type_counter = defaultdict(int)
    for nid in comm:
        type_counter[node_type(nid)] += 1
    node_degrees = [(nid, degree_dict.get(nid, 0)) for nid in comm]
    node_degrees.sort(key=lambda x: x[1], reverse=True)
    comm_summaries.append({
        'id': i, 'size': len(comm), 'edge_count': sub.number_of_edges(),
        'cohesion': cohesion_scores[i],
        'top_types': dict(sorted(type_counter.items(), key=lambda x: x[1], reverse=True)),
        'top_nodes': [node_label(nid) for nid, _ in node_degrees[:8]],
    })
comm_summaries.sort(key=lambda x: x['size'], reverse=True)

community_labels = {}
for cs in comm_summaries:
    cid = cs['id']
    top_types = list(cs['top_types'].keys())
    community_labels[cid] = f"Community{cid}:{','.join(top_types[:2])}"

god_node_list = []
for nid, deg in top_by_degree[:20]:
    god_node_list.append({
        "label": node_label(nid),
        "type": node_type(nid),
        "edges": deg,
        "community": node_community.get(nid, -1),
    })

surprise_list = []
token_cost = {"input": 0, "output": 0}

print("Generating report...")
from graphify.report import generate
report_md = generate(
    G, communities=communities_dict,
    cohesion_scores=cohesion_scores,
    community_labels=community_labels,
    god_node_list=god_node_list,
    surprise_list=surprise_list,
    detection_result=detect_result,
    token_cost=token_cost,
    root="安评_anshang",
    suggested_questions=None,
)

REPORT_PATH = OUT / f"GRAPH_REPORT_安评_anshang_graphify_semantic_cron_{ts}.md"
with open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.write(report_md)
shutil.copy(REPORT_PATH, OUT / "GRAPH_REPORT_安评_graphify_semantic_cron_latest.md")
print(f"Report: {REPORT_PATH}")
print(f"Report length: {len(report_md)} chars")
