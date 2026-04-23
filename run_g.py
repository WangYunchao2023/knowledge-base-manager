#!/usr/bin/env python3
import sys, json, re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ts = datetime.now().strftime('%Y%m%d_%H%M%S')
source_dir = Path('/home/wangyc/Documents/工作/法规指导原则/安评')
converted_dir = source_dir / 'graphify-out/converted'
output_dir = source_dir / 'graphify-out'

print('=== Pipeline ===')

md_files = sorted(converted_dir.glob('*.md'))
print(f'Found {len(md_files)} md files')

det = {'files': [{'path': str(f)} for f in md_files]}
with open('/tmp/.graphify_detect_anshang.json', 'w', encoding='utf-8') as f:
    json.dump(det, f, ensure_ascii=False, indent=2)
print('Detection saved')

# Use existing semantic.json
with open('/tmp/.graphify_semantic.json') as f:
    sd = json.load(f)
nodes = sd['nodes']
edges = sd['edges']
print(f'Loaded: {len(nodes)} nodes, {len(edges)} edges')

import networkx as nx
G = nx.Graph()
for node in nodes:
    nid = node.get('id') or ''
    if not nid: continue
    attrs = {k:v for k,v in node.items() if k != 'id'}
    G.add_node(nid, **attrs)
for edge in edges:
    src = edge.get('source','')
    tgt = edge.get('target','')
    if not src or not tgt: continue
    if src not in G: G.add_node(src)
    if tgt not in G: G.add_node(tgt)
    attrs = {k:v for k,v in edge.items() if k not in ('source','target')}
    G.add_edge(src, tgt, **attrs)

print(f'Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges')

# Louvain clustering
from networkx.algorithms.community import louvain_communities
communities = louvain_communities(G, resolution=1.0, seed=42)
communities = [list(c) for c in communities]
print(f'Communities: {len(communities)}')

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

def nlabel(nid):
    return G.nodes[nid].get('label', nid) if nid in G else str(nid)
def ntype(nid):
    return G.nodes[nid].get('type', 'concept') if nid in G else 'concept'

degree_dict = dict(G.degree())
top_nodes = sorted(degree_dict.items(), key=lambda x: x[1], reverse=True)

comm_summaries = []
for i, comm in enumerate(communities):
    sg = G.subgraph(comm)
    tc = defaultdict(int)
    for nid in comm:
        tc[ntype(nid)] += 1
    nd = [(nid, G.degree(nid)) for nid in comm]
    nd.sort(key=lambda x: x[1], reverse=True)
    comm_summaries.append({
        'id': i, 'size': len(comm), 'edge_count': sg.number_of_edges(),
        'cohesion': cohesion_scores[i],
        'top_types': dict(sorted(tc.items(), key=lambda x: x[1], reverse=True)),
        'top_nodes': [nlabel(nid) for nid, _ in nd[:8]],
        'nodes': [nid for nid, _ in nd],
    })
comm_summaries.sort(key=lambda x: x['size'], reverse=True)
for cs in comm_summaries[:10]:
    print(f'  C{cs["id"]}: {cs["size"]} nodes, coh={cs["cohesion"]}, top={", ".join(cs["top_nodes"][:3])}')

# Save graph JSON
graph_data = {'nodes': [], 'edges': []}
for nid in G.nodes():
    nd = dict(G.nodes[nid])
    nd['id'] = nid
    nd['community'] = node_community.get(nid, -1)
    nd['degree'] = degree_dict.get(nid, 0)
    graph_data['nodes'].append(nd)
for u, v in G.edges():
    ed = dict(G.edges[u, v])
    ed['source'] = u
    ed['target'] = v
    graph_data['edges'].append(ed)

jout = output_dir / f'graph_anshang_{ts}.json'
with open(jout, 'w', encoding='utf-8') as f:
    json.dump(graph_data, f, ensure_ascii=False, indent=2)
(output_dir / 'graph_anshang_latest.json').write_text(json.dumps(graph_data, ensure_ascii=False), encoding='utf-8')
print(f'Saved graph JSON: {jout.name}')

# Generate HTML
nj = json.dumps(graph_data['nodes'], ensure_ascii=False)
ej = json.dumps(graph_data['edges'], ensure_ascii=False)
colors = ["#4A90D9","#D94A4A","#4AD94A","#D9D94A","#4AD9D9","#D94AD9","#4A4AD9","#D98A4A","#4AD98A","#8A4AD9","#D94A8A","#94D94A","#4A94D9","#9A4AD9","#4AD9A9","#D9A94A","#A94AD9"]
cj = json.dumps(colors)
cohj = json.dumps(cohesion_scores)

ci = []
for cs in comm_summaries[:15]:
    color = colors[cs['id'] % len(colors)]
    ci.append(f'<div class="comm-item" style="border-left:3px solid {color}"><div class="comm-title">社区{cs["id"]} <span style="color:#8b949e">({cs["size"]}节点, 凝聚度{cs["cohesion"]:.3f})</span></div><div class="comm-meta">{", ".join(cs["top_nodes"][:3])}</div></div>')
ch = '\n'.join(ci)

html = f'''<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><title>安评知识图谱 - {ts}</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0d1117;color:#e6edf3;overflow:hidden}}
#graph{{width:100vw;height:100vh}}
.node-label{{font-size:9px;fill:#e6edf3;pointer-events:none}}
.link{{stroke-opacity:0.3;stroke:#555}}
.tooltip{{position:absolute;background:#161b22;border:1px solid #30363d;padding:8px 12px;border-radius:6px;font-size:13px;max-width:320px;pointer-events:none;opacity:0;transition:opacity 0.2s;z-index:10;color:#e6edf3}}
.tooltip.visible{{opacity:1}}
.tooltip .type{{color:#58a6ff;font-size:11px}}
.tooltip .file{{color:#8b949e;font-size:11px;margin-top:4px}}
#sidebar{{position:absolute;top:10px;right:10px;width:320px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:15px;max-height:90vh;overflow-y:auto;z-index:5}}
#sidebar h3{{color:#58a6ff;margin-bottom:12px;font-size:14px}}
.comm-item{{margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid #30363d}}
.comm-title{{font-weight:bold;font-size:13px;margin-bottom:3px}}
.comm-meta{{font-size:11px;color:#8b949e}}
#stats{{position:absolute;top:10px;left:10px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;font-size:12px;z-index:5}}
#stats span{{color:#58a6ff;font-weight:bold}}
#controls{{position:absolute;bottom:10px;left:10px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;font-size:12px;z-index:5}}
#controls button{{background:#238636;border:none;color:#fff;padding:4px 10px;border-radius:4px;cursor:pointer;margin-right:5px}}
#controls button:hover{{background:#2ea043}}
</style></head><body>
<div id="graph"></div>
<div id="tooltip" class="tooltip"></div>
<div id="sidebar"><h3>社区聚类 (共{len(communities)}个社区)</h3>{ch}</div>
<div id="stats"><div>节点 <span>{G.number_of_nodes()}</span> | 边 <span>{G.number_of_edges()}</span> | 社区 <span>{len(communities)}</span></div></div>
<div id="controls"><button onclick="resetZoom()">重置视图</button><button onclick="toggleLabels()">切换标签</button></div>
<script>
const nodes={nj};const edges={ej};const colors={cj};const cohesion={cohj};const communities={json.dumps(comm_summaries, ensure_ascii=False)};
const width=window.innerWidth,height=window.innerHeight;
const svg=d3.select("#graph").append("svg").attr("width",width).attr("height",height);
const g=svg.append("g");
const simulation=d3.forceSimulation(nodes)
.force("link",d3.forceLink(edges).id(function(d){{return d.id;}}).distance(60).strength(0.3))
.force("charge",d3.forceManyBody().strength(-80))
.force("center",d3.forceCenter(width/2,height/2))
.force("collision",d3.forceCollide(8));
const link=g.append("g").selectAll("line").data(edges).join("line").attr("class","link").attr("stroke","#555").attr("stroke-width",function(d){{return Math.max(0.5,(d.weight||1)*1.5);}});
const node=g.append("g").selectAll("circle").data(nodes).join("circle")
.attr("r",function(d){{return Math.min(12,4+(d.degree||0)*0.3);}})
.attr("fill",function(d){{return colors[d.community %% colors.length];}})
.attr("class","node")
.call(d3.drag().on("start",function(e,d){{if(!e.active) simulation.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y;}})
.on("drag",function(e,d){{d.fx=e.x;d.fy=e.y;}})
.on("end",function(e,d){{if(!e.active) simulation.alphaTarget(0);d.fx=null;d.fy=null;}})));
const label=g.append("g").selectAll("text").data(nodes).join("text").attr("class","node-label").text(function(d){{return d.label||d.id;}}).attr("text-anchor","middle").attr("dy",function(d){{return (Math.min(12,4+(d.degree||0)*0.3))+4;}}).style("display","none");
const tooltip=d3.select("#tooltip");
node.on("mouseover",function(e,d){{tooltip.classed("visible",true).html("<div class='type'>"+(d.type||"concept")+"</div><div>"+(d.label||d.id)+"</div><div class='file'>"+(d.source_file||"")+"</div><div>度数:"+d.degree+" 社区:"+d.community+"</div>");}})
.on("mousemove",function(e){{tooltip.style("left",(e.pageX+15)+"px").style("top",(e.pageY-10)+"px");}})
.on("mouseout",function(){{tooltip.classed("visible",false);}});
simulation.on("tick",function(){{
link.attr("x1",function(d){{return d.source.x;}}).attr("y1",function(d){{return d.source.y;}}).attr("x2",function(d){{return d.target.x;}}).attr("y2",function(d){{return d.target.y;}});
node.attr("cx",function(d){{return d.x;}}).attr("cy",function(d){{return d.y;}});
label.attr("x",function(d){{return d.x;}}).attr("y",function(d){{return d.y;}});
}});
function resetZoom(){{g.attr("transform",d3.zoomIdentity);}}
var showLabels=false;
function toggleLabels(){{showLabels=!showLabels;label.style("display",showLabels?"block":"none");}}
svg.call(d3.zoom().scaleExtent([0.05,4]).on("zoom",function(e){{g.attr("transform",e.transform);}}));
</script></body></html>'''

hout = output_dir / f'知识图谱_anshang_{ts}.html'
with open(hout, 'w', encoding='utf-8') as f:
    f.write(html)
(output_dir / '知识图谱_anshang_latest.html').write_text(html, encoding='utf-8')
print(f'Saved HTML: {hout.name}')

# Generate report
avg_deg = round(sum(degree_dict.values()) / max(1, len(degree_dict)), 2)
max_deg = max(degree_dict.values()) if degree_dict else 0

lines = []
lines.append(f'# 安评知识图谱分析报告\n\n')
lines.append(f'**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M")}\n\n')
lines.append('---\n## 概览\n\n| 指标 | 数值 |\n|------|------|\n')
lines.append(f'| 节点总数 | {G.number_of_nodes()} |\n')
lines.append(f'| 边总数 | {G.number_of_edges()} |\n')
lines.append(f'| 社区数 | {len(communities)} |\n')
lines.append(f'| 平均度数 | {avg_deg} |\n')
lines.append(f'| 最高度数 | {max_deg} |\n\n')
lines.append('---\n## Top 20 核心节点\n\n| 排名 | 节点 | 类型 | 度数 |\n|------|------|------|------|\n')
for rank, (nid, deg) in enumerate(top_nodes[:20], 1):
    lbl = nlabel(nid).replace('|', '\\|')
    lines.append(f'| {rank} | {lbl} | {ntype(nid)} | {deg} |\n')
lines.append('\n---\n## 社区详情\n\n')
for cs in comm_summaries[:20]:
    ts2 = ', '.join([f'{k}({v})' for k, v in list(cs['top_types'].items())[:5]])
    lines.append(f'### 社区 {cs["id"]}（{cs["size"]}节点，凝聚度 {cs["cohesion"]:.3f}）\n\n')
    lines.append(f'- **类型分布**: {ts2}\n')
    lines.append(f'- **核心节点**: {", ".join(cs["top_nodes"][:5])}\n\n')
lines.append(f'\n---\n*由 graphify 管道自动生成 | {ts}*\n')

report = ''.join(lines)
rout = output_dir / f'GRAPH_REPORT_anshang_{ts}.md'
with open(rout, 'w', encoding='utf-8') as f:
    f.write(report)
(output_dir / 'GRAPH_REPORT_anshang_latest.md').write_text(report, encoding='utf-8')
print(f'Saved report: {rout.name}')

# DONE marker
with open('/tmp/.graphify_done.txt', 'w') as f:
    f.write('DONE')
print('\n=== DONE ===')
print(f'Graph: graph_anshang_{ts}.json')
print(f'HTML: 知识图谱_anshang_{ts}.html')
print(f'Report: GRAPH_REPORT_anshang_{ts}.md')
