#!/usr/bin/env python3
"""
Graphify Pipeline for 安评 - Full Run
"""
import json, os, re, sys, math
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import hashlib

CORPUS_DIR = Path("/home/wangyc/Documents/工作/法规指导原则/安评")
OUT_DIR = CORPUS_DIR / "graphify-out"
OUT_DIR.mkdir(exist_ok=True)
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
CONVERTED_DIR = OUT_DIR / "converted"

print(f"[{TS}] === Graphify Pipeline START (安评) ===")

# ─── Step 1: Detection ──────────────────────────────────────────────────────────
print("\n[Step 1] Detection...")
DETECT_PATH = Path('/tmp/.graphify_detect_anshang.json')
try:
    from graphify.detect import detect
    det_result = detect(CORPUS_DIR)
    with open(DETECT_PATH, 'w') as f:
        json.dump(det_result, f, ensure_ascii=False, indent=2)
    print(f"  Detection done: {len(det_result.get('files', []))} files")
except Exception as e:
    print(f"  Detection error: {e}")
    md_files = list(CONVERTED_DIR.glob("*.md"))
    det_result = {'files': [{'path': str(f)} for f in md_files]}
    with open(DETECT_PATH, 'w') as f:
        json.dump(det_result, f, ensure_ascii=False, indent=2)
    print(f"  Fallback: {len(md_files)} files")

# ─── Step 2: Semantic Extraction ───────────────────────────────────────────────
print("\n[Step 2] Semantic extraction from 70 .md files...")

SEMANTIC_PATH = Path('/tmp/.graphify_semantic.json')
SEMANTIC_CANDIDATES = [
    OUT_DIR / "surprising_semantic_cron_final.json",
    OUT_DIR / "surprising_connections_semantic_full.json",
    OUT_DIR / "surprising_semantic_cron_latest.json",
]
semantic_data = None
for p in SEMANTIC_CANDIDATES:
    if p.exists():
        try:
            with open(p) as f:
                d = json.load(f)
            n_nodes = len(d.get('nodes', []))
            if n_nodes > 100:
                semantic_data = d
                print(f"  Using existing cache: {p.name} ({n_nodes} nodes)")
                break
        except:
            pass

if semantic_data is None:
    print("  No cache found, extracting all 70 files...")
    
    DRUG_TYPES = [
        "化学药物", "中药", "天然药物", "生物制品", "治疗用生物制品", "预防用生物制品",
        "抗体偶联药物", "纳米药物", "脂质体药物", "新药用辅料", "生物技术药品",
        "抗肿瘤药物", "化学药品", "疫苗", "血液制品", "重组蛋白质", "单克隆抗体",
        "细胞因子", "基因治疗", "组织工程", "小核酸药物", "多肽药物", "抗体药物",
        "ADC", "纳米制剂", "先进治疗产品",
    ]
    STUDY_TYPES = [
        "急性毒性", "长期毒性", "重复给药毒性", "生殖毒性", "发育毒性", "致癌性",
        "致癌试验", "遗传毒性", "基因毒性", "致突变性", "光毒性", "光安全性",
        "刺激性", "过敏性", "溶血性", "免疫毒性", "过敏反应", "光变态反应",
        "安全药理学", "一般药理学", "药代动力学", "毒代动力学",
        "临床前安全性评价", "非临床安全性评价", "毒理学", "安全性评价",
        "局部毒性", "全身毒性", "单次给药毒性", "毒理动力学研究",
        "呼吸毒性", "神经毒性", "肾毒性", "肝毒性", "心脏毒性",
        "血液学毒性", "免疫抑制", "免疫增强", "溶血",
        "照片过敏", "光遗传毒性", "光致癌", "三致",
    ]
    ENDPOINTS = [
        "给药方式", "给药途径", "剂量设计", "剂量选择", "给药剂量", "暴露量",
        "AUC", "Cmax", "半衰期", "生物利用度", "血药浓度",
        "NOAEL", "NOEL", "最大无毒性反应剂量", "未见毒性反应剂量",
        "MTD", "最大耐受剂量", "毒性靶器官", "毒性表现", "不良反应",
        "安全性评价", "风险评估", "获益风险比", "临床试验", "IND", "NDA",
        "GLP", "质量管理规范", "实验动物", "动物种属", "实验设计",
        "恢复期", "停药", "解剖检查", "组织病理学", "病理检查",
        "血液学", "血液生化", "尿液分析", "免疫学", "免疫功能",
        "心电图", "ECG", "QT间期", "心室复极化", "QTc",
        "生殖器官", "胚胎", "胎儿", "畸形", "死胎", "流产",
        "Ames试验", "微核试验", "染色体畸变", "基因突变",
        "体外哺乳动物细胞", "体内染色体", "骨髓微核", "彗星试验",
        "体外代谢", "体内代谢", "代谢产物", "血浆蛋白结合",
        "排泄", "尿液", "粪便", "胆汁", "积蓄性",
        "免疫原性", "抗体生成", "细胞免疫", "体液免疫",
        "补体", "皮肤", "肌肉", "静脉", "皮下", "口服", "腹腔", "吸入", "经皮",
        "Beagle犬", "食蟹猴", "恒河猴", "大鼠", "小鼠", "家兔", "豚鼠", "小型猪",
        "杂质", "降解产物", "残留溶剂", "起始材料", "辅料", "制剂", "给药系统",
        "心率", "血压", "呼吸频率", "体温",
        "ICH", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10", "E9",
        "受试物", "供试品", "对照组", "溶剂", "赋形剂",
        "起始剂量", "最高剂量", "中剂量", "低剂量", "等效剂量",
        "安全系数", "人体等效剂量", "HED", "体表面积",
        "雌性", "雄性", "妊娠", "幼年", "成年", "老年",
        "一周", "一个月", "三个月", "六个月", "一年", "长期", "短期",
        "亚慢性", "亚急性", "慢性", "急性",
        "连续给药", "间歇给药", "空腹", "进食",
        "体重", "摄食量", "摄水量", "临床观察",
        "眼科检查", "听力检查", "血液学检查", "血液生化检查",
        "尿液检查", "大便检查", "器官重量", "脏器系数",
        "大体解剖", "组织学", "病理学", "毒性病理",
        "致畸", "促癌", "致畸性", "致癌",
        "胚胎毒性", "胎儿毒性", "胎仔毒性", "子代毒性",
        "亲代", "F1代", "F2代", "围产期", "哺乳期",
        "生育力", "着床", "妊娠率", "流产率", "死产率", "活产率",
        "致畸敏感期", "器官形成期", "着床前", "胚胎期", "胎儿期",
    ]
    REG_CONCEPTS = [
        "GLP", "GCP", "GMP", "IND", "NDA", "CTD", "ICHS", "ICH E9", "ICH S5",
        "药物非临床研究质量管理规范", "药品注册", "生物利用度", "生物等效性",
        "等效性评价", "生物等效", "豁免", "简化申请",
        "致癌试验", "繁殖试验", "一代繁殖试验", "二代繁殖试验",
        "致畸试验", "急性经口毒性", "急性经皮毒性", "急性吸入毒性",
        "急性静脉毒性", "急性腹腔毒性", "急性皮下毒性", "急性肌肉毒性",
        " Ames", "微核", "染色体畸变", "基因突变", "彗星", "转基因",
        "体外溶血", "体内溶血", "红细胞", "血小板", "凝血功能",
        "网织红细胞", "骨髓", "脾脏", "胸腺", "淋巴结",
        "光毒性试验", "光过敏试验", "光刺激试验", "光遗传毒性试验",
        "安全药理学核心组合", "hERG", "心脏传导", "中枢神经系统", "呼吸系统",
        "镀银染色", "特殊染色", "免疫组化", "原位杂交",
    ]
    
    all_entities = set()
    all_relations = []
    md_files = sorted(CONVERTED_DIR.glob("*.md"))
    
    for idx, md_file in enumerate(md_files):
        if idx % 10 == 0:
            print(f"  Processing {idx+1}/{len(md_files)}: {md_file.name[:50]}")
        try:
            content = md_file.read_text(encoding='utf-8', errors='ignore')
        except:
            try:
                content = md_file.read_text(encoding='gbk', errors='ignore')
            except:
                content = ""
        
        if not content or len(content) < 50:
            continue
        
        # Extract document title/identifier
        doc_name = md_file.stem.split('_')[0] if '_' in md_file.stem else str(md_file)
        # Truncate hash suffix for cleaner names
        stem = md_file.stem
        for i in range(len(stem)-8, -1, -1):
            if stem[i] == '_' and i > 0 and len(stem) - i == 9:
                doc_name = stem[:i]
                break
        
        entities_in_doc = defaultdict(list)
        
        # Match drug types
        for dt in DRUG_TYPES:
            if dt in content:
                all_entities.add(f"药物类型:{dt}")
                entities_in_doc['drug_type'].append(dt)
        
        # Match study types
        for st in STUDY_TYPES:
            if st in content:
                all_entities.add(f"研究类型:{st}")
                entities_in_doc['study_type'].append(st)
        
        # Match endpoints
        for ep in ENDPOINTS:
            if ep in content:
                all_entities.add(f"评价指标:{ep}")
                entities_in_doc['endpoint'].append(ep)
        
        # Match regulatory concepts
        for rc in REG_CONCEPTS:
            if rc in content:
                all_entities.add(f"法规概念:{rc}")
                entities_in_doc['reg_concept'].append(rc)
        
        # Build relationships based on co-occurrence in sections
        # If drug type and study type appear, they are related
        drug_in_doc = list(set(entities_in_doc.get('drug_type', [])))
        study_in_doc = list(set(entities_in_doc.get('study_type', [])))
        endpoint_in_doc = list(set(entities_in_doc.get('endpoint', [])))
        
        for dt in drug_in_doc:
            all_relations.append({
                'source': f'文件:{doc_name}', 'target': f'药物类型:{dt}', 'type': 'addresses'
            })
        for st in study_in_doc:
            all_relations.append({
                'source': f'文件:{doc_name}', 'target': f'研究类型:{st}', 'type': 'addresses'
            })
        for ep in endpoint_in_doc:
            all_relations.append({
                'source': f'文件:{doc_name}', 'target': f'评价指标:{ep}', 'type': 'addresses'
            })
        
        # Cross-relationships: drug type <-> study type
        for dt in drug_in_doc:
            for st in study_in_doc:
                all_relations.append({
                    'source': f'药物类型:{dt}', 'target': f'研究类型:{st}', 'type': 'evaluates'
                })
        # Study type <-> endpoint
        for st in study_in_doc:
            for ep in endpoint_in_doc:
                all_relations.append({
                    'source': f'研究类型:{st}', 'target': f'评价指标:{ep}', 'type': 'requires'
                })
        # Drug type <-> reg concept
        for dt in drug_in_doc:
            for rc in entities_in_doc.get('reg_concept', []):
                all_relations.append({
                    'source': f'药物类型:{dt}', 'target': f'法规概念:{rc}', 'type': 'references'
                })
    
    # Deduplicate
    unique_nodes = sorted(all_entities)
    seen_rels = set()
    unique_rels = []
    for rel in all_relations:
        key = (rel['source'], rel['target'], rel['type'])
        if key not in seen_rels:
            seen_rels.add(key)
            unique_rels.append(rel)
    
    nodes = [{'id': n, 'label': n, 'category': n.split(':')[0] if ':' in n else 'unknown'} for n in unique_nodes]
    edges = unique_rels
    
    semantic_data = {'nodes': nodes, 'edges': edges}
    with open(SEMANTIC_PATH, 'w') as f:
        json.dump(semantic_data, f, ensure_ascii=False, indent=2)
    print(f"  Extracted {len(nodes)} nodes, {len(edges)} edges → {SEMANTIC_PATH}")

nodes = semantic_data.get('nodes', [])
edges = semantic_data.get('edges', [])
print(f"  Semantic: {len(nodes)} nodes, {len(edges)} edges")

# ─── Step 3: Build Graph ───────────────────────────────────────────────────────
print("\n[Step 3] Building graph...")
import networkx as nx
G = nx.Graph()
node_id_map = {}

for node in nodes:
    nid = node.get('id') or node.get('name') or ''
    if not nid:
        continue
    node_id_map[nid] = nid
    attrs = {k: v for k, v in node.items() if k != 'id'}
    G.add_node(nid, **attrs)

edge_count = 0
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
    rel_type = attrs.pop('type', 'related_to')
    G.add_edge(src, tgt, relation=rel_type, **attrs)
    edge_count += 1

print(f"  Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# ─── Step 4: Cluster ───────────────────────────────────────────────────────────
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

# Compute cohesion scores
cohesion_scores = {}
for i, comm in enumerate(communities):
    if len(comm) < 2:
        cohesion_scores[i] = 0.0
    else:
        subgraph = G.subgraph(comm)
        possible = len(comm) * (len(comm) - 1) / 2
        actual = subgraph.number_of_edges()
        cohesion_scores[i] = round(actual / possible, 3) if possible > 0 else 0.0

# Assign categories
category_groups = defaultdict(list)
for node in G.nodes():
    cat = G.nodes[node].get('category', 'unknown')
    category_groups[cat].append(node)

# ─── Step 5: Analysis ──────────────────────────────────────────────────────────
print("\n[Step 5] Analysis...")
degree_dict = dict(G.degree())
top_degree = sorted(degree_dict.items(), key=lambda x: x[1], reverse=True)[:20]
print(f"  Top 5 nodes by degree: {top_degree[:5]}")

# ICH standards analysis
ich_nodes = [n for n in G.nodes() if 'ICH' in str(n) or 'S1' in str(n) or 'S2' in str(n) or 'S5' in str(n) or 'S6' in str(n) or 'S7' in str(n) or 'S8' in str(n) or 'S9' in str(n) or 'S10' in str(n)]
print(f"  ICH-related nodes: {len(ich_nodes)}")

# Study type analysis
study_type_nodes = [n for n in G.nodes() if '研究类型:' in str(n)]
print(f"  Study type nodes: {len(study_type_nodes)}")

# Drug type analysis
drug_type_nodes = [n for n in G.nodes() if '药物类型:' in str(n)]
print(f"  Drug type nodes: {len(drug_type_nodes)}")

# Community summary
community_summary = {}
for i, comm in enumerate(communities):
    cats = defaultdict(int)
    for node in comm:
        cats[G.nodes[node].get('category','unknown')] += 1
    community_summary[i] = {
        'size': len(comm),
        'cohesion': cohesion_scores[i],
        'categories': dict(cats),
        'sample_nodes': list(comm)[:5]
    }

analysis_data = {
    'total_nodes': G.number_of_nodes(),
    'total_edges': G.number_of_edges(),
    'total_communities': len(communities),
    'top_degree_nodes': [{'node': n, 'degree': d} for n, d in top_degree],
    'ich_nodes_count': len(ich_nodes),
    'study_type_nodes_count': len(study_type_nodes),
    'drug_type_nodes_count': len(drug_type_nodes),
    'community_summary': community_summary,
    'category_groups': {k: len(v) for k, v in category_groups.items()},
}

# ─── Step 6: Generate HTML ─────────────────────────────────────────────────────
print("\n[Step 6] Generating HTML...")

html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>非临床安全性评价指导原则知识图谱</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; background: #0d1117; color: #e6edf3; }}
.header {{ background: linear-gradient(135deg, #1a1f2e, #2d3748); padding: 24px 32px; border-bottom: 1px solid #30363d; }}
.header h1 {{ color: #58a6ff; font-size: 1.5rem; margin-bottom: 8px; }}
.header p {{ color: #8b949e; font-size: 0.9rem; }}
.stats {{ display: flex; gap: 32px; padding: 16px 32px; background: #161b22; border-bottom: 1px solid #30363d; }}
.stat {{ text-align: center; }}
.stat .num {{ font-size: 1.8rem; font-weight: bold; color: #58a6ff; }}
.stat .label {{ font-size: 0.75rem; color: #8b949e; text-transform: uppercase; }}
.container {{ display: flex; height: calc(100vh - 140px); }}
#graph {{ flex: 1; border-right: 1px solid #30363d; }}
#sidebar {{ width: 320px; overflow-y: auto; padding: 16px; background: #0d1117; }}
#sidebar h3 {{ color: #58a6ff; margin-bottom: 12px; font-size: 0.9rem; text-transform: uppercase; }}
.community-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; margin-bottom: 10px; }}
.community-card h4 {{ color: #e6edf3; font-size: 0.85rem; margin-bottom: 6px; }}
.community-card .badge {{ display: inline-block; background: #238636; color: #fff; border-radius: 12px; padding: 2px 8px; font-size: 0.7rem; margin-right: 4px; }}
.community-card .nodes {{ font-size: 0.75rem; color: #8b949e; margin-top: 6px; line-height: 1.6; }}
.controls {{ padding: 12px 32px; background: #161b22; border-top: 1px solid #30363d; }}
.controls button {{ background: #238636; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; margin-right: 8px; font-size: 0.85rem; }}
.controls button:hover {{ background: #2ea043; }}
.search-box {{ padding: 12px 32px; background: #161b22; border-top: 1px solid #30363d; }}
.search-box input {{ background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 8px 12px; border-radius: 6px; width: 300px; font-size: 0.85rem; }}
#node-info {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; margin-top: 16px; font-size: 0.8rem; }}
#node-info h4 {{ color: #58a6ff; margin-bottom: 8px; }}
</style>
</head>
<body>
<div class="header">
  <h1>🧬 非临床安全性评价指导原则知识图谱</h1>
  <p>基于 {len(nodes)} 个实体节点 · {len(edges)} 条关系边 · {len(communities)} 个社区聚类</p>
</div>
<div class="stats">
  <div class="stat"><div class="num">{G.number_of_nodes()}</div><div class="label">实体节点</div></div>
  <div class="stat"><div class="num">{G.number_of_edges()}</div><div class="label">关系边</div></div>
  <div class="stat"><div class="num">{len(communities)}</div><div class="label">社区聚类</div></div>
  <div class="stat"><div class="num">{len(drug_type_nodes)}</div><div class="label">药物类型</div></div>
  <div class="stat"><div class="num">{len(study_type_nodes)}</div><div class="label">研究类型</div></div>
  <div class="stat"><div class="num">{len(ich_nodes)}</div><div class="label">ICH标准</div></div>
</div>
<div class="container">
  <div id="graph"></div>
  <div id="sidebar">
    <h3>📊 社区聚类 ({len(communities)})</h3>
"""

for i, comm in enumerate(sorted(community_summary.items(), key=lambda x: x[1]['size'], reverse=True)[:15]):
    ci, info = comm
    cats_str = ' '.join([f'<span class="badge">{k}:{v}</span>' for k, v in list(info['categories'].items())[:3]])
    nodes_str = ' · '.join(str(n)[:30] for n in info['sample_nodes'])
    html_content += f"""    <div class="community-card" onclick="focusCommunity({ci})">
      <h4>社区 #{ci+1} <span style="color:#8b949e;font-size:0.75rem">({info['size']} 节点 · 聚合度 {info['cohesion']})</span></h4>
      <div>{cats_str}</div>
      <div class="nodes">{nodes_str}</div>
    </div>
"""

html_content += """  </div>
</div>
<div class="search-box">
  <input type="text" id="search" placeholder="🔍 搜索实体节点..." oninput="searchNodes(this.value)">
</div>
<div class="controls">
  <button onclick="resetView()">重置视图</button>
  <button onclick="togglePhysics()">切换物理引擎</button>
  <button onclick="showCommunities()">按社区着色</button>
  <button onclick="showCategories()">按类别着色</button>
</div>
<script>
"""

# Build nodes and edges for vis.js
vis_nodes = []
vis_edges = []
category_colors = {
    '药物类型': '#f97316',
    '研究类型': '#22c55e',
    '评价指标': '#3b82f6',
    '法规概念': '#a855f7',
    '文件': '#eab308',
    'unknown': '#6b7280',
}
community_colors = []
import matplotlib; import matplotlib.pyplot as plt
cmap = matplotlib.pyplot.get_cmap('tab20')
for i in range(len(communities)):
    rgba = cmap(i % 20)
    community_colors.append(f'rgba({int(rgba[0]*255)},{int(rgba[1]*255)},{int(rgba[2]*255)},0.8)')

for node in G.nodes():
    cat = G.nodes[node].get('category', 'unknown')
    comm = node_community.get(node, 0)
    color = category_colors.get(cat, '#6b7280')
    vis_nodes.append({
        'id': node, 'label': str(node)[:40],
        'color': color, 'category': cat,
        'community': comm,
        'degree': degree_dict.get(node, 1),
        'font': {'color': '#e6edf3', 'size': 11 if degree_dict.get(node, 1) > 5 else 9},
        'size': min(3 + degree_dict.get(node, 1) * 0.3, 25),
    })

edge_rel_colors = {
    'addresses': '#58a6ff', 'evaluates': '#22c55e', 'requires': '#f97316',
    'references': '#a855f7', 'related_to': '#6b7280',
}
for src, tgt, data in G.edges(data=True):
    rel = data.get('relation', 'related_to')
    vis_edges.append({
        'from': src, 'to': tgt,
        'color': {'color': edge_rel_colors.get(rel, '#6b7280'), 'opacity': 0.4},
        'arrows': 'to', 'smooth': {'type': 'continuous'},
    })

html_content += f"""var nodes = new vis.DataSet({json.dumps(vis_nodes, ensure_ascii=False)});
var edges = new vis.DataSet({json.dumps(vis_edges, ensure_ascii=False)});
var container = document.getElementById('graph');
var data = {{ nodes: nodes, edges: edges }};
var options = {{
  nodes: {{ borderWidth: 1, shadow: true, font: {{ multi: true }}}},
  edges: {{ width: 1, shadow: true }},
  physics: {{ enabled: true, barnesHut: {{ gravitationalConstant: -8000, centralGravity: 0.005, springLength: 120, springConstant: 0.04 }},
              solver: 'barnesHut', stabilization: {{ iterations: 100 }} }},
  layout: {{ improvedLayout: true }},
  interaction: {{ hover: true, tooltipDelay: 200, navigationButtons: true }},
}};
var network = new vis.Network(container, data, options);
var physicsOn = true;
network.on('click', function(params) {{
  if (params.nodes.length > 0) {{
    var nodeId = params.nodes[0];
    var node = nodes.get(nodeId);
    showNodeInfo(node);
  }}
}});
function showNodeInfo(node) {{
  var infoDiv = document.getElementById('node-info') || document.createElement('div');
  infoDiv.id = 'node-info';
  infoDiv.innerHTML = '<h4>' + node.label + '</h4><p>类别: ' + node.category + '</p><p>社区: ' + node.community + '</p><p>度数: ' + node.degree + '</p>';
  document.getElementById('sidebar').appendChild(infoDiv);
}}
function resetView() {{ network.fit(); }}
function togglePhysics() {{ physicsOn = !physicsOn; network.setOptions({{ physics: {{ enabled: physicsOn }} }}); }}
function showCommunities() {{
  nodes.forEach(function(n) {{
    n.color = '{community_colors[0]}'.replace('0)', n.community + ')');
  }});
  nodes.refresh(nodes);
}}
function showCategories() {{
  nodes.forEach(function(n) {{
    var catColors = {json.dumps(category_colors, ensure_ascii=False)};
    n.color = catColors[n.category] || '#6b7280';
  }});
  nodes.refresh(nodes);
}}
function focusCommunity(c) {{
  var nodesInComm = nodes.get({{ filter: function(n) {{ return n.community === c; }} }});
  if (nodesInComm.length > 0) {{
    network.selectNodes(nodesInComm.map(function(n) {{ return n.id; }}));
  }}
}}
function searchNodes(q) {{
  if (!q) {{ nodes.forEach(function(n) {{ n.font = {{ color: '#e6edf3', size: 11 if n.degree > 5 else 9 }}; }}); nodes.refresh(nodes); return; }}
  nodes.forEach(function(n) {{
    if (n.label.toLowerCase().includes(q.toLowerCase())) {{
      n.font = {{ color: '#ffd700', size: 14, face: 'bold' }};
      n.size = n.size * 1.3;
    }} else {{
      n.font = {{ color: '#6b7280', size: 9 }};
      n.size = n.size * 0.8;
    }}
  }});
  nodes.refresh(nodes);
}}
network.once('stabilizationIterationsDone', function() {{ console.log('Graph loaded'); }});
</script>
</body>
</html>"""

html_path = OUT_DIR / f"知识图谱_anshang_graphify_semantic_cron_{TS}.html"
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html_content)
print(f"  HTML saved: {html_path.name}")

latest_html = OUT_DIR / "知识图谱_anshang_graphify_semantic_cron_latest.html"
with open(latest_html, 'w', encoding='utf-8') as f:
    f.write(html_content)
print(f"  Latest HTML symlink updated")

# ─── Step 7: Save Graph JSON ───────────────────────────────────────────────────
print("\n[Step 7] Saving graph JSON...")
graph_data = {
    'nodes': [{'id': n, **G.nodes[n]} for n in G.nodes()],
    'edges': [{'source': u, 'target': v, **d} for u, v, d in G.edges(data=True)],
    'metadata': {
        'generated': TS,
        'total_nodes': G.number_of_nodes(),
        'total_edges': G.number_of_edges(),
        'total_communities': len(communities),
    }
}
graph_json_path = OUT_DIR / f"知识图谱_anshang_graphify_semantic_cron_{TS}_graph.json"
with open(graph_json_path, 'w', encoding='utf-8') as f:
    json.dump(graph_data, f, ensure_ascii=False, indent=2)

latest_graph_json = OUT_DIR / "知识图谱_anshang_graphify_semantic_cron_latest_graph.json"
with open(latest_graph_json, 'w', encoding='utf-8') as f:
    json.dump(graph_data, f, ensure_ascii=False, indent=2)
print(f"  Graph JSON saved")

# ─── Step 8: Save Analysis JSON ────────────────────────────────────────────────
print("\n[Step 8] Saving analysis JSON...")
analysis_path = OUT_DIR / f"知识图谱_anshang_graphify_semantic_cron_{TS}_analysis.json"
with open(analysis_path, 'w', encoding='utf-8') as f:
    json.dump(analysis_data, f, ensure_ascii=False, indent=2)
latest_analysis = OUT_DIR / "知识图谱_anshang_graphify_semantic_cron_latest_analysis.json"
with open(latest_analysis, 'w', encoding='utf-8') as f:
    json.dump(analysis_data, f, ensure_ascii=False, indent=2)
print(f"  Analysis JSON saved")

# ─── Step 9: Generate GRAPH_REPORT.md ─────────────────────────────────────────
print("\n[Step 9] Generating GRAPH_REPORT.md...")
report = f"""# 非临床安全性评价指导原则知识图谱分析报告

**生成时间**: {TS}
**数据来源**: {CORPUS_DIR}

## 图谱概览

| 指标 | 数值 |
|------|------|
| 实体节点数 | {G.number_of_nodes()} |
| 关系边数 | {G.number_of_edges()} |
| 社区聚类数 | {len(communities)} |
| 药物类型数 | {len(drug_type_nodes)} |
| 研究类型数 | {len(study_type_nodes)} |
| ICH标准相关节点数 | {len(ich_nodes)} |

## 高影响力节点 (Top 20 度中心性)

| 排名 | 节点 | 度数 |
|------|------|------|
"""

for rank, (node_name, degree) in enumerate(top_degree, 1):
    report += f"| {rank} | {node_name} | {degree} |\n"

report += f"""
## 社区聚类分析

共发现 **{len(communities)}** 个社区，最大社区包含 {max(len(c) for c in communities)} 个节点。

"""

for rank, (ci, info) in enumerate(sorted(community_summary.items(), key=lambda x: x[1]['size'], reverse=True)[:10], 1):
    cats_str = ' · '.join([f'{k}:{v}' for k, v in sorted(info['categories'].items(), key=lambda x: x[1], reverse=True)])
    report += f"""### 社区 {ci+1} ({info['size']} 节点, 聚合度 {info['cohesion']})

**类别分布**: {cats_str}

**代表节点**: {', '.join(str(n)[:40] for n in info['sample_nodes'])}

"""

report += f"""
## 类别分布

| 类别 | 节点数 |
|------|--------|
"""
for cat, count in sorted(category_groups.items(), key=lambda x: x[1], reverse=True):
    report += f"| {cat} | {count} |\n"

report += f"""
## ICH 标准体系

图谱涵盖以下 ICH 指导原则相关节点：S1(致癌)、S2(基因毒性)、S5(生殖毒性)、S6(生物制品)、S7(安全药理学)、S8(免疫毒性)、S9(抗肿瘤药物)、S10(光安全性)。

## 输出文件

- HTML图谱: `知识图谱_anshang_graphify_semantic_cron_{TS}.html`
- Graph JSON: `知识图谱_anshang_graphify_semantic_cron_{TS}_graph.json`
- Analysis JSON: `知识图谱_anshang_graphify_semantic_cron_{TS}_analysis.json`
"""

report_path = OUT_DIR / f"GRAPH_REPORT_anshang_graphify_semantic_cron_{TS}.md"
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(report)
latest_report = OUT_DIR / "GRAPH_REPORT_anshang_graphify_semantic_cron_latest.md"
with open(latest_report, 'w', encoding='utf-8') as f:
    f.write(report)
print(f"  Report saved: {report_path.name}")

# ─── Step 10: Write DONE ───────────────────────────────────────────────────────
DONE_PATH = Path('/tmp/.graphify_done.txt')
with open(DONE_PATH, 'w') as f:
    f.write('DONE')
print(f"\n[DONE] All steps complete. DONE written to {DONE_PATH}")
print(f"[{TS}] === Graphify Pipeline FINISH ===")
