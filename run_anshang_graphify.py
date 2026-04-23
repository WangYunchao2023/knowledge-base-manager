#!/usr/bin/env python3
"""Graphify cron pipeline for 安评."""
import json, sys, os
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path('/home/wangyc/Documents/工作/法规指导原则/安评')
OUT_DIR = WORKSPACE / 'graphify-out'
PYTHON = sys.executable
TS = datetime.now().strftime('%Y%m%d_%H%M%S')

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def load_json(p):
    return json.loads(Path(p).read_text()) if Path(p).exists() else None

def save_json(data, path):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))

log('=== Graphify Cron Pipeline for 安评 ===')

# Load cached semantic
SEMANTIC_LATEST = OUT_DIR / 'anshang_graphify_semantic_cron_latest_semantic.json'
SEMANTIC_OUT = OUT_DIR / f'anshang_graphify_semantic_cron_{TS}_semantic.json'

if SEMANTIC_LATEST.exists():
    log(f'Loading cached semantic from {SEMANTIC_LATEST.name}')
    semantic = load_json(SEMANTIC_LATEST)
    log(f'  {len(semantic["nodes"])} nodes, {len(semantic["edges"])} edges')
else:
    log('ERROR: No semantic cache found!')
    sys.exit(1)

save_json(semantic, SEMANTIC_OUT)

# Build graph
log('Building graph...')
sys.path.insert(0, str(Path(__file__).parent))
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.analyze import god_nodes, surprising_connections, suggest_questions
from graphify.export import to_json, to_html
from graphify.report import generate

G = build_from_json(semantic)
log(f'  {G.number_of_nodes()} nodes, {G.number_of_edges()} edges')

# Cluster & analyze
log('Clustering...')
communities = cluster(G)
cohesion = score_all(G, communities)
log(f'  {len(communities)} communities')

log('Analyzing...')
gods = god_nodes(G)
surprises = surprising_connections(G, communities)
labels = {cid: f'Community {cid}' for cid in communities}
questions = suggest_questions(G, communities, labels)

analysis = {
    'communities': {str(k): list(v) for k, v in communities.items()},
    'cohesion': {str(k): v for k, v in cohesion.items()},
    'gods': gods,
    'surprises': surprises,
    'questions': questions
}

# Auto-label communities
def auto_label(cid, members, G):
    type_count = {}
    for nid in members:
        ntype = G.nodes[nid].get('type', 'unknown')
        type_count[ntype] = type_count.get(ntype, 0) + 1
    if not type_count:
        return f'Community {cid}'
    top = max(type_count, key=type_count.get)
    return f'{top[:25]}'

community_labels = {cid: auto_label(cid, members, G) for cid, members in communities.items()}
log(f'  Labels: {list(community_labels.values())[:5]}')

# Generate report
detection_info = {'total_files': len(semantic.get('nodes', [])), 'total_words': 0,
                  'needs_graph': True, 'warning': None,
                  'files': {'document': [], 'code': [], 'paper': [], 'image': []}}
tokens = {'input': semantic.get('input_tokens', 0), 'output': semantic.get('output_tokens', 0)}

report = generate(G, communities, cohesion, community_labels, gods, surprises,
                  detection_info, tokens, str(WORKSPACE), suggested_questions=questions)

# Save outputs
report_file = OUT_DIR / f'GRAPH_REPORT_anshang_graphify_semantic_cron_{TS}.md'
report_latest = OUT_DIR / 'GRAPH_REPORT.md'
report_file.write_text(report, encoding='utf-8')
report_latest.write_text(report, encoding='utf-8')
log(f'Report: {report_file.name}')

graph_file = OUT_DIR / f'知识图谱_anshang_graphify_semantic_cron_{TS}_graph.json'
graph_latest = OUT_DIR / '知识图谱_anshang_graphify_semantic_cron_latest_graph.json'
to_json(G, communities, str(graph_file))
to_json(G, communities, str(graph_latest))
log(f'Graph JSON: {graph_file.name}')

analysis_file = OUT_DIR / f'知识图谱_anshang_graphify_semantic_cron_{TS}_analysis.json'
analysis_latest = OUT_DIR / '知识图谱_anshang_graphify_semantic_cron_latest_analysis.json'
save_json(analysis, analysis_file)
save_json(analysis, analysis_latest)
log(f'Analysis: {analysis_file.name}')

# HTML
if G.number_of_nodes() <= 5000:
    html_file = OUT_DIR / f'知识图谱_anshang_graphify_semantic_cron_{TS}.html'
    html_latest = OUT_DIR / '知识图谱_anshang_graphify_semantic_cron_latest.html'
    to_html(G, communities, str(html_file), community_labels=community_labels)
    to_html(G, communities, str(html_latest), community_labels=community_labels)
    log(f'HTML: {html_file.name}')
else:
    log(f'Graph too large ({G.number_of_nodes()} nodes) - skipped HTML')

# DONE
Path('/tmp/.graphify_done.txt').write_text('DONE')
log(f'DONE -> /tmp/.graphify_done.txt')
log(f'Nodes={G.number_of_nodes()}, Edges={G.number_of_edges()}, Communities={len(communities)}')
