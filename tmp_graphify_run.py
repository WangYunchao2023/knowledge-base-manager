#!/usr/bin/env python3
import json, re
from pathlib import Path

def slug(text):
    s = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]+', '_', text.strip())
    return s.strip('_').lower()

def extract_entities(text, fname, ftype="document"):
    fname_clean = re.sub(r'\s+', ' ', fname)
    nodes = []
    edges = []

    def node(label, category, extra=None):
        nodes.append({
            "id": slug(label),
            "label": label,
            "category": category,
            "source_file": fname_clean,
            "file_type": ftype,
            **(extra or {})
        })
        return slug(label)

    def edge(src, tgt, rel, conf="EXTRACTED"):
        edges.append({
            "source": src, "target": tgt, "relation": rel,
            "confidence": conf, "source_file": fname_clean
        })

    doc_name = fname.replace('.md', '').strip()
    doc_node = node(doc_name, "指导原则", {"doc_name": doc_name})

    drug_types = [
        ("化学药物","chemical_drug"), ("中药","traditional_chinese_medicine"),
        ("天然药物","natural_drug"), ("生物制品","biologics"),
        ("预防用生物制品","preventive_biologics"), ("治疗用生物制品","therapeutic_biologics"),
        ("疫苗","vaccine"), ("基因治疗产品","gene_therapy"),
        ("细胞治疗产品","cell_therapy"), ("抗体偶联药物","adc"),
        ("纳米药物","nano_drug"), ("放射性药物","radiopharmaceutical"),
        ("中药、天然药物","traditional_chinese_medicine"), ("复方药物","compound_drug"),
        ("血液制品","blood_product"), ("抗体药物","antibody_drug"), ("肽类药物","peptide_drug"),
    ]
    found_drugs = set()
    for name, dtype in drug_types:
        if name in text and name not in found_drugs:
            found_drugs.add(name)
            dn = node(name, "药物类型", {"drug_type": dtype})
            if dn != doc_node:
                edge(doc_node, dn, "addresses")

    tox_types = [
        "急性毒性", "长期毒性", "生殖毒性", "致癌性", "致突变性",
        "免疫毒性", "过敏性", "光变态反应", "局部刺激性", "溶血性",
        "一般药理学", "安全性药理", "毒代动力学", "药代动力学",
        "重复给药毒性", "单次给药毒性", "免疫原性", "光毒性",
        "依赖性", "特种毒性", "挥发性", "热原反应", "异常毒性",
    ]
    found_tox = set()
    for name in tox_types:
        if name in text and name not in found_tox:
            found_tox.add(name)
            tn = node(name, "毒性试验类型")
            edge(doc_node, tn, "addresses")

    species_map = {
        "大鼠":"rat", "小鼠":"mouse", "家兔":"rabbit", "犬":"dog",
        "Beagle犬":"beagle_dog",
        "豚鼠":"guinea_pig", "仓鼠":"hamster", "小型猪":"minipig",
        "恒河猴":"rhesus_monkey", "食蟹猴":"cynomolgus",
        "雪貂":"ferret", "猪":"pig",
        "Wistar大鼠":"wistar_rat", "SD大鼠":"sd_rat",
        "C57BL/6小鼠":"c57bl6_mouse", "新西兰兔":"new_zealand_rabbit",
    }
    found_species = set()
    for key, val in species_map.items():
        if key in text and key not in found_species:
            found_species.add(key)
            sn = node(key, "实验动物")
            edge(doc_node, sn, "addresses")

    endpoints = [
        "临床症状", "体征", "体重", "摄食量", "摄水量", "血液学", "血生化",
        "尿液分析", "组织病理学", "大体解剖", "器官重量", "心电图",
        "血液生化", "免疫功能", "神经系统", "呼吸系统", "心血管系统",
        "肝肾功能", "血常规", "凝血功能", "骨髓象", "过敏反应",
        "刺激性反应", "溶血反应", "光毒反应", "局部刺激", "肉眼观察",
        "镜下观察", "病理学检查", "血液学检查", "生化指标", "体重变化",
        "心率", "呼吸频率", "血压", "体温",
    ]
    found_ep = set()
    for e in endpoints:
        if e in text and e not in found_ep:
            found_ep.add(e)
            en = node(e, "检测指标")
            edge(doc_node, en, "evaluates")

    concepts = [
        ("GLP","GLP规范"), ("《药物非临床研究质量管理规范》","GLP规范"),
        ("药代动力学","药代动力学"), ("毒代动力学","毒代动力学"),
        ("药效学","药效学"), ("起始剂量","起始剂量"),
        ("安全剂量","安全剂量范围"), ("给药途径","给药途径"),
        ("给药方式","给药方式"), ("剂量设计","剂量设计"),
        ("高剂量","剂量设计"), ("低剂量","剂量设计"), ("中剂量","剂量设计"),
        ("剂量-反应关系","剂量反应关系"), ("时间-反应关系","时间反应关系"),
        ("毒性靶器官","毒性靶器官"), ("靶组织","毒性靶器官"),
        ("NOAEL","NOAEL"), ("NOEL","NOEL"),
        ("安全性评价","安全性评价"), ("致癌试验","致癌性评价"),
        ("致突变试验","致突变性评价"), ("最大耐受剂量","最大耐受剂量"),
        ("临床拟用剂量","临床拟用剂量"), ("安全系数","安全系数"),
        ("恢复期","恢复期观察"), ("解毒","解救措施"),
        ("I期临床试验","I期临床"), ("临床试验","临床试验"),
        ("毒理学研究","毒理学研究"), ("非临床研究","非临床安全性评价"),
        ("药学研究","药学研究"), ("受试物","受试物"), ("样品","受试物"),
        ("辅料","辅料"), ("溶媒","溶媒"), ("局部耐受性","局部耐受性"),
        ("光过敏性","光变态反应"), ("重复给药","重复给药"),
        ("单次给药","单次给药"), ("蓄积性","蓄积性"),
        ("MTD","MTD"), ("委托GLP","GLP规范"), ("符合GLP","GLP规范"),
        ("伦理委员会","伦理审查"), ("动物福利","动物福利"),
        ("3R原则","动物福利3R"), ("替代方法","动物福利"),
        ("供试品","受试物"), ("对照组","对照组"),
        ("阴性对照组","对照组"), ("阳性对照组","对照组"),
        ("溶剂对照组","对照组"), ("空白对照组","对照组"),
    ]
    found_conc = set()
    for key, val in concepts:
        if key in text and key not in found_conc:
            found_conc.add(key)
            cn = node(key, "监管/科学概念", {"concept": val})
            edge(doc_node, cn, "addresses")

    tox_pairs = [
        ("急性毒性","长期毒性"), ("急性毒性","生殖毒性"),
        ("急性毒性","致癌性"), ("长期毒性","致癌性"),
        ("急性毒性","一般药理学"), ("长期毒性","一般药理学"),
        ("急性毒性","药代动力学"), ("长期毒性","药代动力学"),
        ("急性毒性","致突变性"), ("致癌性","致突变性"),
        ("刺激性","溶血性"), ("过敏性","免疫毒性"),
        ("长期毒性","药代动力学"), ("长期毒性","毒代动力学"),
        ("急性毒性","局部刺激性"), ("急性毒性","溶血性"),
        ("一般药理学","安全性药理"), ("药代动力学","毒代动力学"),
        ("生殖毒性","致癌性"), ("生殖毒性","致突变性"),
        ("免疫毒性","过敏性"), ("免疫毒性","光变态反应"),
    ]
    for t1, t2 in tox_pairs:
        if t1 in found_tox and t2 in found_tox:
            s1, s2 = slug(t1), slug(t2)
            edge(s1, s2, "related_to")

    return {"nodes": nodes, "edges": edges}


# Main pipeline
ROOT = Path("/home/wangyc/Documents/工作/法规指导原则/安评")
CONV_DIR = ROOT / "graphify-out" / "converted"
OUT_DIR   = ROOT / "graphify-out"

md_files = sorted(CONV_DIR.glob("*.md"))
print(f"Found {len(md_files)} .md files in converted/")

index_file = ROOT / "📋_非临床安全性评价指导原则完整清单.md"
all_files = list(md_files)
if index_file.exists():
    all_files = list(md_files) + [index_file]
    print(f"Added index file, total {len(all_files)} files")

all_nodes = []
all_edges = []
seen_ids = set()

for fp in all_files:
    fname = fp.name
    text = fp.read_text(encoding="utf-8", errors="ignore")
    ext = extract_entities(text, fname)
    for node in ext.get("nodes", []):
        if node["id"] not in seen_ids:
            seen_ids.add(node["id"])
            all_nodes.append(node)
    all_edges.extend(ext.get("edges", []))
    print(f"  {len(ext['nodes'])} nodes from {fname}")

print(f"\nTotal unique nodes: {len(all_nodes)}, edges: {len(all_edges)}")

import graphify.build as gbuild

nodes_by_id = {n["id"]: n for n in all_nodes}
valid_ids = set(nodes_by_id.keys())

seen_edges = set()
filtered_edges = []
for e in all_edges:
    if e["source"] in valid_ids and e["target"] in valid_ids:
        key = (e["source"], e["target"], e.get("relation",""))
        if key not in seen_edges:
            seen_edges.add(key)
            filtered_edges.append(e)

semantic = {"nodes": all_nodes, "edges": filtered_edges, "hyperedges": [],
            "input_tokens": 0, "output_tokens": 0}

sem_path = Path("/tmp/.graphify_semantic.json")
sem_path.write_text(json.dumps(semantic, ensure_ascii=False, indent=2))
print(f"\nSaved semantic JSON: {sem_path}")

G = gbuild.build_from_json(semantic)
print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

import graphify.cluster as gc
communities = gc.cluster(G)
print(f"Communities: {len(communities)}")

def community_label(cid, nodes):
    best = max(nodes, key=lambda n: G.degree(n) if G else 0)
    return nodes_by_id.get(best, {}).get("label", f"Community-{cid}")

community_labels = {cid: community_label(cid, nodes) for cid, nodes in communities.items()}
top_nodes = sorted(G.nodes(), key=lambda n: G.degree(n), reverse=True)[:30]

cluster_path = OUT_DIR / "clusters.json"
cluster_data = {str(cid): {"label": community_labels[cid], "nodes": nodes}
                for cid, nodes in communities.items()}
cluster_path.write_text(json.dumps(cluster_data, ensure_ascii=False, indent=2))
print(f"Saved clusters.json: {cluster_path}")

graph_json_path = OUT_DIR / "graph.json"
graph_json = {
    "nodes": all_nodes, "edges": filtered_edges,
    "metadata": {"files": len(all_files), "nodes": len(all_nodes),
                  "edges": len(filtered_edges), "communities": len(communities),
                  "generated": "2026-04-18T03:09:00+08:00"}
}
graph_json_path.write_text(json.dumps(graph_json, ensure_ascii=False, indent=2))
print(f"Saved graph.json: {graph_json_path}")

ts = "2026-04-18 03:09 CST"
report_lines = [
    f"# GRAPH_REPORT - 安评 法规指导原则知识图谱\n",
    f"**Pipeline**: graphify semantic cron  \n",
    f"**Time**: {ts}  \n",
    f"**Files**: {len(all_files)} markdown files  \n",
    f"**Graph**: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(communities)} communities\n",
    "## Top God Nodes (highest connectivity)\n",
]
for i, nid in enumerate(top_nodes[:20]):
    node = nodes_by_id.get(nid, {})
    deg = G.degree(nid)
    label = node.get("label", nid)
    cat = node.get("category", "")
    report_lines.append(f"{i+1}. **{label}** ({cat}) - degree {deg}")

report_lines += ["\n## Community Structure\n"]
for cid in sorted(communities.keys(), key=lambda c: -len(communities[c])):
    nodes = communities[cid]
    label = community_labels.get(cid, f"Community-{cid}")
    report_lines.append(f"\n### {label} ({len(nodes)} nodes)\n")
    for n in sorted(nodes)[:15]:
        node = nodes_by_id.get(n, {})
        report_lines.append(f"- {node.get('label', n)} [{node.get('category', '')}]")

report_lines += ["\n## Node Categories Summary\n"]
cat_counts = {}
for n in all_nodes:
    cat = n.get("category", "unknown")
    cat_counts[cat] = cat_counts.get(cat, 0) + 1
for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
    report_lines.append(f"- **{cat}**: {cnt} nodes")

report_path = OUT_DIR / "GRAPH_REPORT_安评_graphify_semantic_cron_latest.md"
report_path.write_text("\n".join(report_lines), encoding="utf-8")
print(f"Saved GRAPH_REPORT: {report_path}")

Path("/tmp/.graphify_done.txt").write_text("DONE")
print("\nDONE marker written")
