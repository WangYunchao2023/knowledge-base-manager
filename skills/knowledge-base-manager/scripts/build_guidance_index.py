#!/usr/bin/env python3
"""
版本: 1.0.0
功能: 自动扫描"供AI用信息"目录，生成 guidance_index.json 索引文件
用法: python build_guidance_index.py
"""

import json
import os
import re
from datetime import datetime

# ============ 配置区 ============
# 知识库根目录（索引和脚本都放在这里）
KB_ROOT = "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库"
# 需要扫描的子目录（相对于 KB_ROOT）
SCAN_SUBDIRS = [
    "稳定性/供AI用信息",
    # 未来可扩展：
    # "参考模板",
    # "内部文件",
]
OUTPUT_FILE = os.path.join(KB_ROOT, "guidance_index.json")
# ==============================

def parse_filename(filename):
    """
    从文件名中提取元数据。
    文件名格式示例:
    - 20050318 - 化学药物稳定性研究技术指导原则.md
    - 20150205 - 化学药物（原料药和制剂）稳定性研究技术指导原则.md
    - 20231007 - 《化学药品注射剂配伍稳定性药学研究技术指导原则（征求意见稿）》.md
    - 20231007 - 《化学药品注射剂配伍稳定性药学研究技术指导原则（征求意见稿）》反馈意见表.md
    """
    name = filename.replace(".md", "")
    
    # 1. 提取日期 (8位数字)
    date_match = re.match(r"^(\d{8})", name)
    issue_date = date_match.group(1) if date_match else ""
    
    # 去掉日期得到主体标题
    title_part = re.sub(r"^\d{8}\s*[-—]\s*", "", name)
    
    # 2. 判断文档类型
    doc_type = "main"  # 默认正式指导原则
    status = "active"
    category = "通用"  # 默认
    
    if "征求意见稿" in title_part:
        doc_type = "draft"
        status = "draft"
    if "反馈意见表" in title_part or "征求意见反馈表" in title_part:
        doc_type = "feedback"
        status = "reference"
    if "起草说明" in title_part:
        doc_type = "explanation"
        status = "reference"
    if "试行" in title_part:
        status = "active"  # 试行版也是active
    
    # 3. 判断药品种类
    if "化学药品" in title_part or "化学药物" in title_part:
        category = "化学药"
    elif "中药" in title_part or "天然药物" in title_part:
        category = "中药"
    elif "生物制品" in title_part:
        category = "生物制品"
    elif "疫苗" in title_part:
        category = "疫苗"
    
    # 4. 判断制剂类型（亚分类）
    drug_types = []
    if "注射剂" in title_part:
        drug_types.append("注射剂")
    if "原料药" in title_part:
        drug_types.append("原料药")
    if "口服" in title_part:
        drug_types.append("口服")
    if "制剂" in title_part:
        drug_types.append("制剂")
    
    # 5. 生成唯一ID（包含doc_type以区分同日期的不同文档）
    doc_id = f"guidance_{category}_{issue_date}_{doc_type}" if issue_date else f"guidance_{safe_title}_{doc_type}"
    
    return {
        "id": doc_id,
        "title": title_part,
        "issue_date": issue_date,
        "status": status,
        "doc_type": doc_type,
        "scope": {
            "category": category,
            "type": drug_types if drug_types else ["通用"]
        },
        "tags": extract_tags(title_part),
        "paths": {
            "markdown": f"./{filename}",
            "json": f"./{filename.replace('.md', '.json')}",
            "feishu_wiki_url": ""  # 待后续同步飞书后填充
        }
    }

def extract_tags(title):
    """从标题中提取关键词标签"""
    tags = []
    keyword_map = {
        "稳定性": "稳定性",
        "配伍": "配伍",
        "注射剂": "注射剂",
        "原料药": "原料药",
        "制剂": "制剂",
        "化学药": "化学药",
        "中药": "中药",
        "生物制品": "生物制品",
        "研究技术": "研究技术",
        "指导原则": "指导原则",
    }
    for kw, tag in keyword_map.items():
        if kw in title:
            tags.append(tag)
    return list(set(tags))

def scan_and_build_index():
    """递归扫描所有配置的子目录，构建统一索引"""
    documents = []
    
    for subdir in SCAN_SUBDIRS:
        full_subdir = os.path.join(KB_ROOT, subdir)
        if not os.path.isdir(full_subdir):
            print(f"⚠️ 目录不存在，跳过: {full_subdir}")
            continue
        
        print(f"\n📂 扫描目录: {subdir}")
        print("-" * 40)
        
        for fname in sorted(os.listdir(full_subdir)):
            if not fname.endswith(".md"):
                continue
            
            full_path = os.path.join(full_subdir, fname)
            if os.path.isdir(full_path):
                continue
            
            print(f"  处理: {fname}")
            doc_info = parse_filename(fname)
            # 记录来源子目录（方便溯源）
            doc_info["source_subdir"] = subdir
            documents.append(doc_info)
            print(f"    → ID: {doc_info['id']}, 类型: {doc_info['doc_type']}, 分类: {doc_info['scope']['category']}")
    
    return {
        "version": "1.0",
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "kb_root": KB_ROOT,
        "scanned_dirs": SCAN_SUBDIRS,
        "total_docs": len(documents),
        "documents": documents
    }

def main():
    print("=" * 50)
    print("法规指导原则知识库索引构建工具")
    print("=" * 50)
    print()
    
    index_data = scan_and_build_index()
    
    # 写入JSON文件
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    
    print()
    print("=" * 50)
    print(f"✅ 索引构建完成！共处理 {index_data['total_docs']} 个文档")
    print(f"📄 输出文件: {OUTPUT_FILE}")
    print("=" * 50)
    
    # 打印摘要
    print("\n【索引摘要】")
    active_docs = [d for d in index_data['documents'] if d['status'] == 'active']
    draft_docs = [d for d in index_data['documents'] if d['status'] == 'draft']
    print(f"  正式版(Active): {len(active_docs)} 个")
    print(f"  征求意见稿(Draft): {len(draft_docs)} 个")
    print(f"  其他参考文档: {index_data['total_docs'] - len(active_docs) - len(draft_docs)} 个")

if __name__ == "__main__":
    main()
