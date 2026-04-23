"""
Full graphify pipeline for 安评 directory - uses existing rich semantic data.
"""
import os, json, sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

print("=== Full Graphify Pipeline for 安评 ===")
ts = datetime.now().strftime("%Y%m%d_%H%M%S")

source_dir = Path("/home/wangyc/Documents/工作/法规指导原则/安评")
converted_dir = source_dir / "graphify-out/converted"
output_dir = source_dir / "graphify-out"

# ── Step 1: Detection ────────────────────────────────────────────────────────
print("\n[Step 1] Running detection...")
try:
    from graphify.detect import detect, FileType
    det_result = detect(source_dir)
    with open('/tmp/.graphify_detect_anshang.json', 'w') as f:
        json.dump(det_result, f, ensure_ascii=False, indent=2)
    total_files = len(det_result.get('files', []))
    print(f"  Detection done: {total_files} files found")
except Exception as e:
    print(f"  Detection error (non-fatal): {e}")
    md_files = list(converted_dir.glob("*.md"))
    det_result = {'files': [{'path': str(f), 'type': 'document'} for f in md_files]}
    with open('/tmp/.graphify_detect_anshang.json', 'w') as f:
        json.dump(det_result, f, ensure_ascii=False, indent=2)
    print(f"  Detection fallback: {len(md_files)} .md files")

# ── Step 2: Load best available semantic data ────────────────────────────────
print("\n[Step 2] Loading semantic data...")

# Try to find the most comprehensive existing semantic file
semantic_candidates = [
    output_dir / "graphify_semantic_anshang_cron_latest.json",
    output_dir / "graphify_semantic_anshang_latest.json",
    output_dir / "semantic_full.json",
    output_dir / "graphify_semantic_latest.json",
]

semantic_path = None
for p in semantic_candidates:
    if p.exists():
        with open(p) as f:
            d = json.load(f)
        n_nodes = len(d.get('nodes', []))
        if n_nodes > 100:
            semantic_path = p
            semantic_data = d
            print(f"  Using: {p.name} ({n_nodes} nodes, {len(d.get('edges',[]))} edges)")
            break

if semantic_path is None:
    print("  ERROR: No semantic data found!")
    sys.exit(1)

nodes = semantic_data.get('nodes', [])
edges = semantic_data.get('edges', [])
print(f"  Semantic: {len(nodes)} nodes, {len(edges)} edges")

# ── Step 3: Build Graph ───────────────────────────────────────────────────────
print("\n[Step 3] Building graph...")
import networkx as nx
G = nx.Graph()

def node_id(n):
    return n.get('id') or n.get('name') or ''

def get_edge_src_tgt(e):
    src = e.get('source') or e.get('from') or e.get('src') or ''
    tgt = e.get('target') or e.get('to') or e.get('dst') or ''
    return src, tgt

for node in nodes:
    nid = node_id(node)
    if not nid:
        continue
    attrs = {k: v for k, v in node.items() if k != 'id'}
    G.add_node(nid, **attrs)

for edge in edges:
    src, tgt = get_edge_src_tgt(edge)
    if not src or not tgt:
        continue
    if src not in G:
        G.add_node(src)
    if tgt not in G:
        G.add_node(tgt)
    attrs = {k: v for k, v in edge.items() if k not in ('source','target','from','to','src','dst')}
    G.add_edge(src, tgt, **attrs)

print(f"  Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# ── Step 4: Cluster ──────────────────────────────────────────────────────────
print("\n[Step 4] Clustering...")
try:
    from networkx.algorithms.community import louvain_communities
    communities = louvain_communities(G, resolution=1.0, seed=42)
    communities = [list(c) for c in communities]
except Exception as e:
    print(f"  Louvain failed: {e}, using connected components")
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
        possible = len(comm) * (len(comm) - 1) / 2
        actual = subgraph.number_of_edges()
        cohesion_scores[i] = round(actual / possible, 3) if possible > 0 else 0.0

# ── Step 5: Community summaries ─────────────────────────────────────────────
print("\n[Step 5] Generating community summaries...")

def node_label(nid):
    return G.nodes[nid].get('label', G.nodes[nid].get('name', nid)) if nid in G else str(nid)

def node_type(nid):
    return G.nodes[nid].get('type', G.nodes[nid].get('file_type', 'concept')) if nid in G else 'concept'

def node_degree(nid):
    return G.degree(nid) if nid in G else 0

degree_dict = dict(G.degree())

top_nodes_by_degree = sorted(degree_dict.items(), key=lambda x: x[1], reverse=True)

comm_summaries = []
for i, comm in enumerate(communities):
    subgraph = G.subgraph(comm)
    type_counter = defaultdict(int)
    for nid in comm:
        t = node_type(nid)
        type_counter[t] += 1
    
    node_degrees = [(nid, G.degree(nid)) for nid in comm]
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

# Sort communities by size
comm_summaries.sort(key=lambda x: x['size'], reverse=True)

for cs in comm_summaries[:10]:
    print(f"  Community {cs['id']}: {cs['size']} nodes, {cs['edge_count']} edges, cohesion={cs['cohesion']}")
    print(f"    Top nodes: {', '.join(cs['top_nodes'][:3])}")

# ── Step 6: Save JSON graph ──────────────────────────────────────────────────
print("\n[Step 6] Saving graph JSON...")

graph_data = {
    'nodes': [],
    'edges': [],
}

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

# ── Step 7: Generate HTML ───────────────────────────────────────────────────
print("\n[Step 7] Generating HTML...")

nodes_j = json.dumps(graph_data['nodes'], ensure_ascii=False)
edges_j = json.dumps(graph_data['edges'], ensure_ascii=False)
colors_list = [
    "#4A90D9","#D94A4A","#4AD94A","#D9D94A","#4AD9D9",
    "#D94AD9","#4A4AD9","#D98A4A","#4AD98A","#8A4AD9",
    "#D94A8A","#4AD9D9","#D9D94A","#94D94A","#4A94D9",
    "#9A4AD9","#4AD9A9","#D9A94A","#A94AD9","#D9A9A9"
]
colors_j = json.dumps(colors_list)
coh_j = json.dumps(cohesion_scores)

# Community legend
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

_html = []
_html.append('<!DOCTYPE html>')
_html.append('<html lang="zh">')
_html.append('<head>')
_html.append('<meta charset="UTF-8">')
_html.append('<title>安评知识图谱 - %s</title>' % ts)
_html.append('<script src="https://d3js.org/d3.v7.min.js"></script>')
_html.append('<style>')
_html.append('*{margin:0;padding:0;box-sizing:border-box}')
_html.append('body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0d1117;color:#e6edf3;overflow:hidden}')
_html.append('#graph{width:100vw;height:100vh}')
_html.append('.node{cursor:pointer}')
_html.append('.node-label{font-size:9px;fill:#e6edf3;pointer-events:none}')
_html.append('.link{stroke-opacity:0.35;stroke:#555}')
_html.append('.tooltip{position:absolute;background:#161b22;border:1px solid #30363d;padding:8px 12px;border-radius:6px;font-size:13px;max-width:320px;pointer-events:none;opacity:0;transition:opacity 0.2s;z-index:10;color:#e6edf3}')
_html.append('.tooltip.visible{opacity:1}')
_html.append('.tooltip .type{color:#58a6ff;font-size:11px}')
_html.append('.tooltip .file{color:#8b949e;font-size:11px;margin-top:4px}')
_html.append('#sidebar{position:absolute;top:10px;right:10px;width:320px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:15px;max-height:90vh;overflow-y:auto;z-index:5}')
_html.append('#sidebar h3{color:#58a6ff;margin-bottom:12px;font-size:14px}')
_html.append('.comm-item{margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid #30363d}')
_html.append('.comm-title{font-weight:bold;font-size:13px;margin-bottom:3px}')
_html.append('.comm-meta{font-size:11px;color:#8b949e}')
_html.append('#stats{position:absolute;top:10px;left:10px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;font-size:12px;z-index:5}')
_html.append('#stats span{color:#58a6ff;font-weight:bold}')
_html.append('#controls{position:absolute;bottom:10px;left:10px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;font-size:12px;z-index:5}')
_html.append('#controls button{background:#238636;border:none;color:#fff;padding:4px 10px;border-radius:4px;cursor:pointer;margin-right:5px}')
_html.append('#controls button:hover{background:#2ea043}')
_html.append('</style>')
_html.append('</head>')
_html.append('<body>')
_html.append('<div id="graph"></div>')
_html.append('<div id="tooltip" class="tooltip"></div>')
_html.append('<div id="sidebar">')
_html.append('<h3>📊 社区聚类 (共%d个社区)</h3>' % len(communities))
_html.append(comm_legend_html)
_html.append('</div>')
_html.append('<div id="stats">')
_html.append('<div>节点 <span>%d</span> | 边 <span>%d</span> | 社区 <span>%d</span></div>' % (
    G.number_of_nodes(), G.number_of_edges(), len(communities)))
_html.append('</div>')
_html.append('<div id="controls">')
_html.append('<button onclick="resetZoom()">重置视图</button>')
_html.append('<button onclick="toggleLabels()">切换标签</button>')
_html.append('</div>')
_html.append('<script>')
_html.append('const nodes = %s;' % nodes_j)
_html.append('const edges = %s;' % edges_j)
_html.append('const colors = %s;' % colors_j)
_html.append('const cohesion = %s;' % coh_j)
_html.append('const communities = %s;' % json.dumps(comm_summaries, ensure_ascii=False))
_html.append('const width = window.innerWidth, height = window.innerHeight;')
_html.append('const svg = d3.select("#graph").append("svg").attr("width",width).attr("height",height);')
_html.append('const g = svg.append("g");')
_html.append('const simulation = d3.forceSimulation(nodes)')
_html.append('  .force("link", d3.forceLink(edges).id(function(d){return d.id;}).distance(60).strength(0.3))')
_html.append('  .force("charge", d3.forceManyBody().strength(-80))')
_html.append('  .force("center", d3.forceCenter(width/2, height/2))')
_html.append('  .force("collision", d3.forceCollide(8));')
_html.append('const link = g.append("g").selectAll("line").data(edges)')
_html.append('  .join("line").attr("class","link")')
_html.append('  .attr("stroke","#555").attr("stroke-width", function(d){return Math.max(0.5,(d.weight||1)*1.5);});')
_html.append('const node = g.append("g").selectAll("circle").data(nodes)')
_html.append('  .join("circle")')
_html.append('  .attr("r", function(d){return Math.min(12,4+(d.degree||0)*0.3);})')
_html.append('  .attr("fill", function(d){return colors[d.community%%colors.length];})')
_html.append('  .attr("class","node")')
_html.append('  .call(d3.drag()')
_html.append('    .on("start",function(e,d){if(!e.active) simulation.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y;})')
_html.append('    .on("drag",function(e,d){d.fx=e.x;d.fy=e.y;})')
_html.append('    .on("end",function(e,d){if(!e.active) simulation.alphaTarget(0);d.fx=null;d.fy=null;}));')
_html.append('const label = g.append("g").selectAll("text").data(nodes)')
_html.append('  .join("text").attr("class","node-label")')
_html.append('  .text(function(d){return d.label||d.id;})')
_html.append('  .attr("text-anchor","middle")')
_html.append('  .attr("dy",function(d){return (Math.min(12,4+(d.degree||0)*0.3))+4;})')
_html.append('  .style("display","none");')
_html.append('const tooltip = d3.select("#tooltip");')
_html.append('node.on("mouseover",function(e,d){')
_html.append('  var t = d.type || "concept";')
_html.append('  var l = d.label || d.id;')
_html.append('  var f = d.source_file || "";')
_html.append('  tooltip.classed("visible",true)')
_html.append('    .html("<div class=\\"type\\">"+t+"</div><div>"+l+"</div><div class=\\"file\\">"+f+"</div><div>度数:"+d.degree+" 社区:"+d.community+"</div>");')
_html.append('  }).on("mousemove",function(e){tooltip.style("left",(e.pageX+15)+"px").style("top",(e.pageY-10)+"px");})')
_html.append('  .on("mouseout",function(){tooltip.classed("visible",false);});')
_html.append('simulation.on("tick",function(){')
_html.append('  link.attr("x1",function(d){return d.source.x;}).attr("y1",function(d){return d.source.y;})')
_html.append('      .attr("x2",function(d){return d.target.x;}).attr("y2",function(d){return d.target.y;});')
_html.append('  node.attr("cx",function(d){return d.x;}).attr("cy",function(d){return d.y;});')
_html.append('  label.attr("x",function(d){return d.x;}).attr("y",function(d){return d.y;});')
_html.append('});')
_html.append('function resetZoom(){g.attr("transform",d3.zoomIdentity);}')
_html.append('var showLabels=false;')
_html.append('function toggleLabels(){showLabels=!showLabels;label.style("display",showLabels?"block":"none");}')
_html.append('svg.call(d3.zoom().scaleExtent([0.05,4]).on("zoom",function(e){g.attr("transform",e.transform);}));')
_html.append('</script>')
_html.append('</body>')
_html.append('</html>')
html = '\n'.join(_html)

html_out = output_dir / ("知识图谱_anshang_%s.html" % ts)
with open(html_out, 'w', encoding='utf-8') as f:
    f.write(html)
(output_dir / "知识图谱_anshang_latest.html").write_text(html, encoding='utf-8')
print(f"  Saved: {html_out.name}")

# ── Step 8: Generate GRAPH_REPORT.md ────────────────────────────────────────
print("\n[Step 8] Generating GRAPH_REPORT.md...")

avg_deg = round(sum(degree_dict.values()) / max(1, len(degree_dict)), 2)
max_deg = max(degree_dict.values()) if degree_dict else 0

report_lines = []
report_lines.append('# 安评知识图谱分析报告\n')
report_lines.append('**生成时间**: %s  \n' % datetime.now().strftime("%Y-%m-%d %H:%M"))
report_lines.append('**数据来源**: %s\n' % str(source_dir))
report_lines.append('\n---\n')
report_lines.append('## 概览\n')
report_lines.append('| 指标 | 数值 |\n')
report_lines.append('|------|------|\n')
report_lines.append('| 节点总数 | %d |\n' % G.number_of_nodes())
report_lines.append('| 边总数 | %d |\n' % G.number_of_edges())
report_lines.append('| 社区数 | %d |\n' % len(communities))
report_lines.append('| 平均度数 | %s |\n' % avg_deg)
report_lines.append('| 最高度数 | %d |\n' % max_deg)
report_lines.append('\n---\n')
report_lines.append('## Top 20 核心节点（按度数）\n')
report_lines.append('| 排名 | 节点 | 类型 | 度数 |\n')
report_lines.append('|------|------|------|------|\n')
for rank, (nid, deg) in enumerate(top_nodes_by_degree[:20], 1):
    lbl = node_label(nid).replace('|', '\\|')
    typ = node_type(nid)
    report_lines.append('| %d | %s | %s | %d |\n' % (rank, lbl, typ, deg))

report_lines.append('\n---\n')
report_lines.append('## 社区详情\n')
for rank, cs in enumerate(comm_summaries[:20], 1):
    color = colors_list[cs['id'] % len(colors_list)]
    type_str = ', '.join(['%s(%d)' % (k, v) for k, v in list(cs['top_types'].items())[:5]])
    report_lines.append('### 社区 %d（%d节点，凝聚度 %.3f）\n\n' % (cs['id'], cs['size'], cs['cohesion']))
    report_lines.append('- **类型分布**: %s\n' % type_str)
    report_lines.append('- **核心节点**: %s\n' % ', '.join(cs['top_nodes'][:5]))
    report_lines.append('- **边数**: %d\n\n' % cs['edge_count'])

report_lines.append('---\n')
report_lines.append('## 输入文件统计\n')
file_nodes = defaultdict(list)
for n in nodes:
    sf = n.get('source_file', '')
    if sf:
        file_nodes[sf].append(n.get('label', n.get('id', '')))
for sf, labels in sorted(file_nodes.items()):
    report_lines.append('- **%s**: %d 实体\n' % (sf, len(labels)))

report_lines.append('\n---\n')
report_lines.append('*由 graphify 管道自动生成 | %s*\n' % ts)

report = ''.join(report_lines)
report_out = output_dir / ("GRAPH_REPORT_anshang_%s.md" % ts)
report_out.write_text(report, encoding='utf-8')
(output_dir / "GRAPH_REPORT_anshang_latest.md").write_text(report, encoding='utf-8')
print(f"  Saved: GRAPH_REPORT_anshang_%s.md" % ts)

# ── Step 9: Write DONE marker ─────────────────────────────────────────────────
print("\n[Step 9] Writing completion marker...")
with open('/tmp/.graphify_done.txt', 'w') as f:
    f.write('DONE')

print("\n=== Pipeline Complete ===")
print(f"  Graph JSON: graph_anshang_{ts}.json")
print(f"  HTML: 知识图谱_anshang_{ts}.html")
print(f"  Report: GRAPH_REPORT_anshang_{ts}.md")
print(f"  DONE marker: /tmp/.graphify_done.txt")
