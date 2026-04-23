#!/usr/bin/env python3
"""Extract regulatory entities and relationships from markdown guidance documents."""
import json, re, os
from pathlib import Path
from collections import defaultdict

source_dir = Path("/home/wangyc/Documents/工作/法规指导原则/安评")
converted_dir = source_dir / "graphify-out/converted"
output_dir = source_dir / "graphify-out"

# ─── Entity patterns ─────────────────────────────────────────────────────────

DRUG_CATEGORIES = [
    "化学药物", "中药", "天然药物", "生物制品", "治疗用生物制品", "预防用生物制品",
    "纳米药物", "抗体偶联药物", "脂质体药物", "细胞类药物", "基因治疗药物",
    "疫苗", "血液制品", "重组蛋白质", "单克隆抗体", "抗体药物", "放射性药物",
    "中药注射剂", "中药复方", "化药", "生物技术药物", "小分子药物", "大分子药物",
    "新药用辅料", "辅料", "化药原料药", "化学原料药",
]

TOXICITY_STUDY_TYPES = [
    "急性毒性试验", "急性毒性研究", "单次给药毒性试验", "单次给药毒性研究",
    "长期毒性试验", "长期毒性研究", "重复给药毒性试验", "重复给药毒性研究",
    "生殖毒性试验", "生殖毒性研究", "生育力毒性", "早期胚胎毒性", "胚胎毒性",
    "致畸试验", "发育毒性", "围产期毒性",
    "遗传毒性试验", "遗传毒性研究", "基因毒性研究", "基因毒性试验", "致癌试验", "致癌性试验",
    "安全药理学试验", "安全药理学研究", "一般药理学研究", "药理学研究",
    "毒代动力学研究", "毒代动力学", "药代动力学研究", "药代动力学", "ADME",
    "免疫毒性研究", "免疫毒性试验", "过敏性研究", "光变态反应", "免疫原性",
    "局部毒性试验", "刺激性试验", "过敏性试验", "溶血性试验", "刺激性研究",
    "光安全性评价", "光毒性", "光敏性",
    "中毒量试验", "最大耐受量", "耐受性试验",
    "临床前安全性评价", "非临床安全性评价", "毒理学评价", "安全性评价",
    "毒理试验", "一般毒性试验", "特殊毒性试验",
]

REGULATORY_CONCEPTS = [
    "GLP", "GMP", "GCP", "GAP", "药品注册", "临床试验", "非临床研究",
    "给药方式", "给药途径", "给药剂量", "剂量设计", "剂量选择", "高剂量设计",
    "无观察到不良作用的剂量", "NOAEL", "未见不良反应剂量", "最大耐受剂量", "MTD",
    "安全系数", "起始剂量", "临床剂量",
    "实验动物", "种属选择", "动物种属", "大鼠", "小鼠", "犬", " Beagle犬", "小型猪",
    "豚鼠", "家兔", "猴", "非人灵长类", "转基因动物",
    "一般药理学", "中枢神经系统", "心血管系统", "呼吸系统",
    "QT间期延长", "心室复极化", "hERG通道", "心电图",
    "体外试验", "体内试验", "体外研究", "体内研究",
    " Ames试验", "微核试验", "染色体畸变", "基因突变", "TK基因突变",
    "拍照安全评估", "光安全", "皮肤光毒性",
    "致癌性", "致癌试验", "阳性结果", "阴性结果",
    "申报资料", "CTD格式", "注册申请", "技术审评",
    "IND", "NDA", "BLA", "对照品", "阳性对照", "阴性对照",
    "受试物", "供试品", "样品", "制剂", "赋形剂",
    "恢复期", "停药期", "恢复期观察", "对照设计",
    "组织病理学", "病理检查", "大体解剖", "镜检",
    "血液学", "血液生化", "尿液分析", "免疫学指标",
    "统计分析", "统计学方法", "显著性检验",
    "S9", "S7A", "S7B", "S8", "S9", "S10", "S1A", "S1B", "S1C", "S2", "S5", "S6",
    "ICH指导原则", "ICH E9", "ICH S5(R3)", "ICH S11",
    "生物技术药物", "细胞因子", "抗体", "ADC", "抗体偶联药物",
    "亲和力", "效价", "生物活性", "免疫反应", "抗药抗体", "ADA",
    "纳米粒径", "纳米载体", "纳米特性", "巨噬细胞", "生物分布",
    "脂质体", "脂质体药物", "PEG化", "长循环",
    "药物警戒", "安全性信号", "风险控制", "SUSAR",
    "儿童用药", "儿科", "老年人", "特殊人群",
    "ICH E9(R1)", "S5(R3)", "S11", "S1B", "S1C(R2)",
    "Q&A", "问答", "指导原则实施", "转化实施",
    "WHO", "FDA", "EMA", "PMDA", "国家药品监督管理局", "NMPA",
    "指导原则", "技术指导原则", "研究技术指导原则", "一般原则",
    "毒性表现", "不良反应", "毒效应", "靶器官", "毒性靶点",
    "蓄积毒性", "依赖性", "成瘾性", "耐受性",
    "受试品检测", "含量测定", "纯度分析", "稳定性",
    "配制记录", "给药体积", "浓度", "溶剂", "助溶剂",
    "文献资料", "参考文献", "公开文献", "已有数据",
]

STUDY_DESIGNS = [
    "单次给药", "重复给药", "每日一次", "每日多次", "连续给药",
    "灌胃", "腹腔注射", "静脉注射", "静脉滴注", "肌内注射", "皮下注射", "皮内注射",
    "经皮给药", "吸入给药", "雾化给药", "眼用给药", "鼻腔给药", "舌下给药",
    "平行设计", "交叉设计", "自身对照", "历史对照",
    "急性毒性分级", "LD50", "最大耐受量法", "最大给药量", "近似致死量",
    "28天毒性试验", "90天毒性试验", "6个月毒性试验", "12个月毒性试验", "长期毒性试验",
    "亚慢性毒性", "慢性毒性", "致癌试验周期",
    "剂量组设计", "三个剂量组", "高剂量组", "中剂量组", "低剂量组",
    "恢复期组", "卫星组", "毒代动力学组",
    "安乐死", "人道处死", "濒死动物", "濒死状态",
    "尸检", "解剖", "脏器系数", "器官重量",
    "组织学", "病理学", "HE染色", "免疫组化",
]

ANIMAL_SPECIES = [
    "大鼠", "Wistar大鼠", "SD大鼠", "Sprague-Dawley大鼠",
    "小鼠", "C57BL/6小鼠", "BALB/c小鼠", "KM小鼠", "ICR小鼠",
    "Beagle犬", "比格犬", "犬", "小型猪", "Gottingen小型猪",
    "食蟹猴", "恒河猴", "非人灵长类", "猴",
    "豚鼠", "新西兰兔", "家兔", "兔子",
    "仓鼠", "沙鼠",
]

ENDPOINTS = [
    "死亡率", "临床观察", "体重", "摄食量", "摄水量",
    "血液学检查", "凝血功能", "血常规", "血红蛋白", "血小板", "白细胞",
    "血液生化", "肝功能", "肾功能", "血糖", "血脂", "电解质",
    "尿液分析", "尿常规", "蛋白尿", "镜检",
    "心电图", "ECG", "QT间期", "PR间期", "QRS波群",
    "眼科学检查", "眼科检查", "听力检查",
    "大体解剖", "病理检查", "组织病理学", "组织学",
    "脏器重量", "器官重量", "脏器系数", "器官系数",
    "免疫学检测", "抗体检测", "细胞因子", "流式细胞术",
    "毒代动力学参数", "AUC", "Cmax", "Tmax", "CL", "Vdss", "t1/2",
    "中毒病理", "靶器官毒性", "特异性毒性",
]


def make_id(entity_type: str, name: str) -> str:
    """Generate a stable ID for an entity."""
    clean = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]+', '_', name)
    clean = clean.strip('_').lower()[:60]
    h = hex(hash(name) & 0xFFFFFFFF)[:8]
    prefix_map = {
        'drug_category': 'drug',
        'toxicity_study': 'tox',
        'regulatory_concept': 'reg',
        'study_design': 'design',
        'animal_species': 'animal',
        'endpoint': 'endpoint',
        'guideline': 'guide',
        'file': 'file',
    }
    prefix = prefix_map.get(entity_type, 'ent')
    return f"{prefix}_{clean}_{h}"


def normalize(text: str) -> str:
    """Normalize whitespace in text."""
    return re.sub(r'\s+', ' ', text).strip()


def extract_file_name(content: str) -> str:
    """Extract a document identifier from content."""
    title_match = re.search(r'^#+\s*(.+)', content, re.MULTILINE)
    if title_match:
        return normalize(title_match.group(1))
    # Try first non-empty line
    for line in content.split('\n')[:20]:
        line = line.strip()
        if line and not line.startswith('!') and len(line) > 5:
            return normalize(line)[:80]
    return ""


def extract_all_entities(content: str, file_path: str, file_name_raw: str) -> tuple[list, list]:
    """Extract entities and relationships from document content."""
    nodes = []
    edges = []
    seen_ids = {}
    file_id = make_id('file', file_name_raw or file_path)
    file_node_id = file_id

    # File node
    nodes.append({
        "id": file_node_id,
        "label": file_name_raw or file_path.split('/')[-1],
        "type": "guideline_document",
        "entity_type": "guideline_document",
        "source_file": file_path,
    })
    seen_ids[file_node_id] = True

    # ── Drug categories ───────────────────────────────────────────────────────
    for drug in DRUG_CATEGORIES:
        if drug in content:
            nid = make_id('drug_category', drug)
            if nid not in seen_ids:
                nodes.append({
                    "id": nid,
                    "label": drug,
                    "type": "drug_category",
                    "entity_type": "drug_category",
                    "source_file": file_path,
                })
                seen_ids[nid] = True
            edges.append({
                "source": file_node_id,
                "target": nid,
                "type": "addresses",
                "weight": 1,
                "source_file": file_path,
            })

    # ── Toxicity study types ─────────────────────────────────────────────────
    for study in TOXICITY_STUDY_TYPES:
        if study in content:
            nid = make_id('toxicity_study', study)
            if nid not in seen_ids:
                nodes.append({
                    "id": nid,
                    "label": study,
                    "type": "toxicity_study",
                    "entity_type": "toxicity_study",
                    "source_file": file_path,
                })
                seen_ids[nid] = True
            edges.append({
                "source": file_node_id,
                "target": nid,
                "type": "addresses",
                "weight": 2,
                "source_file": file_path,
            })

    # ── Regulatory concepts ─────────────────────────────────────────────────
    for concept in REGULATORY_CONCEPTS:
        if concept in content:
            nid = make_id('regulatory_concept', concept)
            if nid not in seen_ids:
                nodes.append({
                    "id": nid,
                    "label": concept,
                    "type": "regulatory_concept",
                    "entity_type": "regulatory_concept",
                    "source_file": file_path,
                })
                seen_ids[nid] = True
            edges.append({
                "source": file_node_id,
                "target": nid,
                "type": "addresses",
                "weight": 1,
                "source_file": file_path,
            })

    # ── Animal species ──────────────────────────────────────────────────────
    for species in ANIMAL_SPECIES:
        if species in content:
            nid = make_id('animal_species', species)
            if nid not in seen_ids:
                nodes.append({
                    "id": nid,
                    "label": species,
                    "type": "animal_species",
                    "entity_type": "animal_species",
                    "source_file": file_path,
                })
                seen_ids[nid] = True
            edges.append({
                "source": file_node_id,
                "target": nid,
                "type": "addresses",
                "weight": 1,
                "source_file": file_path,
            })

    # ── Endpoints ────────────────────────────────────────────────────────────
    for endpoint in ENDPOINTS:
        if endpoint in content:
            nid = make_id('endpoint', endpoint)
            if nid not in seen_ids:
                nodes.append({
                    "id": nid,
                    "label": endpoint,
                    "type": "endpoint",
                    "entity_type": "endpoint",
                    "source_file": file_path,
                })
                seen_ids[nid] = True
            edges.append({
                "source": file_node_id,
                "target": nid,
                "type": "evaluates",
                "weight": 1,
                "source_file": file_path,
            })

    # ── Study design elements ────────────────────────────────────────────────
    for design in STUDY_DESIGNS:
        if design in content:
            nid = make_id('study_design', design)
            if nid not in seen_ids:
                nodes.append({
                    "id": nid,
                    "label": design,
                    "type": "study_design",
                    "entity_type": "study_design",
                    "source_file": file_path,
                })
                seen_ids[nid] = True
            edges.append({
                "source": file_node_id,
                "target": nid,
                "type": "addresses",
                "weight": 1,
                "source_file": file_path,
            })

    # ── Cross-entity relationships ────────────────────────────────────────────
    # Toxicity study → Animal species (uses)
    for study in TOXICITY_STUDY_TYPES:
        if study not in content:
            continue
        study_id = make_id('toxicity_study', study)
        if study_id not in seen_ids:
            continue
        for species in ANIMAL_SPECIES:
            if species in content:
                species_id = make_id('animal_species', species)
                edges.append({
                    "source": study_id,
                    "target": species_id,
                    "type": "uses",
                    "weight": 1,
                    "source_file": file_path,
                })

    # Toxicity study → endpoint (evaluates)
    for study in TOXICITY_STUDY_TYPES:
        if study not in content:
            continue
        study_id = make_id('toxicity_study', study)
        if study_id not in seen_ids:
            continue
        for endpoint in ENDPOINTS:
            if endpoint in content:
                ep_id = make_id('endpoint', endpoint)
                edges.append({
                    "source": study_id,
                    "target": ep_id,
                    "type": "evaluates",
                    "weight": 1,
                    "source_file": file_path,
                })

    # Regulatory concept → study type (regulates)
    reg_study_map = {
        "GLP": ["长期毒性试验", "急性毒性试验", "生殖毒性试验", "遗传毒性试验"],
        "NOAEL": ["长期毒性试验", "重复给药毒性研究"],
        "给药方式": ["长期毒性试验", "重复给药毒性研究"],
        "剂量设计": ["致癌试验", "长期毒性试验"],
        "QT间期延长": ["安全药理学试验"],
        "hERG通道": ["安全药理学试验"],
        "光安全性评价": ["光安全性评价"],
        "免疫毒性": ["免疫毒性研究", "免疫毒性试验"],
    }
    for concept in REGULATORY_CONCEPTS:
        if concept not in content:
            continue
        concept_id = make_id('regulatory_concept', concept)
        if concept_id not in seen_ids:
            continue
        related = reg_study_map.get(concept, [])
        for rel_study in related:
            if rel_study in content:
                rel_id = make_id('toxicity_study', rel_study)
                edges.append({
                    "source": concept_id,
                    "target": rel_id,
                    "type": "regulates",
                    "weight": 1,
                    "source_file": file_path,
                })

    # Study design → species
    for design in STUDY_DESIGNS:
        if design not in content:
            continue
        design_id = make_id('study_design', design)
        if design_id not in seen_ids:
            continue
        for species in ANIMAL_SPECIES:
            if species in content:
                species_id = make_id('animal_species', species)
                edges.append({
                    "source": design_id,
                    "target": species_id,
                    "type": "performed_on",
                    "weight": 1,
                    "source_file": file_path,
                })

    return nodes, edges


def main():
    print("=== Entity Extraction for 安评 ===")

    # Get all .md files (excluding checklist for now)
    md_files = sorted(converted_dir.glob("*.md"))
    checklist_file = source_dir / "📋_非临床安全性评价指导原则完整清单.md"

    print(f"Found {len(md_files)} .md files in converted/")

    # Filter out the checklist - process it last
    non_checklist = [f for f in md_files if "非临床安全性评价指导原则完整清单" not in str(f)]

    all_nodes = []
    all_edges = []
    all_nodes_seen = {}
    all_edges_seen = {}

    # Process non-checklist files
    for i, fpath in enumerate(non_checklist):
        fname = fpath.name.replace('_' + fpath.stem.split('_')[-1] if '_' in fpath.stem else '', '')
        # Get clean name from filename
        clean_name = fpath.stem.split('_', 1)[-1] if '_' in fpath.stem else fpath.stem
        # Actually just use the part before the hash
        parts = fpath.stem.rsplit('_', 1)
        if len(parts) == 2 and len(parts[1]) < 15:
            clean_name = parts[0]
        else:
            clean_name = fpath.stem

        content = fpath.read_text(encoding='utf-8', errors='replace')
        doc_name = extract_file_name(content)
        if not doc_name:
            doc_name = clean_name[:80]

        nodes, edges = extract_all_entities(content, str(fpath), doc_name)

        for n in nodes:
            nid = n['id']
            if nid not in all_nodes_seen:
                all_nodes.append(n)
                all_nodes_seen[nid] = True

        for e in edges:
            # Create unique edge key
            e_key = (e['source'], e['target'], e.get('type', ''))
            if e_key not in all_edges_seen:
                all_edges.append(e)
                all_edges_seen[e_key] = True

        if (i + 1) % 10 == 0:
            print(f"  Processed {i+1}/{len(non_checklist)} files... (nodes: {len(all_nodes)}, edges: {len(all_edges)})")

    print(f"  Processed {len(non_checklist)} non-checklist files")
    print(f"  Total nodes: {len(all_nodes)}, edges: {len(all_edges)}")

    # Process checklist file
    if checklist_file.exists():
        print(f"\nProcessing checklist: {checklist_file.name}")
        content = checklist_file.read_text(encoding='utf-8', errors='replace')
        doc_name = extract_file_name(content) or "非临床安全性评价指导原则完整清单"
        nodes, edges = extract_all_entities(content, str(checklist_file), doc_name)
        for n in nodes:
            nid = n['id']
            if nid not in all_nodes_seen:
                all_nodes.append(n)
                all_nodes_seen[nid] = True
        for e in edges:
            e_key = (e['source'], e['target'], e.get('type', ''))
            if e_key not in all_edges_seen:
                all_edges.append(e)
                all_edges_seen[e_key] = True
        print(f"  Checklist: +{len(nodes)} nodes, +{len(edges)} edges")

    # Also deduplicate edges by source-target pair
    edge_pairs_seen = {}
    dedup_edges = []
    for e in all_edges:
        key = (e['source'], e['target'])
        if key not in edge_pairs_seen:
            dedup_edges.append(e)
            edge_pairs_seen[key] = True
        else:
            # Merge edge types
            existing = next(x for x in dedup_edges if (x['source'], x['target']) == key)
            existing['weight'] = max(existing.get('weight', 1), e.get('weight', 1))
            t1 = existing.get('type', '')
            t2 = e.get('type', '')
            if t1 != t2:
                existing['type'] = f"{t1}|{t2}"

    print(f"\nFinal: {len(all_nodes)} nodes, {len(dedup_edges)} edges")

    result = {
        "nodes": all_nodes,
        "edges": dedup_edges,
        "metadata": {
            "total_files": len(non_checklist) + (1 if checklist_file.exists() else 0),
            "total_nodes": len(all_nodes),
            "total_edges": len(dedup_edges),
        }
    }

    # Save to /tmp/.graphify_semantic.json
    out_path = Path("/tmp/.graphify_semantic.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {out_path}")
    print("Done!")

if __name__ == "__main__":
    main()
