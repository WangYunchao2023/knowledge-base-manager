#!/usr/bin/env python3
"""Full graphify pipeline for 安评 - anshang - 20260420 04:50"""
import json, time, sys, re, shutil
from pathlib import Path
from collections import defaultdict

print("=== Graphify Pipeline for 安评 ===")
ts = time.strftime("%Y%m%d_%H%M%S")
PREFIX = f"anshang_graphify_semantic_cron_{ts}"

ROOT = Path("/home/wangyc/Documents/工作/法规指导原则/安评")
OUT  = ROOT / "graphify-out"
CONV = OUT / "converted"

# ── Entity vocabulary ─────────────────────────────────────────────────────────
DRUG_TYPES = ["化学药物","中药","天然药物","生物制品","纳米药物","抗体偶联药物","脂质体药物",
    "治疗用生物制品","预防用生物制品","新药用辅料","基因治疗药物","疫苗","血液制品","抗体",
    "细胞因子","酶类药物","小分子药物","大分子药物","生物技术药物","复方药物","创新药物",
    "仿制药","放射性药物","细胞与基因治疗药物","先进疗法","ADC",
    "含毒性药材中药","一般药理学研究用中药"]
TOX_STUDY_TYPES = ["急性毒性试验","长期毒性试验","重复给药毒性试验","生殖毒性试验","致癌试验",
    "遗传毒性试验","免疫毒性试验","过敏性试验","光变态反应试验","刺激性试验","溶血性试验",
    "局部毒性试验","安全药理学试验","一般药理学试验","毒代动力学试验","药代动力学研究",
    "光安全性评价","心脏安全性","QT间期延长","毒理学研究","单次给药毒性研究","单次给药毒性试验",
    "局部刺激性试验","主动过敏试验","被动过敏试验","皮肤刺激试验","眼刺激试验","肌肉刺激试验",
    "主动全身过敏试验","被动皮肤过敏试验","抗肿瘤药物非临床评价","非临床安全性评价",
    "一般药理学研究","临床前安全性评价","局部刺激性和溶血性","光变态反应"]
ENDPOINTS = ["死亡率","LD50","最大给药量","无毒性反应剂量","NOAEL","NOEL","最大耐受剂量","MTD",
    "毒性靶器官","靶组织","不良反应","毒性表现","剂量-反应关系","时间-反应关系","可逆性",
    "蓄积毒性","延迟毒性","起始剂量","暴露量","AUC","Cmax","Tmax","表观分布容积","清除率","半衰期",
    "生物利用度","生物等效性","安全药理学终点","hERG通道","心室复极化"]
TEST_METHODS = ["Ames试验","微核试验","染色体畸变试验","骨髓细胞微核试验","体外染色体畸变试验",
    "小鼠淋巴瘤细胞试验","彗星试验","单次给药毒性试验","14天重复给药毒性试验","90天重复给药毒性试验",
    "SD大鼠","beagle犬","啮齿类动物","非啮齿类动物","急性经口毒性试验","急性经皮毒性试验",
    "急性吸入毒性试验","剂量递增试验","最大可行剂量","极限试验","骨髓细胞染色体畸变试验"]
REG_CONCEPTS = ["GLP","GCP","GMP","非临床研究质量管理规范","药物非临床研究质量管理规范",
    "安全性评价","有效性评价","质量控制","注册申报","技术审评","临床试验","临床试验申请",
    "IND","NDA","生物利用度","等效性","生物等效性","给药途径","给药方式","生物等效性评价",
    "供试品","检测要求","毒代动力学","暴露量评估","非临床研究","临床前","上市申请","I期临床",
    "II期临床","III期临床","毒代动力学","西药","生物等效"]
SPECIES = ["大鼠","小鼠","犬","beagle犬","猴","猩猩","豚鼠","家兔","仓鼠","小型猪","猪","猫","狗","雪貂"]
GUIDELINES = ["ICH S7A","ICH S7B","ICH S9","ICH S5(R3)","ICH S6(R1)","ICH S8","ICH S1A","ICH S1B",
    "ICH S1C","ICH S10","ICH E9","NMPA","CDE","EMA","WHO"]

REL_PAIRS = [
    ("化学药物","急性毒性试验"),("化学药物","长期毒性试验"),("化学药物","一般药理学试验"),
    ("化学药物","刺激性试验"),("化学药物","过敏性试验"),("化学药物","溶血性试验"),
    ("化学药物","药代动力学研究"),("化学药物","重复给药毒性试验"),
    ("中药","急性毒性试验"),("中药","长期毒性试验"),("中药","局部毒性试验"),
    ("中药","免疫毒性试验"),("中药","一般药理学试验"),("中药","刺激性试验"),("中药","溶血性试验"),
    ("生物制品","安全性评价"),("生物制品","临床前安全性"),
    ("治疗用生物制品","非临床安全性评价"),("预防用生物制品","临床前安全性评价"),
    ("纳米药物","非临床安全性研究"),("纳米药物","非临床药代动力学研究"),
    ("抗体偶联药物","非临床研究"),("脂质体药物","非临床药代动力学研究"),
    ("新药用辅料","非临床安全性评价"),
    ("急性毒性试验","LD50"),("急性毒性试验","最大给药量"),("急性毒性试验","死亡率"),
    ("长期毒性试验","NOAEL"),("长期毒性试验","毒性靶器官"),("长期毒性试验","重复给药"),
    ("生殖毒性试验","致畸试验"),("生殖毒性试验","围产期毒性"),
    ("致癌试验","剂量选择"),("致癌试验","NOAEL"),
    ("遗传毒性试验","Ames试验"),("遗传毒性试验","微核试验"),("遗传毒性试验","染色体畸变试验"),
    ("免疫毒性试验","过敏性试验"),("免疫毒性试验","光变态反应"),
    ("安全药理学试验","QT间期延长"),("安全药理学试验","心脏安全性"),
    ("药代动力学研究","AUC"),("药代动力学研究","Cmax"),("药代动力学研究","生物利用度"),
    ("药代动力学研究","半衰期"),
    ("刺激性试验","皮肤刺激"),("刺激性试验","眼刺激"),("刺激性试验","肌肉刺激"),
    ("ICH S7A","安全药理学试验"),("ICH S7B","QT间期延长"),("ICH S9","抗肿瘤药物"),
    ("ICH S5(R3)","生殖毒性"),("ICH S6(R1)","生物技术药物"),("ICH S8","免疫毒性"),
    ("ICH S1A","致癌试验"),("ICH S2(R1)","遗传毒性"),("ICH S10","光安全性评价"),
    ("GLP","安全性评价"),("GLP","长期毒性试验"),
    ("非临床安全性评价","临床试验"),
    ("犬","长期毒性试验"),("大鼠","长期毒性试验"),("大鼠","急性毒性试验"),
    ("小鼠","急性毒性试验"),("豚鼠","过敏性试验"),("家兔","刺激性试验"),
    ("毒代动力学","暴露量"),("毒代动力学","AUC"),("毒代动力学","Cmax"),
    ("单次给药毒性试验","LD50"),("单次给药毒性试验","最大给药量"),
    ("重复给药毒性试验","NOAEL"),("重复给药毒性试验","毒性靶器官"),
    ("QT间期延长","hERG通道"),("QT间期延长","心脏安全性"),
    ("纳米药物","质量控制"),("纳米药物","药代动力学"),
]

def extract_file_label(fname):
    name = fname.rsplit('.md',1)[0]
    parts = name.rsplit('_',1)
    if len(parts)>1 and len(parts[1])==8 and re.match(r'^[a-f0-9]+$',parts[1]):
        name=parts[0]
    return name

def process_file(fpath, fname):
    try:
        content = fpath.read_text(encoding='utf-8')
    except:
        try:
            content = fpath.read_text(encoding='gbk')
        except:
            content = ""
    nodes = []
    seen_ids = {}
    def add_node(et, label, loc="全文"):
        nid = f"{et}_{label}"
        if nid in seen_ids:
            return seen_ids[nid]
        seen_ids[nid] = nid
        nodes.append({
            "id": nid, "label": label, "type": et,
            "file_type": "document",
            "source_file": str(fpath.relative_to(ROOT)),
            "source_location": loc
        })
        return nid

    for dt in DRUG_TYPES:
        if dt in content:
            add_node("药物类型", dt)
    for st in TOX_STUDY_TYPES:
        if st in content:
            add_node("毒性试验类型", st)
    for ep in ENDPOINTS:
        if ep in content:
            add_node("毒性终点", ep)
    for tm in TEST_METHODS:
        if tm in content:
            add_node("检测方法", tm)
    for rc in REG_CONCEPTS:
        if rc in content:
            add_node("监管概念", rc)
    for sp in SPECIES:
        if sp in content:
            add_node("实验动物", sp)
    for gl in GUIDELINES:
        if gl in content:
            add_node("指导原则", gl)
    ichs = re.findall(r'ICH\s*[SsESQ]\d+(?:[RrR]\d+)?', content)
    for i in set(ichs):
        add_node("ICH指导原则", i)
    label = extract_file_label(fname)
    add_node("文档", label)
    return nodes

def build_edges(nodes, fname):
    edges = []
    nm = {n['label']: n['id'] for n in nodes}
    for src, tgt in REL_PAIRS:
        if src in nm and tgt in nm:
            edges.append({
                "source": nm[src], "target": nm[tgt],
                "relation": "addresses", "confidence": "EXTRACTED",
                "confidence_score": 0.95,
                "source_file": fname, "weight": 1.0
            })
    return edges

# ── Step 2: Detection ──────────────────────────────────────────────────────
print(f"\n[{ts}] Step 2: Detection")
detect_files = defaultdict(list)
src_exts = {'.pdf','.doc','.docx','.md'}
for fpath in ROOT.iterdir():
    if fpath.is_file() and fpath.suffix.lower() in src_exts:
        detect_files['document'].append(str(fpath))
for fpath in sorted(CONV.glob("*.md")):
    detect_files['document'].append(str(fpath))
detect_result = {
    "files": dict(detect_files),
    "total_files": sum(len(v) for v in detect_files.values()),
    "timestamp": ts
}
DETECT_PATH = Path("/tmp/.graphify_detect_anshang.json")
with open(DETECT_PATH, "w", encoding="utf-8") as f:
    json.dump(detect_result, f, ensure_ascii=False, indent=2)
print(f"  Detected {detect_result['total_files']} files")

# ── Step 3: Extraction ────────────────────────────────────────────────────
print(f"\n[{ts}] Step 3: Extraction")
all_nodes = []
all_edges = []
md_files = sorted(CONV.glob("*.md"))
清单 = ROOT / "📋_非临床安全性评价指导原则完整清单.md"
all_to_process = list(md_files) + ([清单] if 清单.exists() else [])

for i, fpath in enumerate(all_to_process):
    fname = fpath.name
    nodes = process_file(fpath, fname)
    edges = build_edges(nodes, fname)
    all_nodes.extend(nodes)
    all_edges.extend(edges)
    if (i+1) % 10 == 0:
        print(f"  {i+1}/{len(all_to_process)} files")

seen_ids = set()
deduped_nodes = []
for n in all_nodes:
    if n['id'] not in seen_ids:
        seen_ids.add(n['id'])
        deduped_nodes.append(n)
all_nodes = deduped_nodes

seen_edges = set()
deduped_edges = []
for e in all_edges:
    key = (e['source'], e['target'], e['relation'])
    if key not in seen_edges:
        seen_edges.add(key)
        deduped_edges.append(e)
all_edges = deduped_edges

SEM_PATH = Path("/tmp/.graphify_semantic.json")
semantic_data = {"nodes": all_nodes, "edges": all_edges, "hyperedges": []}
with open(SEM_PATH, "w", encoding="utf-8") as f:
    json.dump(semantic_data, f, ensure_ascii=False, indent=2)
print(f"  Semantic: {len(all_nodes)} nodes, {len(all_edges)} edges -> {SEM_PATH}")

# ── Step 4: Build graph ───────────────────────────────────────────────────
print(f"\n[{ts}] Step 4: Build graph")
import networkx as nx
G = nx.Graph()
for node in all_nodes:
    nid = node.get('id', '')
    if not nid:
        continue
    attrs = {k: v for k, v in node.items() if k != 'id'}
    G.add_node(nid, **attrs)
for edge in all_edges:
    src = edge.get('source', '')
    tgt = edge.get('target', '')
    if not src or not tgt:
        continue
    if src not in G:
        G.add_node(src)
    if tgt not in G:
        G.add_node(tgt)
    attrs = {k: v for k, v in edge.items() if k not in ('source', 'target')}
    G.add_edge(src, tgt, **attrs)
print(f"  Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# ── Step 5: Cluster ──────────────────────────────────────────────────────
print(f"\n[{ts}] Step 5: Cluster")
try:
    from networkx.algorithms.community import louvain_communities
    communities = louvain_communities(G, resolution=1.0, seed=42)
    communities = [list(c) for c in communities]
except Exception as e:
    print(f"  Louvain failed: {e}")
    communities = [list(c) for c in nx.connected_components(G)]
print(f"  {len(communities)} communities")

# Build community dict for graphify export
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

# ── Step 6: Analyze ──────────────────────────────────────────────────────
print(f"\n[{ts}] Step 6: Analyze")
degree_dict = dict(G.degree())
top_by_degree = sorted(degree_dict.items(), key=lambda x: x[1], reverse=True)[:30]
print(f"  Top node: {G.nodes[top_by_degree[0][0]].get('label', top_by_degree[0][0])} ({top_by_degree[0][1]} degree)")

def node_label(nid):
    return G.nodes[nid].get('label', G.nodes[nid].get('name', nid))
def node_type(nid):
    return G.nodes[nid].get('type', G.nodes[nid].get('entity_type', 'concept'))

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
        'nodes': [nid for nid, _ in node_degrees],
    })
comm_summaries.sort(key=lambda x: x['size'], reverse=True)
for cs in comm_summaries[:10]:
    print(f"  Community {cs['id']}: {cs['size']} nodes, top: {', '.join(cs['top_nodes'][:3])}")

# ── Step 7: Save outputs ────────────────────────────────────────────────
print(f"\n[{ts}] Step 7: Save outputs")

# Graph JSON
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

GRAPH_JSON_PATH = OUT / f"{PREFIX}_graph.json"
with open(GRAPH_JSON_PATH, "w", encoding="utf-8") as f:
    json.dump(graph_data, f, ensure_ascii=False, indent=2)
print(f"  Graph JSON: {GRAPH_JSON_PATH}")
shutil.copy(GRAPH_JSON_PATH, OUT / "anshang_graphify_semantic_cron_latest_graph.json")

# HTML using graphify's to_html
print(f"\n[{ts}] Generating HTML...")
try:
    from graphify.export import to_html
    # Build community labels
    community_labels = {}
    for cs in comm_summaries:
        cid = cs['id']
        top_types = list(cs['top_types'].keys())
        community_labels[cid] = f"Community{cid}:{','.join(top_types[:2])}"
    
    HTML_PATH = str(OUT / f"{PREFIX}.html")
    to_html(G, communities=communities_dict, output_path=HTML_PATH, community_labels=community_labels)
    shutil.copy(HTML_PATH, str(OUT / "anshang_graphify_semantic_cron_latest.html"))
    print(f"  HTML: {HTML_PATH}")
except Exception as e:
    print(f"  [!] HTML error: {e}")
    # Fallback: build simple HTML
    HTML_PATH = None

# Report using graphify's generate
print(f"\n[{ts}] Generating report...")
try:
    from graphify.report import generate
    from datetime import date
    
    # Build god nodes list
    god_node_list = []
    for nid, deg in top_by_degree[:20]:
        god_node_list.append({
            "label": node_label(nid),
            "type": node_type(nid),
            "edges": deg,
            "community": node_community.get(nid, -1),
        })
    
    # Surprising connections
    surprise_list = []
    
    # Community labels
    community_labels = {}
    for cs in comm_summaries:
        cid = cs['id']
        top_types = list(cs['top_types'].keys())
        community_labels[cid] = f"Community{cid}:{','.join(top_types[:2])}"
    
    token_cost = {"input": 0, "output": 0}
    
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
    REPORT_PATH = OUT / f"GRAPH_REPORT_安评_{PREFIX}.md"
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_md)
    shutil.copy(REPORT_PATH, OUT / "GRAPH_REPORT_安评_graphify_semantic_cron_latest.md")
    print(f"  Report: {REPORT_PATH}")
except Exception as e:
    print(f"  [!] Report error: {e}")
    # Fallback: build simple report
    report_lines = [
        f"# Graph Report - 安评_anshang ({time.strftime('%Y-%m-%d')})",
        "",
        "## Summary",
        f"- {G.number_of_nodes()} nodes · {G.number_of_edges()} edges · {len(communities)} communities",
        "",
        "## Top Nodes by Degree",
    ]
    for nid, deg in top_by_degree[:15]:
        report_lines.append(f"- {node_label(nid)} ({node_type(nid)}) - {deg} edges")
    report_lines += ["", "## Community Summaries"]
    for cs in comm_summaries[:15]:
        report_lines.append(f"\n### Community {cs['id']} ({cs['size']} nodes, cohesion={cs['cohesion']})")
        report_lines.append(f"Types: {dict(cs['top_types'])}")
        report_lines.append(f"Top nodes: {', '.join(cs['top_nodes'][:5])}")
    REPORT_PATH = OUT / f"GRAPH_REPORT_安评_{PREFIX}.md"
    REPORT_PATH.write_text("\n".join(report_lines), encoding="utf-8")
    shutil.copy(REPORT_PATH, OUT / "GRAPH_REPORT_安评_graphify_semantic_cron_latest.md")
    print(f"  Report (simple): {REPORT_PATH}")

# Also save semantic with metadata
semantic_full = {
    "nodes": all_nodes, "edges": all_edges,
    "metadata": {
        "total_files": len(all_to_process), "total_nodes": len(all_nodes),
        "total_edges": len(all_edges), "communities": len(communities), "timestamp": ts
    }
}
SEM_FULL_PATH = OUT / f"{PREFIX}_semantic.json"
with open(SEM_FULL_PATH, "w", encoding="utf-8") as f:
    json.dump(semantic_full, f, ensure_ascii=False, indent=2)
shutil.copy(SEM_FULL_PATH, OUT / "anshang_graphify_semantic_cron_latest_semantic.json")

# ── Step 8: Write DONE ───────────────────────────────────────────────────
DONE_PATH = Path("/tmp/.graphify_done.txt")
DONE_PATH.write_text("DONE", encoding="utf-8")
print(f"\n[{ts}] DONE written to {DONE_PATH}")
print(f"\n=== Pipeline Complete ===")
print(f"  Prefix: {PREFIX}")
print(f"  Nodes: {len(all_nodes)}, Edges: {len(all_edges)}, Communities: {len(communities)}")
print(f"  Graph JSON: {GRAPH_JSON_PATH}")
if HTML_PATH:
    print(f"  HTML: {HTML_PATH}")
print(f"  Report: {REPORT_PATH}")
