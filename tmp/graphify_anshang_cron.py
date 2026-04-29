#!/usr/bin/env python3
"""Full graphify pipeline for 安评 - anshang semantic cron - 2026-04-17"""
import os, json, sys, shutil
from pathlib import Path
from collections import defaultdict
from datetime import datetime

print("=== Full Graphify Pipeline for 安评 (cron 2026-04-17) ===")
ts = datetime.now().strftime("%Y%m%d_%H%M%S")

source_dir = Path("/home/wangyc/Documents/工作/法规指导原则/安评")
output_dir = source_dir / "graphify-out"

# Step 2: Load semantic data from /tmp
print("\n[Step 2] Loading semantic data...")
semantic_path = Path("/tmp/.graphify_semantic.json")
if not semantic_path.exists():
    print("ERROR: /tmp/.graphify_semantic.json not found!")
    sys.exit(1)
with open(semantic_path, encoding='utf-8') as f:
    semantic_data = json.load(f)
nodes_data = semantic_data.get('nodes', [])
edges_data = semantic_data.get('edges', [])
print("  Semantic: {} nodes, {} edges".format(len(nodes_data), len(edges_data)))

# Step 3: Build graph
print("\n[Step 3] Building graph...")
import networkx as nx
G = nx.Graph()
for node in nodes_data:
    nid = node.get('id') or node.get('name') or ''
    if not nid:
        continue
    attrs = {k: v for k, v in node.items() if k != 'id'}
    G.add_node(nid, **attrs)
for edge in edges_data:
    src = edge.get('source') or edge.get('from') or edge.get('src') or ''
    tgt = edge.get('target') or edge.get('to') or edge.get('dst') or ''
    if not src or not tgt:
        continue
    if src not in G:
        G.add_node(src)
    if tgt not in G:
        G.add_node(tgt)
    attrs = {k: v for k, v in edge.items() if k not in ('source','target','from','to','src','dst')}
    G.add_edge(src, tgt, **attrs)
print("  Graph: {} nodes, {} edges".format(G.number_of_nodes(), G.number_of_edges()))

# Step 4: Cluster
print("\n[Step 4] Clustering...")
try:
    from networkx.algorithms.community import louvain_communities
    communities = louvain_communities(G, resolution=1.0, seed=42)
    communities = [list(c) for c in communities]
except Exception as e:
    print("  Louvain failed: {}".format(e))
    communities = [list(c) for c in nx.connected_components(G)]
print("  Communities: {}".format(len(communities)))

node_community = {}
for i, comm in enumerate(communities):
    for node in comm:
        node_community[node] = i

cohesion_scores = {}
for i, comm in enumerate(communities):
    if len(comm) < 2:
        cohesion_scores[i] = 0.0
    else:
        subgraph = G.subgraph(comm)
        if subgraph.number_of_edges() > 0:
            cohesion_scores[i] = round(2 * subgraph.number_of_edges() / (len(comm) * (len(comm) - 1)), 4)
        else:
            cohesion_scores[i] = 0.0

# Helper functions
def node_label(nid):
    return G.nodes[nid].get('label', G.nodes[nid].get('name', nid))

def node_type(nid):
    return G.nodes[nid].get('type', G.nodes[nid].get('entity_type', 'concept'))

# Step 5: Compute statistics
print("\n[Step 5] Analyzing...")
degree_dict = dict(G.degree())
top_nodes_by_degree = sorted(degree_dict.items(), key=lambda x: x[1], reverse=True)[:50]
print("  Top node: {} ({} degree)".format(node_label(top_nodes_by_degree[0][0]), top_nodes_by_degree[0][1]))

# Community summaries
comm_summaries = []
for i, comm in enumerate(communities):
    subgraph = G.subgraph(comm)
    type_counter = defaultdict(int)
    for nid in comm:
        t = node_type(nid)
        type_counter[t] += 1
    node_degrees = [(nid, degree_dict.get(nid, 0)) for nid in comm]
    node_degrees.sort(key=lambda x: x[1], reverse=True)
    comm_summaries.append({
        'id': i,
        'size': len(comm),
        'edges': subgraph.number_of_edges(),
        'cohesion': cohesion_scores.get(i, 0.0),
        'types': dict(type_counter),
        'top_nodes': node_degrees[:15]
    })

# Sort communities by size
comm_summaries.sort(key=lambda x: x['size'], reverse=True)
print("  Largest community: {} nodes, {} edges".format(comm_summaries[0]['size'], comm_summaries[0]['edges']))

# Pre-compute all dynamic values for HTML
nodes_js = json.dumps([{'id': n, 'label': node_label(n), 'type': node_type(n),
                        'community': node_community.get(n, -1), 'degree': degree_dict.get(n, 0),
                        'source': G.nodes[n].get('source','')} for n in G.nodes()], ensure_ascii=False)
edges_js = json.dumps([{'from': u, 'to': v, 'relation': d.get('relation', d.get('label','')),
                        'weight': d.get('weight', 1)} for u, v, d in G.edges(data=True)], ensure_ascii=False)

type_color_map = {
    'drug_type': '#66c2a5', 'toxicity_study': '#fc8d62', 'endpoint': '#8da0cb',
    'test_method': '#e78ac3', 'regulatory': '#a6d854', 'species': '#ffd92f',
    'concept': '#999999', 'document': '#e41a1c', 'guideline': '#377eb8', 'default': '#999999'
}
type_colors_js = json.dumps(type_color_map)
cmap_colors = ['#e41a1c','#377eb8','#4daf4a','#984ea3','#ff7f00','#ffff33','#a65628','#f781bf',
               '#999999','#66c2a5','#fc8d62','#8da0cb','#e78ac3','#a6d854','#ffd92f']
comm_colors_js = json.dumps({i: cmap_colors[i % len(cmap_colors)] for i in range(len(communities))})
communities_len = len(communities)
nodes_count = G.number_of_nodes()
edges_count = G.number_of_edges()
large_comm_count = len([c for c in comm_summaries if c['size'] > 10])

# Step 6: Generate HTML
print("\n[Step 6] Generating HTML...")

html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Knowledge Graph - Anshang """ + ts + """</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Segoe UI',Arial,sans-serif; background:#1a1a2e; color:#eee; }
.header { background:#16213e; padding:20px; border-bottom:2px solid #0f3460; }
.header h1 { color:#e94560; font-size:1.5em; }
.header p { color:#aaa; margin-top:5px; font-size:0.9em; }
.stats { display:flex; gap:30px; padding:15px 20px; background:#16213e; flex-wrap:wrap; }
.stat { background:#0f3460; padding:10px 20px; border-radius:8px; }
.stat .num { font-size:1.8em; color:#e94560; font-weight:bold; }
.stat .label { font-size:0.8em; color:#aaa; }
.controls { padding:10px 20px; background:#0f3460; display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
.controls input { background:#1a1a2e; border:1px solid #444; color:#eee; padding:8px 12px; border-radius:5px; width:250px; }
.controls select { background:#1a1a2e; border:1px solid #444; color:#eee; padding:8px; border-radius:5px; }
.controls button { background:#e94560; border:none; color:white; padding:8px 16px; border-radius:5px; cursor:pointer; }
#graph { width:100%; height:calc(100vh - 200px); background:#1a1a2e; }
.legend { position:fixed; bottom:20px; right:20px; background:#16213e; border:1px solid #0f3460; border-radius:8px; padding:15px; max-height:300px; overflow-y:auto; z-index:100; }
.legend h3 { color:#e94560; margin-bottom:10px; font-size:0.9em; }
.legend-item { display:flex; align-items:center; gap:8px; margin:4px 0; font-size:0.8em; }
.legend-dot { width:12px; height:12px; border-radius:50%; flex-shrink:0; }
.info { position:fixed; bottom:20px; left:20px; background:#16213e; border:1px solid #0f3460; border-radius:8px; padding:15px; max-width:300px; z-index:100; }
.info h3 { color:#e94560; margin-bottom:8px; font-size:0.9em; }
.info p { font-size:0.8em; color:#ccc; margin:3px 0; }
</style>
</head>
<body>
<div class="header">
  <h1>Knowledge Graph - Nonclinical Safety Evaluation Guidelines</h1>
  <p>Generated: """ + ts + """ | Based on """ + str(len(nodes_data)) + """ semantic entities from 70 guidelines</p>
</div>
<div class="stats">
  <div class="stat"><div class="num">""" + str(nodes_count) + """</div><div class="label">Entity Nodes</div></div>
  <div class="stat"><div class="num">""" + str(edges_count) + """</div><div class="label">Semantic Relations</div></div>
  <div class="stat"><div class="num">""" + str(communities_len) + """</div><div class="label">Communities</div></div>
  <div class="stat"><div class="num">""" + str(large_comm_count) + """</div><div class="label">Large Communities</div></div>
</div>
<div class="controls">
  <input type="text" id="searchInput" placeholder="Search entities...">
  <select id="typeFilter"><option value="">All Types</option></select>
  <select id="commFilter"><option value="">All Communities</option></select>
  <span id="countLabel" style="color:#aaa;font-size:0.85em;">Showing all</span>
</div>
<div id="graph"></div>
<div class="legend" id="legend"><h3>Legend</h3></div>
<div class="info" id="info"><h3>Node Info</h3><p>Click a node to view details</p></div>
<script src="https://cdn.jsdelivr.net/npm/vis-network/standalone/umd/vis-network.min.js"></script>
<script>
var _nodes = """ + nodes_js + """;
var _edges = """ + edges_js + """;
var _typeColors = """ + type_colors_js + """;
var _commColors = """ + comm_colors_js + """;
var _commLen = """ + str(communities_len) + """;

_nodes.forEach(function(n) {
  n.color = _typeColors[n.type] || '#999';
  n.font = {color:'#eee', size: n.degree > 30 ? 16 : n.degree > 10 ? 13 : 11};
  n.size = Math.max(8, Math.min(40, n.degree * 0.8 + 8));
});

var typeFilter = document.getElementById('typeFilter');
var allTypes = [...new Set(_nodes.map(function(n){return n.type;}))];
allTypes.forEach(function(t) {
  var opt = document.createElement('option');
  opt.value = t; opt.textContent = t;
  typeFilter.appendChild(opt);
});

var commFilter = document.getElementById('commFilter');
for (var ci = 0; ci < _commLen; ci++) {
  var opt = document.createElement('option');
  opt.value = ci;
  opt.textContent = 'Community #' + ci + ' (' + (_nodes.filter(function(n){return n.community===ci;}).length) + ' nodes)';
  commFilter.appendChild(opt);
}

var container = document.getElementById('graph');
var data = {nodes: new vis.DataSet(_nodes), edges: new vis.DataSet(_edges)};
var options = {
  nodes: {borderWidth: 1, shape: 'dot', shadow: {enabled: true}},
  edges: {width: 0.3, color: {color: '#444', opacity: 0.4}, smooth: {type: 'continuous'}},
  physics: {barnesHut: {gravitationalConstant: -5000, centralGravity: 0.3, springLength: 120, springConstant: 0.04}},
  interaction: {hover: true, tooltipDelay: 100, hideEdgesOnDrag: true},
  layout: {improvedLayout: true}
};
var network = new vis.Network(container, data, options);
network.on('click', function(props) {
  var ids = props.nodes;
  if (ids.length > 0) {
    var n = _nodes.find(function(x){return x.id === ids[0];});
    if (n) {
      document.getElementById('info').innerHTML = '<h3>Node Info</h3><p><b>'+n.label+'</b></p><p>Type: '+n.type+'</p><p>Community: #'+n.community+'</p><p>Degree: '+n.degree+'</p><p>Source: '+(n.source||'N/A')+'</p>';
    }
  }
});
network.on('doubleClick', function(props) {
  if (props.nodes.length > 0) { network.focus(props.nodes[0], {scale: 1.5, animation: true}); }
});

function filterNodes() {
  var q = document.getElementById('searchInput').value.toLowerCase();
  var ft = document.getElementById('typeFilter').value;
  var fc = document.getElementById('commFilter').value;
  var visible = _nodes.filter(function(n) {
    var match = n.label.toLowerCase().indexOf(q) >= 0;
    if (ft && n.type !== ft) match = false;
    if (fc !== '' && n.community !== parseInt(fc)) match = false;
    return match;
  });
  document.getElementById('countLabel').textContent = 'Showing ' + visible.length + ' / ' + _nodes.length;
  var visibleIds = {};
  visible.forEach(function(n){ visibleIds[n.id] = true; });
  data.nodes.forEach(function(n) { n.hidden = !visibleIds[n.id]; });
  data.edges.forEach(function(e) { e.hidden = !visibleIds[e.from] || !visibleIds[e.to]; });
  data.nodes.refresh();
  data.edges.refresh();
}
document.getElementById('searchInput').addEventListener('input', filterNodes);
document.getElementById('typeFilter').addEventListener('change', filterNodes);
document.getElementById('commFilter').addEventListener('change', filterNodes);

var legend = document.getElementById('legend');
Object.keys(_typeColors).forEach(function(t) {
  var div = document.createElement('div');
  div.className = 'legend-item';
  div.innerHTML = '<div class="legend-dot" style="background:'+_typeColors[t]+'"></div><span>'+t+'</span>';
  legend.appendChild(div);
});
</script>
</body></html>"""

# Step 7: Save outputs
html_path = source_dir / ("知识图谱_anshang_semantic_cron_" + ts + ".html")
json_out_path = source_dir / ("知识图谱_anshang_semantic_cron_" + ts + ".json")

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print("  Saved HTML: {}".format(html_path))

with open(json_out_path, 'w', encoding='utf-8') as f:
    json.dump({'nodes': [{'id': n, **dict(G.nodes[n])} for n in G.nodes()],
               'edges': [{'source': u, 'target': v, **dict(d)} for u, v, d in G.edges(data=True)],
               'communities': [{'id': c['id'], 'size': c['size'], 'cohesion': c['cohesion'], 'types': c['types']} for c in comm_summaries]
              }, f, ensure_ascii=False, indent=2)
print("  Saved JSON: {}".format(json_out_path))

shutil.copy(html_path, source_dir / "知识图谱_anshang_semantic_cron_latest.html")
shutil.copy(json_out_path, source_dir / "知识图谱_anshang_semantic_cron_latest.json")

# Step 8: Generate GRAPH_REPORT.md
print("\n[Step 8] Generating GRAPH_REPORT.md...")
report_path = source_dir / ("GRAPH_REPORT_anshang_semantic_cron_" + ts + ".md")

report_lines = [
    "# Knowledge Graph Analysis Report - Nonclinical Safety Evaluation Guidelines",
    "",
    "**Generated**: {} (Asia/Shanghai)".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
    "**Data Source**: 70 guideline documents from /graphify-out/converted/",
    "",
    "## 1. Graph Overview",
    "",
    "- **Total Entity Nodes**: {}".format(G.number_of_nodes()),
    "- **Total Semantic Relations**: {}".format(G.number_of_edges()),
    "- **Community Clusters**: {}".format(len(communities)),
    "- **Largest Community**: {} nodes, {} edges".format(comm_summaries[0]['size'], comm_summaries[0]['edges']),
    "",
    "## 2. High-Degree Core Entities (Top 30)",
    "",
]
for nid, deg in top_nodes_by_degree[:30]:
    ntype = node_type(nid)
    label = node_label(nid)
    comm = node_community.get(nid, -1)
    report_lines.append("- **{}** ({}) - Degree {}, Community #{}".format(label, ntype, deg, comm))

report_lines += ["", "## 3. Community Cluster Details", ""]

for idx, cs in enumerate(comm_summaries[:20]):
    report_lines.append("### Community #{} (#{})".format(idx, cs['id']))
    report_lines.append("- Size: {} nodes, {} edges".format(cs['size'], cs['edges']))
    report_lines.append("- Cohesion: {:.4f}".format(cs['cohesion']))
    report_lines.append("- Type distribution: {}".format(json.dumps(cs['types'], ensure_ascii=False)))
    report_lines.append("- Top nodes:")
    for nid, deg in cs['top_nodes'][:10]:
        report_lines.append("  - {} ({})".format(node_label(nid), deg))
    report_lines.append("")

report_lines += ["", "## 4. Entity Type Distribution", ""]
type_stats = defaultdict(lambda: {'count': 0, 'total_degree': 0})
for nid in G.nodes():
    t = node_type(nid)
    type_stats[t]['count'] += 1
    type_stats[t]['total_degree'] += degree_dict.get(nid, 0)

for t, stats in sorted(type_stats.items(), key=lambda x: x[1]['count'], reverse=True):
    avg_deg = stats['total_degree'] / stats['count'] if stats['count'] > 0 else 0
    report_lines.append("- **{}**: {} entities, avg degree {:.1f}".format(t, stats['count'], avg_deg))

report_lines += ["", "## 5. Key Relation Types", ""]
edge_labels = defaultdict(int)
for u, v, d in G.edges(data=True):
    rel = d.get('relation', d.get('label', 'related_to'))
    edge_labels[rel] += 1

for rel, cnt in sorted(edge_labels.items(), key=lambda x: x[1], reverse=True)[:20]:
    report_lines.append("- **{}**: {} relations".format(rel, cnt))

report_lines += ["", "---", "*Generated by graphify pipeline · {}*".format(ts)]

with open(report_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(report_lines))
print("  Saved report: {}".format(report_path))

shutil.copy(report_path, source_dir / "GRAPH_REPORT_anshang_semantic_cron_latest.md")

print("\n=== Pipeline Complete ===")
print("HTML: {}".format(html_path))
print("JSON: {}".format(json_out_path))
print("REPORT: {}".format(report_path))
