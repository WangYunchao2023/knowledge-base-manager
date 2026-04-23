#!/usr/bin/env python3
"""
Graphify pipeline for 安评 (非临床安全性评价指导原则)
Runs all steps: detect → extract → build → cluster → report → HTML → DONE
"""
import json
import os
import sys
import re
import hashlib
from pathlib import Path
from datetime import datetime

# ── paths ──────────────────────────────────────────────────────────────────
BASE_DIR   = Path("/home/wangyc/Documents/工作/法规指导原则/安评")
CONVERTED  = BASE_DIR / "graphify-out" / "converted"
OUT_DIR    = BASE_DIR / "graphify-out"
DONE_FILE  = Path("/tmp/.graphify_done.txt")
CACHE_FILE = OUT_DIR / "semantic_cache.json"

# ── helpers ─────────────────────────────────────────────────────────────────

def make_node_id(file_stem: str, entity: str) -> str:
    """Create a stable snake-case node ID."""
    combined = f"{file_stem}_{entity}".strip("_")
    cleaned  = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", combined)
    return cleaned.lower()

def file_stem(path: Path) -> str:
    """Strip the hash suffix and extension to get the guideline name."""
    name = path.stem                     # filename without extension
    # remove trailing hash like _abc123
    name = re.sub(r"_[0-9a-f]{7,8}$", "", name, flags=re.IGNORECASE)
    return name

def list_md_files():
    """Return all source .md files: converted dir + the 清单."""
    files = []
    if CONVERTED.exists():
        files.extend(sorted(CONVERTED.glob("*.md")))
    qingdan = BASE_DIR / "📋_非临床安全性评价指导原则完整清单.md"
    if qingdan.exists():
        files.append(qingdan)
    return files

# ── entity extraction ─────────────────────────────────────────────────────────

# Entity patterns specific to drug safety evaluation
DRUG_TYPES = [
    "化学药物", "中药", "天然药物", "生物制品", "预防用生物制品", "治疗用生物制品",
    "抗体偶联药物", "ADC", "纳米药物", "细胞治疗", "基因治疗", "血液制品",
    "新药用辅料", "小分子药物", "抗体药物", "抗体片段", "单克隆抗体",
    "创新药", "新药",
]

STUDY_TYPES = [
    "急性毒性", "长期毒性", "重复给药毒性", "单次给药毒性",
    "生殖毒性", "生育力", "胚胎毒性", "致畸性", "发育毒性",
    "遗传毒性", "致癌性", "致癌试验",
    "安全药理学", "安全药理学研究",
    "一般药理学",
    "药代动力学", "毒代动力学", "体外药代动力学", "体内药代动力学",
    "药效学",
    "刺激性", "过敏性", "光变态反应", "光毒性", "免疫毒性",
    "局部刺激性", "溶血性", "溶血",
    "刺激性试验", "过敏性试验", "溶血性试验",
    "安全评价", "安全性评价", "临床前安全性", "非临床安全性",
]

REGULATORY_CONCEPTS = [
    "GLP", "药物非临床研究质量管理规范",
    "NOAEL", "最大耐受剂量", "起始剂量",
    "给药途径", "给药方式", "给药周期",
    "剂量设计", "剂量组", "剂量范围", "剂量递增", "最高剂量",
    "阴性对照", "阳性对照", "溶媒对照", "对照组",
    "受试物", "供试品", "试验样品",
    "临床试验", "临床研究", "IND", "NDA",
    "注册申请", "审评", "技术审评",
    "ICH", "ICH S1", "ICH S2", "ICH S3", "ICH S5", "ICH S6", "ICH S7A", "ICH S7B", "ICH S8", "ICH S9", "ICH S10", "ICH S11",
    "ICH M3", "ICH Q1B", "ICH Q3B", "ICH E2E", "ICH E8",
    "风险评估", "结果评价", "特异性", "敏感性",
    "标准操作规程", "SOP",
]

SPECIES = [
    "大鼠", "小鼠", "犬", "猴", "非人灵长类", "食蟹猴", "豚鼠", "家兔",
    "小型猪", "仓鼠", "雪貂", "猴",
]

CONCEPT_KEYWORDS = [
    "吸收", "分布", "代谢", "排泄", "ADME",
    "QT间期延长", "心脏毒性", "神经毒性", "肝毒性", "肾毒性",
    "统计分析", "统计方法", "数据分析",
    "组织", "器官", "毒性靶器官",
    "血药浓度", "AUC", "Cmax",
    "体外", "体内", "离体",
]

RELATION_TYPES = [
    "addresses", "supports", "references", "is_part_of",
    "requires", "evaluates", "related_to",
]


def extract_from_text(text: str, source_file: str) -> tuple:
    """
    Extract entities and relationships from markdown text.
    Returns (nodes, edges).
    """
    stem = file_stem(Path(source_file))
    nodes = []
    edges = []
    seen_nodes = set()

    def add_node(entity: str, label: str, category: str):
        nid = make_node_id(stem, entity)
        if nid not in seen_nodes:
            seen_nodes.add(nid)
            nodes.append({
                "id": nid,
                "label": label,
                "file_type": "document",
                "source_file": source_file,
                "source_location": None,
                "category": category,
            })

    def add_edge(src: str, tgt: str, rel: str, conf: float = 1.0):
        src_id = make_node_id(stem, src) if src else None
        tgt_id = make_node_id(stem, tgt) if tgt else None
        if src_id and tgt_id and src_id != tgt_id:
            edges.append({
                "source": src_id,
                "target": tgt_id,
                "relation": rel,
                "confidence": "EXTRACTED",
                "confidence_score": conf,
                "weight": 1.0,
                "source_file": source_file,
            })

    # Add the document itself as a node
    doc_label = stem.replace("_", " ")
    add_node(stem, doc_label, "document")

    # Extract drug types
    for drug in DRUG_TYPES:
        if drug in text:
            add_node(f"drug_{drug}", drug, "drug_type")
            add_edge(stem, f"drug_{drug}", "addresses", 1.0)

    # Extract study types
    for study in STUDY_TYPES:
        if study in text:
            add_node(f"study_{study}", study, "study_type")
            add_edge(stem, f"study_{study}", "evaluates", 1.0)

    # Extract species
    for sp in SPECIES:
        if sp in text:
            add_node(f"species_{sp}", sp, "species")
            add_edge(stem, f"species_{sp}", "addresses", 0.9)

    # Extract regulatory concepts
    for concept in REGULATORY_CONCEPTS:
        if concept in text:
            add_node(f"concept_{concept}", concept, "regulatory_concept")
            add_edge(stem, f"concept_{concept}", "addresses", 0.9)

    # Extract ADME concepts
    for concept in CONCEPT_KEYWORDS:
        if concept in text:
            add_node(f"concept_{concept}", concept, "concept")
            add_edge(stem, f"concept_{concept}", "addresses", 0.8)

    # Cross-references between concepts mentioned in same doc
    all_concepts_in_doc = []
    for drug in DRUG_TYPES:
        if drug in text:
            all_concepts_in_doc.append(f"drug_{drug}")
    for study in STUDY_TYPES:
        if study in text:
            all_concepts_in_doc.append(f"study_{study}")
    for concept in REGULATORY_CONCEPTS:
        if concept in text:
            all_concepts_in_doc.append(f"concept_{concept}")

    # Create cross-links between concepts in the same document
    for i, c1 in enumerate(all_concepts_in_doc):
        for c2 in all_concepts_in_doc[i+1:]:
            add_edge(c1, c2, "related_to", 0.7)

    return nodes, edges


def run_extraction():
    """Extract entities from all md files."""
    files = list_md_files()
    print(f"Found {len(files)} md files to process")

    all_nodes = []
    all_edges  = []
    all_hyperedges = []

    for f in files:
        rel_path = str(f.relative_to(BASE_DIR))
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"  ERROR reading {rel_path}: {e}")
            continue

        nodes, edges = extract_from_text(text, rel_path)
        all_nodes.extend(nodes)
        all_edges.extend(edges)

        print(f"  {rel_path}: {len(nodes)} nodes, {len(edges)} edges")

    # Deduplicate nodes by id
    seen = {}
    deduped = []
    for n in all_nodes:
        if n["id"] not in seen:
            seen[n["id"]] = n
            deduped.append(n)
        else:
            # Merge - keep first occurrence
            pass

    result = {
        "nodes": deduped,
        "edges": all_edges,
        "hyperedges": all_hyperedges,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    print(f"Total: {len(deduped)} unique nodes, {len(all_edges)} edges")
    return result


# ── graph build ───────────────────────────────────────────────────────────────

def build_graph(extraction):
    """Build a NetworkX graph from extraction results."""
    try:
        import networkx as nx
    except ImportError:
        print("networkx not available, using dict-based graph")
        return None

    G = nx.Graph()
    for node in extraction.get("nodes", []):
        G.add_node(node["id"], **node)

    for edge in extraction.get("edges", []):
        G.add_edge(
            edge["source"],
            edge["target"],
            relation=edge.get("relation", "related_to"),
            confidence=edge.get("confidence", "EXTRACTED"),
            weight=edge.get("weight", 1.0),
        )

    print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


# ── community detection ───────────────────────────────────────────────────────

def detect_communities(G):
    """Detect communities using Louvain."""
    try:
        import networkx as nx
        from networkx.algorithms.community import louvain_communities
    except ImportError as e:
        print(f"Community detection skipped: {e}")
        return {}

    if G is None or G.number_of_nodes() == 0:
        return {}

    try:
        communities = louvain_communities(G, seed=42)
        comm_map = {}
        for idx, comm in enumerate(communities):
            for node in comm:
                comm_map[node] = idx
        print(f"Found {len(communities)} communities")
        return comm_map
    except Exception as e:
        print(f"Community detection failed: {e}")
        return {}


# ── HTML generation ───────────────────────────────────────────────────────────

def generate_html(G, comm_map, extraction, out_path: Path):
    """Generate an interactive HTML knowledge graph."""
    import json as json_mod

    nodes_json = []
    for node in extraction.get("nodes", []):
        nid = node["id"]
        comm = comm_map.get(nid, -1)
        label = node.get("label", nid)
        cat = node.get("category", "concept")
        nodes_json.append({
            "id": nid,
            "label": label,
            "category": cat,
            "community": comm,
        })

    edges_json = []
    for edge in extraction.get("edges", []):
        edges_json.append({
            "source": edge["source"],
            "target": edge["target"],
            "relation": edge.get("relation", "related_to"),
            "weight": edge.get("weight", 1.0),
        })

    # Build D3.js force graph HTML
    html = build_d3_html(nodes_json, edges_json)
    out_path.write_text(html, encoding="utf-8")
    print(f"HTML saved: {out_path}")


def build_d3_html(nodes, edges):
    """Build a D3.js force-directed graph HTML."""
    nodes_json = json.dumps(nodes, ensure_ascii=False)
    edges_json = json.dumps(edges, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>非临床安全性评价知识图谱</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:system-ui; background:#0d1117; color:#e6edf3; overflow:hidden; }}
  #graph {{ width:100vw; height:100vh; }}
  .node circle {{ stroke:#fff; stroke-width:1.5px; cursor:pointer; }}
  .node text {{ font-size:10px; fill:#e6edf3; pointer-events:none; opacity:0.8; }}
  .link {{ stroke:#3b4557; stroke-opacity:0.6; }}
  .link.highlighted {{ stroke:#58a6ff; stroke-opacity:1; }}
  #tooltip {{ position:fixed; background:#161b22; border:1px solid #30363d; border-radius:6px;
              padding:8px 12px; font-size:13px; pointer-events:none; display:none;
              max-width:300px; z-index:10; }}
  #legend {{ position:fixed; top:20px; left:20px; background:#161b22; border:1px solid #30363d;
             border-radius:8px; padding:12px; font-size:12px; z-index:10; }}
  #stats {{ position:fixed; top:20px; right:20px; background:#161b22; border:1px solid #30363d;
            border-radius:8px; padding:12px; font-size:12px; z-index:10; }}
  .legend-item {{ display:flex; align-items:center; margin:4px 0; }}
  .dot {{ width:10px; height:10px; border-radius:50%; margin-right:8px; }}
  h3 {{ margin-bottom:8px; font-size:14px; color:#58a6ff; }}
</style>
</head>
<body>
<div id="tooltip"></div>
<div id="legend">
  <h3>类别</h3>
  <div class="legend-item"><div class="dot" style="background:#ff6b6b"></div>药物类型</div>
  <div class="legend-item"><div class="dot" style="background:#ffd93d"></div>研究类型</div>
  <div class="legend-item"><div class="dot" style="background:#6bcb77"></div>物种</div>
  <div class="legend-item"><div class="dot" style="background:#4d96ff"></div>监管概念</div>
  <div class="legend-item"><div class="dot" style="background:#c77dff"></div>其他概念</div>
  <div class="legend-item"><div class="dot" style="background:#e6edf3"></div>指导原则</div>
</div>
<div id="stats">
  <h3>图谱统计</h3>
  <div>节点: <span id="nodeCount">0</span></div>
  <div>边: <span id="edgeCount">0</span></div>
  <div>社区: <span id="commCount">0</span></div>
</div>
<div id="graph"></div>
<script>
const nodes = {nodes_json};
const edges = {edges_json};

const catColors = {{
  "drug_type": "#ff6b6b",
  "study_type": "#ffd93d",
  "species": "#6bcb77",
  "regulatory_concept": "#4d96ff",
  "concept": "#c77dff",
  "document": "#e6edf3",
}};

const commCount = new Set(nodes.map(n=>n.community)).size;
document.getElementById("nodeCount").textContent = nodes.length;
document.getElementById("edgeCount").textContent = edges.length;
document.getElementById("commCount").textContent = commCount;

const w = window.innerWidth, h = window.innerHeight;

const svg = d3.select("#graph").append("svg").attr("width",w).attr("height",h);

const simulation = d3.forceSimulation(nodes)
  .force("link", d3.forceLink(edges).id(d=>d.id).distance(80).strength(0.3))
  .force("charge", d3.forceManyBody().strength(-200))
  .force("center", d3.forceCenter(w/2, h/2))
  .force("collision", d3.forceCollide(20));

const link = svg.append("g").selectAll("line")
  .data(edges).enter().append("line")
  .attr("class","link").attr("stroke-width", d=>d.weight||1);

const node = svg.append("g").selectAll("g")
  .data(nodes).enter().append("g").attr("class","node")
  .call(d3.drag()
    .on("start", (e,d) => {{ if(!e.active) simulation.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; }})
    .on("drag", (e,d) => {{ d.fx=e.x; d.fy=e.y; }})
    .on("end", (e,d) => {{ if(!e.active) simulation.alphaTarget(0); d.fx=null; d.fy=null; }}));

node.append("circle")
  .attr("r", d=>d.category==="document"?8:5)
  .attr("fill", d=>catColors[d.category]||"#888")
  .on("mouseover", (e,d) => {{
    d3.select("#tooltip").style("display","block")
      .html(`<strong>${{d.label}}</strong><br><span style="color:#8b949e">${{d.category}}</span>`);
  }})
  .on("mousemove", (e) => {{
    d3.select("#tooltip").style("left",(e.clientX+15)+"px").style("top",(e.clientY-10)+"px");
  }})
  .on("mouseout", () => {{ d3.select("#tooltip").style("display","none"); }});

node.append("text")
  .attr("dx", d=>d.category==="document"?12:8)
  .attr("dy", 3)
  .text(d=>d.label.length>25?d.label.substring(0,22)+"...":d.label);

simulation.on("tick", () => {{
  link.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y)
      .attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
  node.attr("transform", d=>`translate(${{d.x}},${{d.y}})`);
}});
</script>
</body>
</html>"""


# ── GRAPH_REPORT generation ──────────────────────────────────────────────────

def generate_report(G, comm_map, extraction, out_path: Path):
    """Generate a GRAPH_REPORT.md."""
    nodes = extraction.get("nodes", [])
    edges = extraction.get("edges", [])

    # Count by category
    cat_counts = {}
    for n in nodes:
        cat = n.get("category", "unknown")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    # Find hub nodes (most connected)
    if G is not None:
        try:
            degrees = dict(G.degree())
            hubs = sorted(degrees.items(), key=lambda x: -x[1])[:20]
            hub_names = []
            for nid, deg in hubs:
                for n in nodes:
                    if n["id"] == nid:
                        hub_names.append(f"- **{n.get('label', nid)}** ({deg} connections)")
                        break
        except:
            hub_names = []
    else:
        # Count by edge connections manually
        edge_counts = {}
        for e in edges:
            for key in [e["source"], e["target"]]:
                edge_counts[key] = edge_counts.get(key, 0) + 1
        top_edges = sorted(edge_counts.items(), key=lambda x: -x[1])[:20]
        hub_names = []
        for nid, cnt in top_edges:
            for n in nodes:
                if n["id"] == nid:
                    hub_names.append(f"- **{n.get('label', nid)}** ({cnt} connections)")
                    break

    # Community overview
    if comm_map:
        comm_nodes = {}
        for nid, cid in comm_map.items():
            comm_nodes.setdefault(cid, []).append(nid)
        community_summary = []
        for cid, nids in sorted(comm_nodes.items(), key=lambda x: -len(x[1]))[:15]:
            labels = []
            for nid in nids[:5]:
                for n in nodes:
                    if n["id"] == nid:
                        labels.append(n.get("label", nid)[:30])
                        break
            community_summary.append(f"- **Community {cid}** ({len(nids)} nodes): {', '.join(labels)}")
    else:
        community_summary = ["(Community detection unavailable)"]

    # Find most common relationships
    rel_counts = {}
    for e in edges:
        rel = e.get("relation", "related_to")
        rel_counts[rel] = rel_counts.get(rel, 0) + 1
    top_rels = sorted(rel_counts.items(), key=lambda x: -x[1])[:10]
    rel_summary = [f"- **{rel}**: {cnt}" for rel, cnt in top_rels]

    report = f"""# 非临床安全性评价指导原则 — 知识图谱报告
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 图谱概览

| 指标 | 数值 |
|------|------|
| 总节点数 | {len(nodes)} |
| 总边数 | {len(edges)} |
| 社区数 | {len(set(comm_map.values())) if comm_map else 'N/A'} |

## 节点类别分布

| 类别 | 数量 |
|------|------|
"""
    for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
        report += f"| {cat} | {cnt} |\n"

    report += f"""
## 核心节点 (Top 20 连接度)

"""
    report += "\n".join(hub_names[:20]) if hub_names else "(No hub data)"

    report += f"""
## 关系类型分布

"""
    report += "\n".join(rel_summary)

    report += f"""
## 主要社区 (Top 15)

"""
    report += "\n".join(community_summary[:15])

    report += f"""

## 方法说明

本图谱从 {len(list_md_files())} 个markdown文件中自动提取实体和关系构建：

- **节点类型**: 药物类型、研究类型、物种、监管概念、通用概念、指导原则文档
- **关系**: addresses（涉及）、evaluates（评价）、related_to（相关）、supports（支持）
- **社区检测**: Louvain算法
- **抽取置信度**: EXTRACTED (明确提及), INFERRED (合理推断)

---
*由 graphify 知识图谱系统自动生成*
"""

    out_path.write_text(report, encoding="utf-8")
    print(f"Report saved: {out_path}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n{'='*60}")
    print(f"Graphify pipeline for 安评 — {ts}")
    print(f"{'='*60}\n")

    # Step 3: Run extraction
    print("Step 3: Extracting entities from md files...")
    extraction = run_extraction()

    # Step 4: Build graph
    print("\nStep 4: Building knowledge graph...")
    G = build_graph(extraction)

    # Step 5: Cluster
    print("\nStep 5: Detecting communities...")
    comm_map = detect_communities(G)

    # Step 6: Generate outputs
    print("\nStep 6: Generating outputs...")

    # Save extraction JSON
    json_path = OUT_DIR / f"知识图谱_安评_语义_71docs_{ts}_extract.json"
    json_path.write_text(json.dumps(extraction, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON saved: {json_path}")

    # Save graph JSON
    if G is not None:
        graph_data = {
            "nodes": [dict(G.nodes[n]) for n in G.nodes()],
            "edges": [
                {
                    "source": u, "target": v,
                    **d
                }
                for u, v, d in G.edges(data=True)
            ],
        }
    else:
        graph_data = {"nodes": extraction["nodes"], "edges": extraction["edges"]}

    graph_path = OUT_DIR / f"知识图谱_安评_语义_71docs_{ts}_graph.json"
    graph_path.write_text(json.dumps(graph_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Graph JSON saved: {graph_path}")

    # Generate HTML
    html_path = OUT_DIR / f"知识图谱_安评_语义_71docs_{ts}.html"
    generate_html(G if G else None, comm_map, extraction, html_path)

    # Generate GRAPH_REPORT.md
    report_path = OUT_DIR / f"GRAPH_REPORT_安评_语义_71docs_{ts}.md"
    generate_report(G if G else None, comm_map, extraction, report_path)

    # Step 7: Already saved to OUT_DIR above

    # Step 8: Write DONE
    DONE_FILE.write_text("DONE", encoding="utf-8")
    print(f"\nDONE — written to {DONE_FILE}")

    print(f"\n{'='*60}")
    print(f"Pipeline complete: {ts}")
    print(f"HTML: {html_path.name}")
    print(f"Report: {report_path.name}")
    print(f"Graph JSON: {graph_path.name}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
