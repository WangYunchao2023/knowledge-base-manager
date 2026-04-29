#!/usr/bin/env python3
"""
Graphify pipeline for: /home/wangyc/Documents/工作/法规指导原则/安评
Run at: 2026-04-20 04:50 CST
"""
import json, time, sys, os
from pathlib import Path

ROOT = Path("/home/wangyc/Documents/工作/法规指导原则/安评")
OUT  = ROOT / "graphify-out"
CONV = OUT / "converted"
OUT.mkdir(exist_ok=True)

TS = time.strftime("%Y%m%d_%H%M%S")
PREFIX = f"anshang_graphify_semantic_cron_{TS}"

print(f"[{TS}] Starting graphify pipeline")
print(f"  PREFIX: {PREFIX}")

# ── Step 1: Collect all .md files ──────────────────────────────────────────
md_files = sorted(CONV.glob("*.md"))
清单_file = ROOT / "📋_非临床安全性评价指导原则完整清单.md"

all_md_paths = md_files
if 清单_file.exists():
    all_md_paths = list(md_files) + [清单_file]

print(f"  .md files in converted/: {len(md_files)}")
print(f"  total md files to process: {len(all_md_paths)}")

# ── Step 2: Semantic extraction ─────────────────────────────────────────────
from graphify.extract import extract_entities_and_relations

results = []
for i, fpath in enumerate(all_md_paths):
    label = fpath.name
    try:
        text = fpath.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  [!] read error {label}: {e}")
        continue

    try:
        result = extract_entities_and_relations(text, label=label)
        results.append(result)
        if (i+1) % 10 == 0:
            print(f"  processed {i+1}/{len(all_md_paths)}")
    except Exception as e:
        print(f"  [!] extract error {label}: {e}")

print(f"  extraction done: {len(results)} files processed")

# ── Step 3: Merge into single semantic JSON ─────────────────────────────────
merged = {"nodes": [], "edges": [], "metadata": {"files": [], "timestamp": TS}}
for r in results:
    if not r:
        continue
    if isinstance(r, dict):
        merged["nodes"].extend(r.get("nodes", []))
        merged["edges"].extend(r.get("edges", []))
        merged["metadata"]["files"].append(r.get("label", "unknown"))

# Deduplicate nodes by id
seen_nodes = {}
for n in merged["nodes"]:
    seen_nodes[n["id"]] = n
merged["nodes"] = list(seen_nodes.values())

# Deduplicate edges
seen_edges = set()
deduped_edges = []
for e in merged["edges"]:
    key = (e.get("source"), e.get("target"), e.get("type"))
    if key not in seen_edges:
        seen_edges.add(key)
        deduped_edges.append(e)
merged["edges"] = deduped_edges

merged["metadata"]["total_files"] = len(all_md_paths)
merged["metadata"]["total_nodes"] = len(merged["nodes"])
merged["metadata"]["total_edges"] = len(merged["edges"])

SEM_PATH = OUT / f"{PREFIX}_semantic.json"
with open(SEM_PATH, "w", encoding="utf-8") as f:
    json.dump(merged, f, ensure_ascii=False, indent=2)
print(f"  semantic saved: {SEM_PATH} ({len(merged['nodes'])} nodes, {len(merged['edges'])} edges)")

# Also save latest
import shutil
latest_sem = OUT / "anshang_graphify_semantic_cron_latest_semantic.json"
shutil.copy(SEM_PATH, latest_sem)

# ── Step 4: Build graph ──────────────────────────────────────────────────────
from graphify.build import build_from_json

G = build_from_json(SEM_PATH)
print(f"  graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# ── Step 5: Cluster ──────────────────────────────────────────────────────────
from graphify.cluster import cluster

clusters = cluster(G)
print(f"  clusters: {len(clusters)}")

# ── Step 6: Analyze ──────────────────────────────────────────────────────────
from graphify.analyze import god_nodes, score_all

god = god_nodes(G, top=20)
scores = score_all(G)

# ── Step 7: Export ─────────────────────────────────────────────────────────
from graphify.export import to_json, to_html

# JSON graph
graph_json = to_json(G)
GRAPH_JSON_PATH = OUT / f"{PREFIX}_graph.json"
with open(GRAPH_JSON_PATH, "w", encoding="utf-8") as f:
    json.dump(graph_json, f, ensure_ascii=False, indent=2)

# HTML
HTML_PATH = OUT / f"{PREFIX}.html"
try:
    html = to_html(G, title=f"知识图谱_安评_{PREFIX}")
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)
except Exception as e:
    print(f"  [!] HTML export error: {e}")
    HTML_PATH = None

# Latest copies
import shutil
latest_graph_json = OUT / "anshang_graphify_semantic_cron_latest_graph.json"
shutil.copy(GRAPH_JSON_PATH, latest_graph_json)
if HTML_PATH:
    latest_html = OUT / "anshang_graphify_semantic_cron_latest.html"
    shutil.copy(HTML_PATH, latest_html)

# ── Step 8: Report ─────────────────────────────────────────────────────────
from graphify.report import generate

try:
    report_md = generate(G, clusters=clusters, god=god, scores=scores,
                        title=f"GRAPH_REPORT_安评_{PREFIX}")
    REPORT_PATH = OUT / f"GRAPH_REPORT_安评_{PREFIX}.md"
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_md)
    latest_report = OUT / "GRAPH_REPORT_安评_graphify_semantic_cron_latest.md"
    shutil.copy(REPORT_PATH, latest_report)
    print(f"  report saved: {REPORT_PATH}")
except Exception as e:
    print(f"  [!] report error: {e}")

# ── Step 9: Write DONE ──────────────────────────────────────────────────────
DONE_PATH = Path("/tmp/.graphify_done.txt")
DONE_PATH.write_text("DONE", encoding="utf-8")
print(f"  DONE written to {DONE_PATH}")

print(f"\n[OK] Pipeline complete!")
print(f"  Semantic : {SEM_PATH}")
print(f"  Graph JSON: {GRAPH_JSON_PATH}")
if HTML_PATH:
    print(f"  HTML      : {HTML_PATH}")
print(f"  Report    : {REPORT_PATH}")
