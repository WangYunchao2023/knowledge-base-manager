import json, os, sys, math
import networkx as nx
from pathlib import Path
from datetime import datetime

D = Path("/home/wangyc/Documents/工作/法规指导原则/安评/graphify-out")
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
print(f"Starting {TS}")

SEMS = sorted(D.glob("知识图谱_安评_graphify_semantic_cron_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
if SEMS:
    SEM = SEMS[0]
else:
    ALT = D / "anshang_graphify_semantic_cron_latest_semantic.json"
    if ALT.exists():
        SEM = ALT
    else:
        print("ERROR: No semantic cache")
        sys.exit(1)

print(f"Using: {SEM.name}")
with open(SEM, encoding="utf-8") as f:
    sem = json.load(f)
print(f"  nodes={len(sem['nodes'])}, edges={len(sem['edges'])}")

G = nx.Graph()
for n in sem["nodes"]:
    nid = n["id"]
    attrs = {k: v for k, v in n.items() if k != "id"}
    G.add_node(nid, **attrs)
for e in sem["edges"]:
    s, t = e["source"], e["target"]
    if s in G and t in G:
        attrs = {k: v for k, v in e.items() if k not in ("source", "target")}
        G.add_edge(s, t, **attrs)
print(f"Graph: {G.number_of_nodes()}N {G.number_of_edges()}E")

print("Louvain...")
try:
    comms = nx.community.louvain_communities(G, seed=42, max_level=10, threshold=1e-4)
except:
    try:
        from networkx.community import greedy_modularity_communities as gmc
        comms = list(gmc(G))
    except:
        from networkx.community import label_propagation_communities as lpc
        comms = list(lpc(G))
communities = {i: sorted(list(c)) for i, c in enumerate(comms)}
print(f"  {len(communities)} communities")

def coh(sub):
    n = len(sub.nodes())
    if n < 2: return 0.0
    return round(sub.number_of_edges() / (n*(n-1)/2), 3)
cohesion = {cid: coh(G.subgraph(ns)) for cid, ns in communities.items()}

deg = dict(G.degree())
sn = sorted(deg.items(), key=lambda x: -x[1])
SKIP = (".md)", ".py)", ".ts)", ".java)")
gods = []
for nid, d in sn:
    lbl = G.nodes[nid].get("label","")
    if lbl.endswith(SKIP): continue
    sf = G.nodes[nid].get("source_file","")
    bn = os.path.basename(sf).replace(".md","").replace("_","")
    if bn and lbl.replace("_","").replace(" ","") == bn[:30]: continue
    gods.append({"id": nid, "label": lbl, "edges": d})
    if len(gods) >= 15: break
print(f"  Top god: {gods[0]['label']} ({gods[0]['edges']})")

cross = []
for u, v, ed in G.edges(data=True):
    uc = next((c for c, ns in communities.items() if u in ns), None)
    vc = next((c for c, ns in communities.items() if v in ns), None)
    if uc is not None and vc is not None and uc != vc:
        cross.append({"source":u,"target":v,"relation":ed.get("relation","related_to"),"confidence":ed.get("confidence","EXTRACTED"),"source_label":G.nodes[u].get("label",""),"target_label":G.nodes[v].get("label","")})
cross.sort(key=lambda x: -deg.get(x["source"],0)-deg.get(x["target"],0))
print(f"  {len(cross)} cross-community edges")

LABELS = {}
for cid, nodes in communities.items():
    words = " ".join([G.nodes[n].get("label","") for n in nodes[:10]]).split()
    wf = {}
    for w in words:
        if len(w) >= 3: wf[w] = wf.get(w, 0) + 1
    tw = sorted(wf.items(), key=lambda x: -x[1])
    LABELS[cid] = " ".join([w for w,_ in (tw[:3] if tw else [(f"C{cid}",1)])])[:40]

GP = D / f"知识图谱_安评_graphify_semantic_cron_{TS}_graph.json"
data = nx.node_link_data(G)
data["communities"] = {str(k): v for k, v in communities.items()}
with open(GP, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"Graph JSON: {GP.name}")

HP = D / f"知识图谱_安评_graphify_semantic_cron_{TS}.html"
HCOLS = ['#e06c75','#98c379','#e5c07b','#61afef','#c678dd','#56b6c2','#d19a66','#be5046','#4db6ac','#f44336']
nj = []
for nid in G.nodes():
    nd = G.nodes[nid]
    cm = next((c for c, ns in communities.items() if nid in ns), 0)
    nj.append({"id":nid,"label":nd.get("label",nid)[:40],"group":cm,"color":HCOLS[cm%10],"edges":G.degree(nid)})
elj = []
for u, v, ed in G.edges(data=True):
    elj.append({"source":u,"target":v,"relation":ed.get("relation","unknown"),"confidence":ed.get("confidence","EXTRACTED")})
html = f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>安评知识图谱</title><script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script><style>body{{margin:0;font-family:system-ui;background:#0d1117;color:#e6edf3}}#h{{padding:14px 22px;background:#161b22;border-bottom:1px solid #30363d}}#h h1{{margin:0;color:#58a6ff;font-size:1.2em}}#h div{{color:#8b949e;font-size:0.83em;margin-top:5px}}#n{{width:100vw;height:calc(100vh-65px)}}</style></head><body><div id="h"><h1>🔬 安评非临床安全性评价知识图谱</h1><div>节点:{G.number_of_nodes()} | 边:{G.number_of_edges()} | 社区:{len(communities)} | {TS}</div></div><div id="n"></div><script>var nd=new vis.DataSet({json.dumps(nj,ensure_ascii=False)});var ed=new vis.DataSet({json.dumps(elj,ensure_ascii=False)});var c=document.getElementById("n");new vis.Network(c,{{nodes:nd,edges:ed}},{{nodes:{{shape:"dot",size:11,font:{{size:11,color:"#e6edf3"}}}},edges:{{width:1.1,color:{{color:"#30363d",highlight:"#58a6ff"}}}},physics:{{forceAtlas2Based:{{gravitationalConstant:-80,springLength:100}},maxVelocity:50,solver:"forceAtlas2Based",timestep:0.35,stabilization:{{iterations:150}}}},interaction:{{hover:true,navigationButtons:true}}}).stabilize();</script></body></html>'
HP.write_text(html, encoding="utf-8")
print(f"HTML: {HP.name}")

RP = D / f"知识图谱_安评_graphify_semantic_cron_{TS}_report.md"
sc = sorted(communities.items(), key=lambda x: -len(x[1]))
rlines = [f"# 📊 安评知识图谱分析报告\n\n**生成**: {TS}\n**规模**: {G.number_of_nodes()}N · {G.number_of_edges()}E · {len(communities)}社区\n\n---\n\n## 🏛 God Nodes\n\n| 节点 | 标签 | 度数 |\n|------|------|------|\n"]
for g in gods[:10]:
    rlines.append(f"| {g['id'][:35]} | {g['label'][:45]} | {g['edges']} |")
rlines.append("\n## 🌉 跨社区连接\n\n| 源 | 关系 | 目标 | 置信 |\n|----|------|------|------|\n")
for c2 in cross[:20]:
    rlines.append(f"| {c2['source_label'][:25]} | {c2['relation']} | {c2['target_label'][:25]} | {c2['confidence']} |")
rlines.append("\n## 📂 社区概览\n\n")
for rank,(cid,nodes) in enumerate(sc[:12]):
    lbl = LABELS.get(cid,f"Community{cid}")
    rlines.append(f"### {rank+1}. {lbl} (cohesion={cohesion.get(cid,0)}, {len(nodes)}nodes)\n")
    rlines.append(f"- {', '.join([G.nodes[n].get('label','')[:35] for n in nodes[:7]])}\n\n")
RP.write_text("".join(rlines), encoding="utf-8")
print(f"Report: {RP.name}")

for ln, tp in [("知识图谱_安评_graphify_semantic_cron_latest.html", HP), ("知识图谱_安评_graphify_semantic_cron_latest_graph.json", GP), ("知识图谱_安评_graphify_semantic_cron_latest_report.md", RP)]:
    lp = D / ln
    if lp.is_symlink() or lp.exists(): lp.unlink()
    try: lp.symlink_to(tp.name)
    except: pass
print("Symlinks updated")
print(f"\n=== DONE: {G.number_of_nodes()}N {G.number_of_edges()}E {len(communities)}C ===")
Path("/tmp/.graphify_done.txt").write_text("DONE")
print("DONE written")
