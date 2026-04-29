"""
Extract entities and relationships from all converted markdown files
for the 安评 directory.
"""
import os, json, re
from pathlib import Path
from collections import defaultdict

source_dir = Path("/home/wangyc/Documents/工作/法规指导原则/安评")
converted_dir = source_dir / "graphify-out/converted"

# Get all converted .md files
md_files = sorted(converted_dir.glob("*.md"))
qinbing_file = source_dir / "📋_非临床安全性评价指导原则完整清单.md"
all_files = md_files + ([qinbing_file] if qinbing_file.exists() else [])

print(f"Total files to process: {len(all_files)}")

# ── Entity patterns ──────────────────────────────────────────────────────────

# Drug categories
DRUG_CATEGORIES = [
    "化学药物", "中药", "天然药物", "生物制品", "预防用生物制品", "治疗用生物制品",
    "纳米药物", "抗体偶联药物", "ADC", "脂质体药物", "小分子药物", "大分子药物",
    "创新药", "新药", "细胞治疗", "基因治疗", "血液制品", "抗体药物",
    "单克隆抗体", "抗体片段", "新药用辅料", "医疗器械",
]

# Toxicity / study types
STUDY_TYPES = [
    "急性毒性", "长期毒性", "重复给药毒性", "单次给药毒性",
    "生殖毒性", "生育力", "发育毒性", "致畸性",
    "遗传毒性", "基因毒性", "致癌性", "致癌试验",
    "刺激性", "过敏性", "溶血性", "免疫毒性", "光毒性", "光变态反应",
    "安全药理学", "一般药理学",
    "药代动力学", "毒代动力学", "药效学", "毒理学试验",
    "临床前安全性评价", "非临床安全性评价", "非临床药代动力学",
    "非临床安全性", "临床安全性", "安全性评价",
    "吸收", "分布", "代谢", "排泄", "ADME",
    "体外药代动力学", "体内药代动力学",
    "局部刺激性", "局部毒性", "全身毒性",
]

# Regulatory concepts
REGULATORY_CONCEPTS = [
    "给药途径", "给药方式", "给药周期", "给药剂量", "剂量设计", "剂量组",
    "剂量设计", "剂量范围", "起始剂量", "最高剂量", "最大耐受剂量", "NOAEL",
    "剂量递增", "阴性对照", "阳性对照", "对照组", "溶媒对照",
    " GLP", "药物非临床研究质量管理规范",
    "试验样品", "供试品", "受试物",
    "ICH", "ICH S1", "ICH S2", "ICH S3", "ICH S4", "ICH S5", "ICH S6",
    "ICH S7A", "ICH S7B", "ICH S8", "ICH S9", "ICH S10", "ICH S11",
    "ICH E9", "ICH M3", "ICH Q1B",
    "IND", "NDA", "注册申请", "临床试验", "临床研究",
    "指导原则", "技术指导原则", "审评", "审批",
    "风险评估", "结果评价", "数据分析", "统计分析",
    "标准操作规程", "生物标志物",
    "QT间期延长",
]

# Animal species
SPECIES = [
    "大鼠", "小鼠", "犬", "猴", "家兔", "豚鼠", "小型猪",
    "雪貂", "仓鼠", "非人灵长类", "食蟹猴", "裸鼠",
]

# Relationship patterns
REL_PATTERNS = [
    (r'([^\s,，、]+)适用于([^\s,，、]+)', 'applies_to'),
    (r'([^\s,，、]+)要求([^\s,，、]+)', 'requires'),
    (r'([^\s,，、]+)评价([^\s,，、]+)', 'evaluates'),
    (r'([^\s,，、]+)支持([^\s,，、]+)', 'supports'),
    (r'([^\s,，、]+)参考([^\s,，、]+)', 'references'),
    (r'([^\s,，、]+)包括([^\s,，、]+)', 'includes'),
    (r'([^\s,，、]+)属于([^\s,，、]+)', 'belongs_to'),
    (r'([^\s,，、]+)用于([^\s,，、]+)', 'used_for'),
    (r'([^\s,，、]+)通过([^\s,，、]+)', 'via'),
    (r'([^\s,，、]+)进行([^\s,，、]+)', 'conducts'),
    (r'([^\s,，、]+)采用([^\s,，、]+)', 'adopts'),
    (r'([^\s,，、]+)依据([^\s,，、]+)', 'based_on'),
    (r'([^\s,，、]+)结合([^\s,，、]+)', 'combines_with'),
    (r'([^\s,，、]+)涉及([^\s,，、]+)', 'involves'),
]

def clean_entity(s):
    s = s.strip().replace('\n', '').replace('*', '').replace('#', '')
    s = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', s)
    s = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9（）\(\)《》·]', '', s)
    s = s.strip('（），、。；：""''').strip()
    return s

def extract_entities(text, source_file):
    """Extract all entities from text using pattern matching."""
    entities_found = set()
    
    # Collect all patterns
    all_patterns = DRUG_CATEGORIES + STUDY_TYPES + REGULATORY_CONCEPTS + SPECIES
    
    for pattern in all_patterns:
        if pattern in text and len(pattern) >= 2:
            entities_found.add(pattern)
    
    # Extract numbers + units (doses)
    dose_patterns = re.findall(r'(\d+(?:\.\d+)?)\s*(?:mg/kg|g/kg|μg/kg|ml/kg|L/kg|mg/m²|mL/kg)', text)
    for d in dose_patterns:
        entities_found.add(f"{d}mgkg_dose")
    
    # Extract time durations
    time_patterns = re.findall(r'(\d+)\s*(?:天|周|月|小时|分钟|秒|小时|日)', text)
    for t in time_patterns:
        entities_found.add(f"{t}天_duration" if '天' in text[text.find(t)+len(t):text.find(t)+len(t)+2] else f"{t}小时_duration")
    
    # Extract guideline references (e.g., S1, S2, S5(R3))
    ich_refs = re.findall(r'ICH\s*[SMEQ]\d+(?:\([R\w]\))?', text)
    entities_found.update(ich_refs)
    
    # Extract year references
    years = re.findall(r'(19\d{2}|20\d{2})\s*年', text)
    for y in years:
        entities_found.add(f"{y}年")
    
    return entities_found

def extract_relationships(text, entities, source_file):
    """Extract relationships between entities from text."""
    rels = []
    text_lower = text  # keep original for CJK matching
    
    for pattern_str, rel_type in REL_PATTERNS:
        try:
            matches = re.findall(pattern_str, text)
            for m in matches:
                if len(m) == 2:
                    src = clean_entity(m[0])
                    tgt = clean_entity(m[1])
                    if src and tgt and src != tgt and len(src) >= 2 and len(tgt) >= 2:
                        rels.append((src, tgt, rel_type))
        except Exception:
            pass
    
    return rels

# ── Process all files ────────────────────────────────────────────────────────
all_nodes = []
all_edges = []
node_ids = set()

def add_node(label, node_type, source_file):
    """Add a node if not exists, return its id."""
    nid = label
    if nid in node_ids:
        return nid
    node_ids.add(nid)
    all_nodes.append({
        'id': nid,
        'label': label,
        'type': node_type,
        'source_file': source_file,
    })
    return nid

def add_edge(src, tgt, rel_type, source_file):
    """Add an edge (deduplicated by set)."""
    edge_key = (src, tgt, rel_type)
    all_edges.append({
        'source': src,
        'target': tgt,
        'type': rel_type,
        'source_file': source_file,
        'weight': 1,
    })

entity_type_map = {}
for p in DRUG_CATEGORIES:
    entity_type_map[p] = 'drug_category'
for p in STUDY_TYPES:
    entity_type_map[p] = 'study_type'
for p in REGULATORY_CONCEPTS:
    entity_type_map[p] = 'regulatory_concept'
for p in SPECIES:
    entity_type_map[p] = 'species'

file_count = 0
for fpath in all_files:
    file_count += 1
    fname = fpath.name
    try:
        text = fpath.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        print(f"  [WARN] Cannot read {fname}: {e}")
        continue
    
    # Extract entities
    entities = extract_entities(text, fname)
    
    for ent in entities:
        ntype = entity_type_map.get(ent, 'concept')
        add_node(ent, ntype, fname)
    
    # Extract relationships
    rels = extract_relationships(text, entities, fname)
    for src, tgt, rtype in rels:
        if src in node_ids and tgt in node_ids:
            add_edge(src, tgt, rtype, fname)
    
    # Also add co-occurrence edges for entities in same paragraph
    para_limit = 500
    paras = text.split('\n')
    for para in paras:
        if len(para) < 10:
            continue
        para_entities = extract_entities(para, fname)
        para_entities = [e for e in para_entities if e in node_ids]
        # Add co-occurrence relationships (within same paragraph)
        for i, e1 in enumerate(para_entities):
            for e2 in para_entities[i+1:]:
                if e1 != e2:
                    add_edge(e1, e2, 'co_occurs_in', fname)
    
    print(f"  [{file_count}/{len(all_files)}] {fname}: {len(entities)} entities")

# Deduplicate edges by source+target+type
seen_edges = set()
deduped_edges = []
for e in all_edges:
    key = (e['source'], e['target'], e['type'])
    if key not in seen_edges:
        seen_edges.add(key)
        deduped_edges.append(e)

# Output
out = {'nodes': all_nodes, 'edges': deduped_edges}
out_path = Path('/tmp/.graphify_semantic.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(f"\nExtraction complete:")
print(f"  Nodes: {len(all_nodes)}")
print(f"  Edges (deduped): {len(deduped_edges)}")
print(f"  Saved to: {out_path}")
