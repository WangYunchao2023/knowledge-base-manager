#!/usr/bin/env python3
"""
版本: 2.0.0
功能: 基于文档正文的语义关系图构建器
      高效版：直接遍历 kids 数组提取段落文本，不递归遍历整棵树

原理：两文档如果同时提到同一监管概念（术语/要求/试验类型），
     则认为它们存在语义关联，边权重与共同概念数量正相关。

用法:
  python3 semantic_graph_builder.py --dry-run      # 少量测试
  python3 semantic_graph_builder.py --run          # 全量构建
  python3 semantic_graph_builder.py --status       # 查看进度
"""

import os
import sys
import json
import time
import argparse
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# ============ 配置区 ============
KB_ROOT = "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库"
INDEX_FILE = os.path.join(KB_ROOT, "guidance_index.json")
OUTPUT_FILE = os.path.join(KB_ROOT, "graphify-out", "semantic_edges.json")
PROGRESS_FILE = os.path.join(KB_ROOT, "graphify-out", "semantic_progress.json")
GRAPHIFY_OUT = os.path.join(KB_ROOT, "graphify-out")

# 监管概念词表
REGULATORY_CONCEPTS = {
    "稳定性研究": ["稳定性研究", "稳定性试验", "长期稳定性", "加速稳定性", "影响因素试验", "影响因素", "长期试验", "加速试验", "留样观察"],
    "生物等效性": ["生物等效性", "BE", "生物等效", "等效性研究", "人体生物等效性", "生物利用度", "BA", "AUC0-t", "AUC0-∞", "Cmax"],
    "药代动力学": ["药代动力学", "PK", "药动学", "体内药代", "血药浓度", "药时曲线", "半衰期", "清除率", "分布容积"],
    "临床试验": ["临床试验", "临床研究", "人体研究", "临床评价", "临床安全性", "临床有效性", "GCP", "临床方案", "研究者发起的临床试验"],
    "非临床研究": ["非临床研究", "临床前", "毒理学", "药效学", "药理毒理", "GLP", "安全药理", "生殖毒理", "遗传毒理"],
    "质量研究": ["质量研究", "质量标准", "质量控制", "质量评价", "关键质量属性", "CQA", "质量属性", "质量源于设计", "QbD"],
    "注射剂": ["注射剂", "注射液", "静脉注射", "肌内注射", "输液", "特殊注射剂", "注射用", "输液剂"],
    "固体制剂": ["固体制剂", "片剂", "胶囊", "口服固体制剂", "口服片剂", "胶囊剂", "颗粒剂", "散剂"],
    "原料药": ["原料药", "活性成分", "API", "起始物料", "药用辅料", "辅料"],
    "制剂工艺": ["制剂工艺", "生产工艺", "处方工艺", "无菌工艺", "制粒", "压片", "混合", "灭菌", "冻干", "薄膜包衣"],
    "变更研究": ["变更研究", "工艺变更", "处方变更", "变更申请", "补充申请", "变更分类", "重大变更", "中等变更", "微小变更"],
    "注册申报": ["注册申报", "上市申请", "NDA", "仿制药", "一致性评价", "注册批", "上市许可", "MAH", "药品注册"],
    "仿制药": ["仿制药", "仿制药一致性", "参比制剂", "受试制剂", "Generic", "仿制药研发", "一致性评价"],
    "含量测定": ["含量测定", "含量", "含量均匀度", "溶出度", "崩解时限", "含量均匀性", "最大单杂", "总杂"],
    "杂质研究": ["杂质研究", "有关物质", "杂质谱", "降解杂质", "基因毒性杂质", "潜在杂质", "有机杂质", "无机杂质", "残留溶剂"],
    "分析方法": ["分析方法", "方法学验证", "专属性", "精密度", "准确度", "耐用性", "检测限", "定量限", "线性", "范围"],
    "配伍稳定性": ["配伍稳定性", "配伍", "复配", "联合用药", "配伍禁忌", "配伍变化"],
    "特殊制剂": ["特殊制剂", "脂质体", "微球", "乳剂", "胶束", "特殊注射剂", "纳米粒", "混悬型"],
    "儿童用药": ["儿童用药", "儿科", "小儿", "儿童临床", "儿科临床", "幼龄"],
    "生物制品": ["生物制品", "抗体", "疫苗", "蛋白药物", "重组", "单抗", "多肽", "生物药"],
    "中药": ["中药", "天然药物", "中成药", "中药制剂", "民族药", "中药材", "中药饮片", "植物药"],
    "安全性": ["安全性", "安全评价", "毒性", "不良反应", "风险评估", "安全风险", "警戒"],
    "有效性": ["有效性", "疗效", "有效性评价", "临床疗效", "治疗效果", "有效率"],
    "质量可控": ["质量可控", "质量可控性"],
    "对照品": ["对照品", "参比品", "标准品", "对照药材", "标准物质"],
    "包材相容": ["包材相容", "包装系统", "相容性", "密封性", "包装相容", "容器密封", "泄漏"],
    "给药系统": ["给药系统", "给药装置", "吸入制剂", "透皮制剂", "经皮", "吸入", "喷雾剂"],
    "对照研究": ["对照研究", "对比研究", "参比制剂对比", "受试制剂对比", "比较研究"],
    "生物学": ["生物学", "体外释放", "体内释放", "释放度", "释放试验"],
    "注册生物": ["注册标准", "试行标准", "正式标准", "进口标准", "注册标准编号"],
}

# 预编译
CONCEPT_PATTERNS = {}
for concept, synonyms in REGULATORY_CONCEPTS.items():
    pattern_str = "|".join(re.escape(syn) for syn in synonyms)
    CONCEPT_PATTERNS[concept] = re.compile(pattern_str)

# ==============================

def load_index():
    with open(INDEX_FILE, encoding="utf-8") as f:
        return json.load(f)


def extract_concepts_fast(json_path):
    """
    高效版：只遍历 kids 数组，直接取每条记录的 content 字段。
    不递归，不解析嵌套结构。
    """
    if not os.path.exists(json_path):
        return set()
    
    try:
        with open(json_path, encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    except Exception:
        return set()
    
    found_concepts = set()
    
    for kid in data.get("kids", []):
        # 只处理有 content 的段落/标题
        text = kid.get("content", "")
        if not text or not isinstance(text, str):
            continue
        
        for concept, pattern in CONCEPT_PATTERNS.items():
            if pattern.search(text):
                found_concepts.add(concept)
    
    return found_concepts


def build_semantic_edges(docs):
    """
    阶段1: 提取所有文档的概念集
    阶段2: 倒排索引生成边
    """
    total = len(docs)
    
    # 阶段1: 文档→概念集
    doc_concepts = {}  # doc_id → set of concepts
    concept_docs = defaultdict(set)  # concept → set of doc_ids
    
    print("📖 阶段1: 概念提取...")
    t0 = time.time()
    
    for i, doc in enumerate(docs):
        doc_id = doc["id"]
        json_path = os.path.join(KB_ROOT, doc["paths"].get("json", ""))
        concepts = extract_concepts_fast(json_path)
        
        if concepts:
            doc_concepts[doc_id] = concepts
            for c in concepts:
                concept_docs[c].add(doc_id)
        
        if (i + 1) % 100 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = (total - i - 1) / rate if rate > 0 else 0
            print(f"\r  进度: {i+1}/{total} ({100*(i+1)/total:.1f}%) | {elapsed:.1f}s | 剩余~{remaining:.0f}s", end="", flush=True)
    
    print(f"\r  ✅ 概念提取完成: {len(doc_concepts)} 份有概念, 耗时 {time.time()-t0:.1f}s")
    
    # 阶段2: 倒排索引建边
    print("🔗 阶段2: 生成语义边...")
    t1 = time.time()
    
    edges = []
    edge_map = {}  # (a,b) → edge_obj
    
    for concept, doc_set in concept_docs.items():
        if len(doc_set) < 2:
            continue
        
        doc_list = sorted(doc_set)
        n = len(doc_list)
        
        # 两两组合（从小到大排序避免重复）
        for a_idx in range(n):
            for b_idx in range(a_idx + 1, n):
                a = doc_list[a_idx]
                b = doc_list[b_idx]
                key = (a, b) if a < b else (b, a)
                
                if key in edge_map:
                    # 累加
                    e = edge_map[key]
                    if concept not in e["shared_concepts"]:
                        e["shared_concepts"].append(concept)
                    e["weight"] += 1
                else:
                    e = {
                        "source": key[0],
                        "target": key[1],
                        "weight": 1,
                        "shared_concepts": [concept],
                        "relation_type": "shared_regulatory_concept"
                    }
                    edge_map[key] = e
                    edges.append(e)
    
    print(f"  ✅ 语义边生成完成: {len(edges)} 条, 耗时 {time.time()-t1:.1f}s")
    
    # 按权重降序
    edges.sort(key=lambda x: -x["weight"])
    
    return edges, doc_concepts


def main():
    parser = argparse.ArgumentParser(description="语义关系图构建器 v2.0.0")
    parser.add_argument("--run", action="store_true", help="执行全量构建")
    parser.add_argument("--dry-run", action="store_true", help="少量测试（20份文档）")
    parser.add_argument("--status", action="store_true", help="查看进度")
    args = parser.parse_args()
    
    if args.status:
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE) as f:
                e = json.load(f)
            print(f"✅ 语义边已存在: {len(e.get('edges', []))} 条")
            print(f"   生成时间: {e.get('generated_at', '未知')}")
            print(f"   文档数: {e.get('doc_count', '?')}")
        else:
            print("📭 尚未构建")
        return
    
    if not (args.run or args.dry_run):
        print("用法: --run 全量 | --dry-run 测试 | --status 查看")
        return
    
    print("🚀 语义关系图构建器 v2.0.0")
    print(f"   知识库: {KB_ROOT}")
    print(f"   概念词表: {len(REGULATORY_CONCEPTS)} 个概念")
    
    index_data = load_index()
    docs = index_data["documents"]
    
    if args.dry_run:
        docs = docs[:20]
        print(f"🧪 测试模式: 仅处理 {len(docs)} 份文档")
    else:
        print(f"📚 全量处理: {len(docs)} 份文档")
    
    start = time.time()
    edges, doc_concepts = build_semantic_edges(docs)
    elapsed = time.time() - start
    
    # 保存
    os.makedirs(GRAPHIFY_OUT, exist_ok=True)
    result = {
        "version": "2.0.0",
        "generated_at": datetime.now().isoformat(),
        "doc_count": len(doc_concepts),
        "total_docs": len(docs),
        "edge_count": len(edges),
        "concepts_used": list(REGULATORY_CONCEPTS.keys()),
        "min_weight": 1,
        "max_weight": max(e["weight"] for e in edges) if edges else 0,
        "edges": edges
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 完成!")
    print(f"   含概念文档: {len(doc_concepts)}/{len(docs)}")
    print(f"   语义边: {len(edges)} 条")
    print(f"   总耗时: {elapsed:.1f}秒")
    print(f"   输出: {OUTPUT_FILE}")
    
    # 权重分布
    weight_dist = defaultdict(int)
    for e in edges:
        w = min(e["weight"], 10)
        key = w if w <= 10 else "10+"
        weight_dist[key] += 1
    
    print(f"\n📊 边权重分布（共享概念数）:")
    for w in sorted(weight_dist.keys(), key=lambda x: (isinstance(x, str), x)):
        print(f"   ≥{w} 个概念: {weight_dist[w]} 条边")


if __name__ == "__main__":
    main()