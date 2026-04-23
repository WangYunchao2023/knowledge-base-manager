#!/usr/bin/env python3
"""Graphify pipeline for 安评 regulatory guidance - uses existing semantic cache"""
import json, os, sys, math
import networkx as nx
from pathlib import Path
from datetime import datetime, timezone

CORPUS_DIR = Path("/home/wangyc/Documents/工作/法规指导原则/安评")
OUT_DIR = CORPUS_DIR / "graphify-out"
OUT_DIR.mkdir(exist_ok=True)
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
WORK = Path("/home/wangyc/.openclaw/workspace/tmp")
WORK.mkdir(exist_ok=True)

print(f"[{TS}] Starting graphify pipeline for 安评...")

# ── Load most recent semantic cache ──────────────────────────────────────────
sem_files = sorted(
    (OUT_DIR).glob("知识图谱_安评_graphify_semantic_cron_*.json"),
    key=lambda p: p.stat().st_mtime,
    reverse=True
)
if sem_files:
    SEM = sem_files[0]
else:
    # fallback to anshang prefix
    alt = OUT_DIR / "anshang_graphify_semantic_cron_latest_semantic.json"
    if alt.exists():
        SEM = alt
    else:
        print("ERROR: No semantic cache found!")
        sys.exit(1)

print(f"Loading semantic cache: {SEM.name}")
with open(SEM, encoding="utf-8") as f:
    sem = json.load(f)
print(f"  {len(sem['nodes'])} nodes, {len(sem['edges'])} edges")

# ── Build graph ───────────────────────────────────────────────────────────────
print("Building graph...")
G = nx.Graph()
for n in sem["nodes"]:
    nid = n["id"]
    attrs = {k: v for k, v in n.items() if k != "id"}
    G.add_node(nid, **attrs)

edge_added = 0
for e in sem["edges"]:
    src, tgt = e["source"], e["target"]
    if src in G and tgt in G:
        attrs = {k: v for k, v in e.items() if k not in ("source", "target")}
        G.add_edge(src, tgt, **attrs)
        edge_added += 1

print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# ── Community detection ────────────────────────────────────────────────────────
print("Running Louvain community detection...")
try:
    comms = nx.community.louvain_communities(G, seed=42, max_level=10, threshold=1e-4)
except Exception as e:
    print(f"  Louvain failed: {e}, using greedy modularity")
    try:
        from networkx.community import greedy_modularity_communities
        comms = list(greedy_modularity_communities(G))
    except:
        from networkx.community import label_propagation_communities
        comms = list(label_propagation_communities(G))
communities = {i: sorted(list(c)) for i, c in enumerate(comms)}
print(f"  {len(communities)} communities found")

# ── Cohesion ──────────────────────────────────────────────────────────────────
def calc_cohesion(subgraph):
    n = len(subgraph.nodes())
    if n < 2:
        return 0.0
    possible = n * (n - 1) / 2
    return round(subgraph.number_of_edges() / possible, 3) if possible > 0 else 0

cohesion = {}
for cid, nodes in communities.items():
    sub = G.subgraph(nodes)
    cohesion[cid] = calc_cohesion(sub)

# ── God nodes ─────────────────────────────────────────────────────────────────
degree = dict(G.degree())
sorted_nodes = sorted(degree.items(), key=lambda x: -x[1])
gods = []
skip_patterns = (".md)", ".py)", ".ts)", ".js)", ".go)", ".java)")
for nid, deg in sorted_nodes:
    label = G.nodes[nid].get("label", nid)
    if label.endswith(skip_patterns):
        continue
    src_file = G.nodes[nid].get("source_file", "")
    basename = os.path.basename(src_file).replace(".md", "").replace("_","")
    if basename and label.replace("_","").replace(" ","") == basename[:30]:
        continue
    gods.append({"id": nid, "label": label, "edges": deg})
    if len(gods) >= 15:
        break

print(f"  Top god node: {gods[0]['label']} ({gods[0]['edges']} edges)")

# ── Surprising connections ─────────────────────────────────────────────────────
cross_comm = []
for u, v, d in G.edges(data=True):
    uc = next((c for c, ns in communities.items() if u in ns), None)
    vc = next((c for c, ns in communities.items() if v in ns), None)
    if uc is not None and vc is not None and uc != vc:
        cross_comm.append({
            "source": u, "target": v,
            "relation": d.get("relation", "related_to"),
            "confidence": d.get("confidence", "EXTRACTED"),
            "source_label": G.nodes[u].get("label", u),
            "target_label": G.nodes[v].get("label", v)
        })

cross_comm.sort(key=lambda x: -degree.get(x["source"], 0) - degree.get(x["target"], 0))
print(f"  {len(cross_comm)} cross-community edges")

# ── Community labels ───────────────────────────────────────────────────────────
LABELS = {}
for cid, nodes in communities.items():
    labels_list = [G.nodes[n].get("label","") for n in nodes[:10]]
    all_text = " ".join(labels_list)
    words = [w for w in all_text.split() if len(w) >= 3]
    word_freq = {}
    for w in words:
        word_freq[w] = word_freq.get(w, 0) + 1
    top_words = sorted(word_freq.items(), key=lambda x: -x[1])
    if top_words:
        main_words = " ".join([w for w, _ in top_words[:3]])
    else:
        main_words = f"Community {cid}"
    LABELS[cid] = main_words[:40]
print(f"  Community labels assigned: {len(LABELS)}")

# ── Save graph JSON ────────────────────────────────────────────────────────────
graph_json_path = OUT_DIR / f"知识图谱_安评_graphify_semantic_cron_{TS}_graph.json"
data = nx.node_link_data(G)
data["communities"] = {str(k): v for k, v in communities.items()}
with open(graph_json_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"Graph JSON: {graph_json_path.name}")

# ── Generate HTML using graphify ─────────────────────────────────────────────
html_path = OUT_DIR / f"知识图谱_安评_graphify_semantic_cron_{TS}.html"
try:
    from graphify.export import to_html
    to_html(G, communities, str(html_path), community_labels=LABELS)
    print(f"HTML: {html_path.name}")
except Exception as e:
    print(f"graphify to_html failed: {e}, building fallback HTML")
    fallback_html = _build_simple_html(G, communities, LABELS, gods, cross_comm)
    html_path.write_text(fallback_html, encoding="utf-8")
    print(f"HTML (fallback): {html_path.name}")

# ── Generate GRAPH_REPORT.md ──────────────────────────────────────────────────
report = _build_report(G, communities, cohesion, LABELS, gods, cross_comm, sem)
report_path = OUT_DIR / f"知识图谱_安评_graphify_semantic_cron_{TS}_report.md"
report_path.write_text(report, encoding="utf-8")
print(f"Report: {report_path.name}")

# ── Update symlinks ───────────────────────────────────────────────────────────
for link_name, target in [
    ("知识图谱_安评_graphify_semantic_cron_latest.html", html_path),
    ("知识图谱_安评_graphify_semantic_cron_latest_graph.json", graph_json_path),
    ("知识图谱_安评_graphify_semantic_cron_latest_report.md", report_path),
]:
    link_path = OUT_DIR / link_name
    if link_path.is_symlink() or link_path.exists():
        link_path.unlink()
    try:
        link_path.symlink_to(target.name)
    except Exception:
        pass
print("Symlinks updated")

print(f"\n=== DONE ===")
print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(communities)} communities")

# ── Write DONE file ────────────────────────────────────────────────────────────
Path("/tmp/.graphify_done.txt").write_text("DONE")
print("DONE file written: /tmp/.graphify_done.txt")

# ── Helper functions ───────────────────────────────────────────────────────────
def _build_simple_html(G, communities, labels, gods, cross_comm):
    nodes_json = []
    for nid in G.nodes():
        d = G.nodes[nid]
        comm = next((c for c, ns in communities.items() if nid in ns), 0)
        color_idx = comm % 10
        colors = ['#e06c75','#98c379','#e5c07b','#61afef','#c678dd','#56b6c2','#d19a66','#be5046','#4db6ac','#f44336']
        nodes_json.append({
            "id": nid,
            "label": d.get("label", nid)[:40],
            "community": comm,
            "group": comm,
            "color": colors[color_idx % len(colors)],
            "edges": G.degree(nid)
        })
    
    links_json = []
    for u, v, d_e in G.edges(data=True):
        links_json.append({
            "source": u, "target": v,
            "relation": d_e.get("relation", "unknown"),
            "confidence": d_e.get("confidence", "EXTRACTED")
        })
    
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>安评知识图谱</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
body {{ margin:0; font-family:system-ui,sans-serif; background:#0d1117; color:#e6edf3 }}
#header {{ padding:16px 24px; background:#161b22; border-bottom:1px solid #30363d; display:flex; align-items:center; gap:20px }}
#header h1 {{ margin:0; color:#58a6ff; font-size:1.3em }}
.stats {{ color:#8b949e; font-size:0.85em }}
#mynetwork {{ width:100vw; height:calc(100vh - 70px) }}
</style></head><body>
<div id="header">
  <h1>🔬 安评非临床安全性评价知识图谱</h1>
  <div class="stats">节点: {G.number_of_nodes()} | 边: {G.number_of_edges()} | 社区: {len(communities)} | 生成: {TS}</div>
</div>
<div id="mynetwork"></div>
<script>
var nodes = new vis.DataSet({json.dumps(nodes_json, ensure_ascii=False)});
var edges = new vis.DataSet({json.dumps(links_json, ensure_ascii=False)});
var container = document.getElementById('mynetwork');
var data = {{ nodes: nodes, edges: edges }};
var options = {{
  nodes: {{
    shape:'dot', size:12,
    font: {{ size:12, color:'#e6edf3', face:'system-ui' }},
    borderWidth:2
  }},
  edges: {{
    width:1.2,
    color: {{ color:'#30363d', highlight:'#58a6ff', hover: '#8b949e' }},
    smooth: {{ type:'continuous' }}
  }},
  physics: {{ 
    forceAtlas2Based: {{ gravitationalConstant:-80, centralGravity:0.01, springLength:100, springConstant:0.08 }},
    maxVelocity: 50, solver: 'forceAtlas2Based', timestep: 0.35, stabilization: {{ iterations: 150 }}
  }},
  interaction: {{ hover: true, tooltipDelay: 200, navigationButtons: true }}
}};
var network = new vis.Network(container, data, options);
network.stabilize();
</script></body></html>"""
    return html

def _build_report(G, communities, cohesion, labels, gods, cross_comm, sem):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# 📊 安评知识图谱分析报告",
        f"",
        f"**生成时间**: {ts}",
        f"**图谱规模**: {G.number_of_nodes()} 节点 · {G.number_of_edges()} 条边",
        f"**社区数量**: {len(communities)}",
        f"",
        f"---",
        f"",
    ]
    
    lines.append("## 🏛 God Nodes（核心枢纽节点）")
    lines.append("")
    lines.append("| 节点ID | 标签 | 度数 |")
    lines.append("|--------|------|------|")
    for g in gods[:10]:
        lid = g['label'][:50]
        lines.append(f"| `{g['id'][:35]}` | {lid} | {g['edges']} |")
    lines.append("")
    
    lines.append("## 🌉 跨社区连接（Surprising Connections）")
    lines.append("")
    lines.append("跨社区边揭示了不同指导原则之间的非明显关联：")
    lines.append("")
    lines.append("| 源节点 | 关系类型 | 目标节点 | 置信度 |")
    lines.append("|--------|----------|--------|--------|")
    for c in cross_comm[:20]:
        sl = c['source_label'][:28]
        tl = c['target_label'][:28]
        lines.append(f"| {sl} | `{c['relation']}` | {tl} | {c['confidence']} |")
    lines.append("")
    
    lines.append("## 📂 社区详细分析")
    lines.append("")
    sorted_comms = sorted(communities.items(), key=lambda x: -len(x[1]))
    for rank, (cid, nodes) in enumerate(sorted_comms[:15]):
        coh = cohesion.get(cid, 0)
        comm_label = labels.get(cid, f"Community {cid}")
        node_sample = [G.nodes[n].get("label", n)[:38] for n in nodes[:10]]
        lines.append(f"### {rank+1}. {comm_label}")
        lines.append(f"- **规模**: {len(nodes)} 节点 | **内聚度**: {coh}")
        lines.append(f"- **代表节点**: {', '.join(node_sample[:6])}")
        lines.append("")
    
    return "\n".join(lines)
