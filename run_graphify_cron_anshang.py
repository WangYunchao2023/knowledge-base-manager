#!/usr/bin/env python3
"""Full graphify pipeline for 安评 - anshang semantic cron - 20260416"""
import os, json, sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

print("=== Full Graphify Pipeline for 安评 (cron final) ===")
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
nodes = semantic_data.get('nodes', [])
edges = semantic_data.get('edges', [])
print(f"  Semantic: {len(nodes)} nodes, {len(edges)} edges")

# Step 3: Build graph
print("\n[Step 3] Building graph...")
import networkx as nx
G = nx.Graph()
for node in nodes:
    nid = node.get('id') or node.get('name') or ''
    if not nid:
        continue
    attrs = {k: v for k, v in node.items() if k != 'id'}
    G.add_node(nid, **attrs)
for edge in edges:
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
print(f"  Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# Step 4: Cluster
print("\n[Step 4] Clustering...")
try:
    from networkx.algorithms.community import louvain_communities
    communities = louvain_communities(G, resolution=1.0, seed=42)
    communities = [list(c) for c in communities]
except Exception as e:
    print(f"  Louvain failed: {e}")
    communities = [list(c) for c in nx.connected_components(G)]
print(f"  Communities: {len(communities)}")

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

def node_label(nid):
    return G.nodes[nid].get('label', G.nodes[nid].get('name', nid))

def node_type(nid):
    return G.nodes[nid].get('type', G.nodes[nid].get('entity_type', 'concept'))

# Step 5: Compute statistics
print("\n[Step 5] Analyzing...")
degree_dict = dict(G.degree())
top_nodes_by_degree = sorted(degree_dict.items(), key=lambda x: x[1], reverse=True)[:50]
print(f"  Top node: {node_label(top_nodes_by_degree[0][0])} ({top_nodes_by_degree[0][1]} degree)")

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
        'edge_count': subgraph.number_of_edges(),
        'cohesion': cohesion_scores[i],
        'top_types': dict(sorted(type_counter.items(), key=lambda x: x[1], reverse=True)),
        'top_nodes': [node_label(nid) for nid, _ in node_degrees[:8]],
        'nodes': [nid for nid, _ in node_degrees],
    })
comm_summaries.sort(key=lambda x: x['size'], reverse=True)
for cs in comm_summaries[:10]:
    print(f"  Community {cs['id']}: {cs['size']} nodes, cohesion={cs['cohesion']}")
    print(f"    Top: {', '.join(cs['top_nodes'][:3])}")

# Step 6: Save JSON
print("\n[Step 6] Saving graph JSON...")
graph_data = {'nodes': [], 'edges': []}
for nid in G.nodes():
    ndata = dict(G.nodes[nid])
    ndata['id'] = nid
    ndata['community'] = node_community.get(nid, -1)
    ndata['degree'] = degree_dict.get(nid, 0)
    graph_data['nodes'].append(ndata)
for u, v in G.edges():
    edata = dict(G.edges[u, v])
    edata['source'] = u
    edata['target'] = v
    graph_data['edges'].append(edata)

json_out = output_dir / ("graph_anshang_%s.json" % ts)
with open(json_out, 'w', encoding='utf-8') as f:
    json.dump(graph_data, f, ensure_ascii=False, indent=2)
(output_dir / "graph_anshang_latest.json").write_text(json.dumps(graph_data, ensure_ascii=False), encoding='utf-8')
print(f"  Saved: {json_out.name}")

json_out2 = output_dir / ("graph_安评_anshang_semantic_cron_%s.json" % ts)
with open(json_out2, 'w', encoding='utf-8') as f:
    json.dump(graph_data, f, ensure_ascii=False, indent=2)
(output_dir / "graph_安评_anshang_semantic_cron_latest.json").write_text(json.dumps(graph_data, ensure_ascii=False), encoding='utf-8')
print(f"  Saved: graph_安评_anshang_semantic_cron_{ts}.json")

# Step 7: Generate HTML
print("\n[Step 7] Generating HTML...")
nodes_j = json.dumps(graph_data['nodes'], ensure_ascii=False)
edges_j = json.dumps(graph_data['edges'], ensure_ascii=False)
colors_list = ["#4A90D9","#D94A4A","#4AD94A","#D9D94A","#4AD9D9","#D94AD9","#4A4AD9","#D98A4A","#4AD98A","#8A4AD9","#D94A8A","#4AD9D9","#D9D94A","#94D94A","#4A94D9","#9A4AD9","#4AD9A9","#D9A94A","#A94AD9","#D9A9A9"]
colors_j = json.dumps(colors_list)
coh_j = json.dumps(cohesion_scores)

comm_legend_items = []
for cs in comm_summaries[:15]:
    color = colors_list[cs['id'] % len(colors_list)]
    top_nodes_str = ', '.join(cs['top_nodes'][:3])
    comm_legend_items.append(
        '<div class="comm-item" style="border-left:3px solid %s">'
        '<div class="comm-title">社区%d <span style="color:#8b949e">(%d节点, 凝聚度%.3f)</span></div>'
        '<div class="comm-meta">%s</div></div>'
        % (color, cs['id'], cs['size'], cs['cohesion'], top_nodes_str)
    )
comm_legend_html = '\n'.join(comm_legend_items)

html = '''<!DOCTYPE html>
<html lang="zh"><head><meta charset="UTF-8">
<title>安评知识图谱 - anshang_semantic_cron - ''' + ts + '''</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0d1117;color:#e6edf3;overflow:hidden}
#graph{width:100vw;height:100vh}
.node{cursor:pointer}
.node-label{font-size:9px;fill:#e6edf3;pointer-events:none}
.link{stroke-opacity:0.35;stroke:#555}
.tooltip{position:absolute;background:#161b22;border:1px solid #30363d;padding:8px 12px;border-radius:6px;font-size:13px;max-width:320px;pointer-events:none;opacity:0;transition:opacity 0.2s;z-index:10;color:#e6edf3}
.tooltip.visible{opacity:1}
.tooltip .type{color:#58a6ff;font-size:11px}
.tooltip .file{color:#8b949e;font-size:11px;margin-top:4px}
#sidebar{position:absolute;top:10px;right:10px;width:320px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:15px;max-height:90vh;overflow-y:auto;z-index:5}
#sidebar h3{color:#58a6ff;margin-bottom:12px;font-size:14px}
.comm-item{margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid #30363d}
.comm-title{font-weight:bold;font-size:13px;margin-bottom:3px}
.comm-meta{font-size:11px;color:#8b949e}
#stats{position:absolute;top:10px;left:10px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;font-size:12px;z-index:5}
#stats span{color:#58a6ff;font-weight:bold}
#controls{position:absolute;bottom:10px;left:10px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;font-size:12px;z-index:5}
#controls button{background:#238636;border:none;color:#fff;padding:4px 10px;border-radius:4px;cursor:pointer;margin-right:5px}
#controls button:hover{background:#2ea043}
</style>
</head><body>
<div id="graph"></div>
<div id="tooltip" class="tooltip"></div>
<div id="sidebar">
<h3>社区聚类 (共%d个社区)</h3>%s
</div>
<div id="stats">
<div>节点 <span>%d</span> | 边 <span>%d</span> | 社区 <span>%d</span></div>
</div>
<div id="controls">
<button onclick="resetZoom()">重置视图</button>
<button onclick="toggleLabels()">切换标签</button>
</div>
<script>
const nodes=%s;
const edges=%s;
const colors=%s;
const cohesion=%s;
const communities=%s;
const width=window.innerWidth,height=window.innerHeight;
const svg=d3.select("#graph").append("svg").attr("width",width).attr("height",height);
const g=svg.append("g");
const simulation=d3.forceSimulation(nodes)
  .force("link",d3.forceLink(edges).id(function(d){return d.id;}).distance(60).strength(0.3))
  .force("charge",d3.forceManyBody().strength(-80))
  .force("center",d3.forceCenter(width/2,height/2))
  .force("collision",d3.forceCollide(8));
const link=g.append("g").selectAll("line").data(edges).join("line")
  .attr("class","link").attr("stroke","#555")
  .attr("stroke-width",function(d){return Math.max(0.5,(d.weight||1)*1.5);});
const node=g.append("g").selectAll("circle").data(nodes).join("circle")
  .attr("r",function(d){return Math.min(12,4+(d.degree||0)*0.3);})
  .attr("fill",function(d){return colors[d.community%%colors.length];})
  .attr("class","node")
  .call(d3.drag().on("start",function(e,d){if(!e.active) simulation.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y;})
    .on("drag",function(e,d){d.fx=e.x;d.fy=e.y;})
    .on("end",function(e,d){if(!e.active) simulation.alphaTarget(0);d.fx=null;d.fy=null;}));
const label=g.append("g").selectAll("text").data(nodes).join("text")
  .attr("class","node-label").text(function(d){return d.label||d.id;})
  .attr("text-anchor","middle")
  .attr("dy",function(d){return (Math.min(12,4+(d.degree||0)*0.3))+4;})
  .style("display","none");
const tooltip=d3.select("#tooltip");
node.on("mouseover",function(e,d){
  var t=d.type||"concept";
  var l=d.label||d.id;
  var f=d.source_file||"";
  tooltip.classed("visible",true).html("<div class='type'>"+t+"</div><div>"+l+"</div><div class='file'>"+f+"</div><div>度数:"+d.degree+" 社区:"+d.community+"</div>");
}).on("mousemove",function(e){tooltip.style("left",(e.pageX+15)+"px").style("top",(e.pageY-10)+"px");})
  .on("mouseout",function(){tooltip.classed("visible",false);});
simulation.on("tick",function(){
  link.attr("x1",function(d){return d.source.x;}).attr("y1",function(d){return d.source.y;})
      .attr("x2",function(d){return d.target.x;}).attr("y2",function(d){return d.target.y;});
  node.attr("cx",function(d){return d.x;}).attr("cy",function(d){return d.y;});
  label.attr("x",function(d){return d.x;}).attr("y",function(d){return d.y;});
});
function resetZoom(){g.attr("transform",d3.zoomIdentity);}
var showLabels=false;
function toggleLabels(){showLabels=!showLabels;label.style("display",showLabels?"block":"none");}
svg.call(d3.zoom().scaleExtent([0.05,4]).on("zoom",function(e){g.attr("transform",e.transform);}));
</script></body></html>''' % (
    len(communities), comm_legend_html,
    G.number_of_nodes(), G.number_of_edges(), len(communities),
    nodes_j, edges_j, colors_j, coh_j,
    json.dumps(comm_summaries, ensure_ascii=False)
)

html_out = output_dir / ("知识图谱_安评_anshang_semantic_cron_%s.html" % ts)
with open(html_out, 'w', encoding='utf-8') as f:
    f.write(html)
(output_dir / "知识图谱_安评_anshang_semantic_cron_latest.html").write_text(html, encoding='utf-8')
print(f"  Saved: 知识图谱_安评_anshang_semantic_cron_{ts}.html")

# Step 8: GRAPH_REPORT.md
print("\n[Step 8] Generating GRAPH_REPORT.md...")
avg_deg = round(sum(degree_dict.values()) / max(1, len(degree_dict)), 2)
max_deg = max(degree_dict.values()) if degree_dict else 0

report_lines = []
report_lines.append('# 安评知识图谱分析报告\n')
report_lines.append('**生成时间**: %s  \n' % datetime.now().strftime("%Y-%m-%d %H:%M"))
report_lines.append('**数据来源**: %s\n' % str(source_dir))
report_lines.append('**管道**: anshang_semantic_cron | **数据源**: /tmp/.graphify_semantic.json\n')
report_lines.append('\n---\n## 概览\n| 指标 | 数值 |\n|------|------|\n')
report_lines.append('| 节点总数 | %d |\n| 边总数 | %d |\n| 社区数 | %d |\n' % (G.number_of_nodes(), G.number_of_edges(), len(communities)))
report_lines.append('| 平均度数 | %s |\n| 最高度数 | %d |\n\n---\n' % (avg_deg, max_deg))
report_lines.append('## Top 20 核心节点（按度数）\n| 排名 | 节点 | 类型 | 度数 |\n|------|------|------|------|\n')
for rank, (nid, deg) in enumerate(top_nodes_by_degree[:20], 1):
    lbl = node_label(nid).replace('|', '\\|')
    typ = node_type(nid)
    report_lines.append('| %d | %s | %s | %d |\n' % (rank, lbl, typ, deg))
report_lines.append('\n---\n## 社区详情\n')
for rank, cs in enumerate(comm_summaries[:20], 1):
    type_str = ', '.join(['%s(%d)' % (k, v) for k, v in list(cs['top_types'].items())[:5]])
    report_lines.append('### 社区 %d（%d节点，凝聚度 %.3f）\n\n' % (cs['id'], cs['size'], cs['cohesion']))
    report_lines.append('- **类型分布**: %s\n' % type_str)
    report_lines.append('- **核心节点**: %s\n' % ', '.join(cs['top_nodes'][:5]))
    report_lines.append('- **边数**: %d\n\n' % cs['edge_count'])
report_lines.append('---\n## 输入文件统计\n')
file_nodes = defaultdict(list)
for n in nodes:
    sf = n.get('source_file', '')
    if sf:
        file_nodes[sf].append(n.get('label', n.get('id', '')))
for sf, labels in sorted(file_nodes.items()):
    report_lines.append('- **%s**: %d 实体\n' % (sf, len(labels)))
report_lines.append('\n---\n*由 graphify 管道自动生成 | %s*\n' % ts)

report = ''.join(report_lines)
report_out = output_dir / ("GRAPH_REPORT_安评_anshang_semantic_cron_%s.md" % ts)
with open(report_out, 'w', encoding='utf-8') as f:
    f.write(report)
(output_dir / "GRAPH_REPORT_安评_anshang_semantic_cron_latest.md").write_text(report, encoding='utf-8')
print(f"  Saved: GRAPH_REPORT_安评_anshang_semantic_cron_{ts}.md")

# Step 9: DONE marker
print("\n[Step 9] Writing DONE marker...")
with open('/tmp/.graphify_done.txt', 'w') as f:
    f.write('DONE')
print("\n=== Pipeline Complete ===")
print(f"  Graph: graph_anshang_{ts}.json")
print(f"  Graph2: graph_安评_anshang_semantic_cron_{ts}.json")
print(f"  HTML:  知识图谱_安评_anshang_semantic_cron_{ts}.html")
print(f"  Report: GRAPH_REPORT_安评_anshang_semantic_cron_{ts}.md")
print(f"  DONE: /tmp/.graphify_done.txt")
