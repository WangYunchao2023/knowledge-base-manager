#!/usr/bin/env python3
"""Graphify pipeline for 安评 - cron run."""
import json, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import networkx as nx

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
output_dir = Path("/home/wangyc/Documents/工作/法规指导原则/安评/graphify-out")

# Load semantic
print("Loading semantic data...")
with open("/tmp/.graphify_semantic.json") as f:
    semantic_data = json.load(f)
nodes = semantic_data.get("nodes", [])
edges = semantic_data.get("edges", [])
print(f"  Nodes: {len(nodes)}, Edges: {len(edges)}")

# Build graph
print("Building graph...")
G = nx.Graph()
for node in nodes:
    nid = node.get("id") or node.get("name")
    if not nid:
        continue
    nid = str(nid)
    attrs = {k: v for k, v in node.items() if k != "id"}
    G.add_node(nid, **attrs)
for edge in edges:
    src = str(edge.get("source") or edge.get("from") or edge.get("src") or "")
    tgt = str(edge.get("target") or edge.get("to") or edge.get("dst") or "")
    if not src or not tgt:
        continue
    attrs = {k: v for k, v in edge.items() if k not in ("source", "target", "from", "to", "src", "dst")}
    G.add_edge(src, tgt, **attrs)
print(f"  Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# Cluster
print("Clustering...")
try:
    from networkx.algorithms.community import louvain_communities
    communities = louvain_communities(G, resolution=1.0, seed=42)
    communities = [list(c) for c in communities]
except Exception as e:
    print(f"  Louvain failed: {e}")
    communities = [list(c) for c in nx.connected_components(G)]
print(f"  Communities: {len(communities)}")

# Analytics
degree_dict = dict(G.degree())
node_community = {}
for i, comm in enumerate(communities):
    for node in comm:
        node_community[node] = i

cohesion_scores = {}
for i, comm in enumerate(communities):
    if len(comm) < 2:
        cohesion_scores[i] = 0.0
    else:
        sg = G.subgraph(comm)
        possible = len(comm) * (len(comm) - 1) / 2
        actual = sg.number_of_edges()
        cohesion_scores[i] = round(actual / possible, 3) if possible > 0 else 0.0

for nid in G.nodes:
    G.nodes[nid]["degree"] = degree_dict.get(nid, 0)
    G.nodes[nid]["label"] = nid
    G.nodes[nid]["community"] = node_community.get(nid, -1)

def summarize(comm_id, node_list):
    tc = defaultdict(int)
    for n in node_list:
        tc[G.nodes[n].get("type", "concept")] += 1
    top_types = dict(sorted(tc.items(), key=lambda x: x[1], reverse=True)[:8])
    top_deg = sorted([(n, degree_dict.get(n, 0)) for n in node_list], key=lambda x: x[1], reverse=True)
    top_nodes = [n for n, _ in top_deg[:8]]
    return {
        "id": comm_id,
        "size": len(node_list),
        "top_types": top_types,
        "top_nodes": top_nodes,
        "edge_count": G.subgraph(node_list).number_of_edges(),
        "cohesion": cohesion_scores.get(comm_id, 0.0),
    }

comm_summaries = sorted([summarize(i, c) for i, c in enumerate(communities)], key=lambda x: x["size"], reverse=True)

# Save JSON
graph_data = {
    "nodes": [{"id": n, **dict(G.nodes[n])} for n in G.nodes],
    "edges": [{"source": u, "target": v, **dict(d)} for u, v, d in G.edges(data=True)],
    "communities": comm_summaries[:20],
    "metadata": {"timestamp": ts, "nodes": G.number_of_nodes(), "edges": G.number_of_edges(), "communities": len(communities)},
}
json_out = output_dir / f"graph_anshang_{ts}.json"
with open(json_out, "w", encoding="utf-8") as f:
    json.dump(graph_data, f, ensure_ascii=False)
(output_dir / "graph_anshang_latest.json").write_text(json.dumps(graph_data, ensure_ascii=False), encoding="utf-8")
print(f"Saved JSON: {json_out.name}")

# HTML
print("Generating HTML...")
colors = ["#4A90D9","#D94A4A","#4AD94A","#D9D94A","#4AD9D9","#D94AD9","#4A4AD9","#D98A4A","#4AD98A","#8A4AD9","#D94A8A","#4AD9D9","#D9D94A","#94D94A","#4A94D9","#9A4AD9","#4AD9A9","#D9A94A","#A94AD9","#D9A9A9"]
comm_legend = []
for cs in comm_summaries[:15]:
    c = colors[cs["id"] % len(colors)]
    tns = ", ".join(cs["top_nodes"][:3])
    comm_legend.append('<div class="comm-item" style="border-left:3px solid %s"><div class="comm-title">社区%d <span style="color:#8b949e">(%d节点, 凝聚度%.3f)</span></div><div class="comm-meta">%s</div></div>' % (c, cs["id"], cs["size"], cs["cohesion"], tns))

nj = json.dumps([{"id": n, **dict(G.nodes[n])} for n in G.nodes], ensure_ascii=False)
ej = json.dumps([{"source": u, "target": v, **dict(d)} for u, v, d in G.edges(data=True)], ensure_ascii=False)
cj = json.dumps(colors)
csj = json.dumps(comm_summaries, ensure_ascii=False)

html_chunks = [
    '<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><title>安评知识图谱 - ', ts, '</title><script src="https://d3js.org/d3.v7.min.js"></script>',
    '<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0d1117;color:#e6edf3;overflow:hidden}#graph{width:100vw;height:100vh}.node{cursor:pointer}.node-label{font-size:9px;fill:#e6edf3;pointer-events:none}.link{stroke-opacity:0.35;stroke:#555}.tooltip{position:absolute;background:#161b22;border:1px solid #30363d;padding:8px 12px;border-radius:6px;font-size:13px;max-width:320px;pointer-events:none;opacity:0;transition:opacity 0.2s;z-index:10;color:#e6edf3}.tooltip.visible{opacity:1}.tooltip .type{color:#58a6ff;font-size:11px}.tooltip .file{color:#8b949e;font-size:11px;margin-top:4px}#sidebar{position:absolute;top:10px;right:10px;width:320px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:15px;max-height:90vh;overflow-y:auto;z-index:5}#sidebar h3{color:#58a6ff;margin-bottom:12px;font-size:14px}.comm-item{margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid #30363d}.comm-title{font-weight:bold;font-size:13px;margin-bottom:3px}.comm-meta{font-size:11px;color:#8b949e}#stats{position:absolute;top:10px;left:10px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;font-size:12px;z-index:5}#stats span{color:#58a6ff;font-weight:bold}#controls{position:absolute;bottom:10px;left:10px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;font-size:12px;z-index:5}#controls button{background:#238636;border:none;color:#fff;padding:4px 10px;border-radius:4px;cursor:pointer;margin-right:5px}#controls button:hover{background:#2ea043}</style>',
    '</head><body><div id="graph"></div><div id="tooltip" class="tooltip"></div><div id="sidebar"><h3>社区聚类 (共' + str(len(communities)) + '个)</h3>' + "\n".join(comm_legend) + '</div><div id="stats"><div>节点 <span>' + str(G.number_of_nodes()) + '</span> | 边 <span>' + str(G.number_of_edges()) + '</span> | 社区 <span>' + str(len(communities)) + '</span></div></div><div id="controls"><button onclick="resetZoom()">重置视图</button><button onclick="toggleLabels()">切换标签</button></div>',
    '<script>const nodes=' + nj + ';const edges=' + ej + ';const colors=' + cj + ';const communities=' + csj + ';const width=window.innerWidth,height=window.innerHeight;const svg=d3.select("#graph").append("svg").attr("width",width).attr("height",height);const g=svg.append("g");const simulation=d3.forceSimulation(nodes).force("link",d3.forceLink(edges).id(function(d){return d.id;}).distance(60).strength(0.3)).force("charge",d3.forceManyBody().strength(-80)).force("center",d3.forceCenter(width/2,height/2)).force("collision",d3.forceCollide(8));const link=g.append("g").selectAll("line").data(edges).join("line").attr("class","link").attr("stroke","#555").attr("stroke-width",function(d){return Math.max(0.5,(d.weight||1)*1.5);});const node=g.append("g").selectAll("circle").data(nodes).join("circle").attr("r",function(d){return Math.min(12,4+(d.degree||0)*0.3);}).attr("fill",function(d){return colors[d.community%%colors.length];}).attr("class","node").call(d3.drag().on("start",function(e,d){if(!e.active)simulation.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y;}).on("drag",function(e,d){d.fx=e.x;d.fy=e.y;}).on("end",function(e,d){if(!e.active)simulation.alphaTarget(0);d.fx=null;d.fy=null;}));const label=g.append("g").selectAll("text").data(nodes).join("text").attr("class","node-label").text(function(d){return d.label||d.id;}).attr("text-anchor","middle").attr("dy",function(d){return (Math.min(12,4+(d.degree||0)*0.3))+4;}).style("display","none");const tooltip=d3.select("#tooltip");node.on("mouseover",function(e,d){var t=d.type||"concept";var l=d.label||d.id;var f=d.source_file||"";tooltip.classed("visible",true).html("<div class=\'type\'>"+t+"</div><div>"+l+"</div><div class=\'file\'>"+f+"</div><div>度数:"+d.degree+" 社区:"+d.community+"</div>");}).on("mousemove",function(e){tooltip.style("left",(e.pageX+15)+"px").style("top",(e.pageY-10)+"px");}).on("mouseout",function(){tooltip.classed("visible",false);});simulation.on("tick",function(){link.attr("x1",function(d){return d.source.x;}).attr("y1",function(d){return d.source.y;}).attr("x2",function(d){return d.target.x;}).attr("y2",function(d){return d.target.y;});node.attr("cx",function(d){return d.x;}).attr("cy",function(d){return d.y;});label.attr("x",function(d){return d.x;}).attr("y",function(d){return d.y;});});function resetZoom(){g.attr("transform",d3.zoomIdentity);}var showLabels=false;function toggleLabels(){showLabels=!showLabels;label.style("display",showLabels?"block":"none");}svg.call(d3.zoom().scaleExtent([0.05,4]).on("zoom",function(e){g.attr("transform",e.transform);}));</script></body></html>',
]

html = "".join(html_chunks)
html_out = output_dir / f"知识图谱_anshang_{ts}.html"
with open(html_out, "w", encoding="utf-8") as f:
    f.write(html)
(output_dir / "知识图谱_anshang_latest.html").write_text(html, encoding="utf-8")
print(f"Saved HTML: {html_out.name}")

# GRAPH_REPORT
print("Generating GRAPH_REPORT.md...")
top20 = sorted(degree_dict.items(), key=lambda x: x[1], reverse=True)[:20]
avg_deg = round(sum(degree_dict.values()) / max(1, len(degree_dict)), 2)
max_deg = max(degree_dict.values()) if degree_dict else 0

lines = []
lines.append("# 安评知识图谱分析报告\n")
lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}  \n")
lines.append("**数据来源**: /home/wangyc/Documents/工作/法规指导原则/安评\n\n")
lines.append("---\n\n## 概览\n\n")
lines.append("| 指标 | 数值 |\n|------|------|\n")
lines.append(f"| 节点总数 | {G.number_of_nodes()} |\n")
lines.append(f"| 边总数 | {G.number_of_edges()} |\n")
lines.append(f"| 社区数 | {len(communities)} |\n")
lines.append(f"| 平均度数 | {avg_deg} |\n")
lines.append(f"| 最高度数 | {max_deg} |\n\n")
lines.append("---\n\n## Top 20 核心节点（按度数）\n\n")
lines.append("| 排名 | 节点 | 类型 | 度数 |\n|------|------|------|------|\n")
for rank, (nid, deg) in enumerate(top20, 1):
    t = G.nodes[n_id].get("type", "concept")
    lines.append(f"| {rank} | {n_id} | {t} | {deg} |\n")
lines.append("\n---\n\n## 社区详情\n\n")
for cs in comm_summaries[:20]:
    type_str = ", ".join([f"{k}({v})" for k, v in list(cs["top_types"].items())[:5]])
    lines.append(f"### 社区 {cs['id']}（{cs['size']}节点，凝聚度 {cs['cohesion']:.3f}）\n\n")
    lines.append(f"- **类型分布**: {type_str}\n")
    lines.append(f"- **核心节点**: {', '.join(cs['top_nodes'][:5])}\n")
    lines.append(f"- **边数**: {cs['edge_count']}\n\n")

file_nodes = defaultdict(list)
for n in nodes:
    sf = n.get("source_file", "")
    if sf:
        file_nodes[sf].append(n.get("label", n.get("id", "")))
lines.append("---\n\n## 输入文件统计\n\n")
for sf, labels in sorted(file_nodes.items()):
    lines.append(f"- **{sf}**: {len(labels)} 实体\n")
lines.append(f"\n---\n*由 graphify 管道自动生成 | {ts}*\n")

report = "".join(lines)
rep_out = output_dir / f"GRAPH_REPORT_anshang_{ts}.md"
with open(rep_out, "w", encoding="utf-8") as f:
    f.write(report)
(output_dir / "GRAPH_REPORT_anshang_latest.md").write_text(report, encoding="utf-8")
print(f"Saved Report: {rep_out.name}")

# DONE
with open("/tmp/.graphify_done.txt", "w") as f:
    f.write("DONE")
print("DONE marker written to /tmp/.graphify_done.txt")
print("Pipeline complete!")
