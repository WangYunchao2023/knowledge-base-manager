#!/usr/bin/env python3
"""
版本: 2.8.0
功能: 为 guidance_index.json 的每个文档添加章节索引（section_index）
       让 Cortana 回答时能给出"文件 > 章节 > 具体位置"

用法:
  python3 add_section_index.py              # 为所有文档添加章节索引
  python3 add_section_index.py --rebuild     # 强制重建（清空现有章节后重新提取）
"""

import json
import re
import os
import sys
from pathlib import Path

KB_ROOT = "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库"
INDEX_FILE = os.path.join(KB_ROOT, "guidance_index.json")
MD_DIR = os.path.join(KB_ROOT, "稳定性", "供AI用信息")


def extract_sections(md_path):
    """提取 markdown 文件的章节结构"""
    if not os.path.exists(md_path):
        return []
    
    sections = []
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    prev_level = 0
    level = 0
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # 匹配标题行
        m = re.match(r'^(#{1,4})\s+(.+)$', stripped)
        if m and len(stripped) < 120:
            level = len(m.group(1))
            title = m.group(2).strip()
            # 跳过目录项（点线连接的行）
            if re.search(r'[·…\uff0e]{3,}$', title) or re.search(r'[·…\uff0e]{3,}$', stripped):
                continue
            # 跳过过短的标题
            if len(title) < 2:
                continue
            sections.append({
                "level": level,
                "title": title,
                "line": i,
                "ref": f"# L{i}"
            })
            prev_level = level
        elif stripped and level > 0:
            # 非标题行，检查是否是编号段落（1.1 小节）
            m2 = re.match(r'^(\d+\.\d+)\s+(.{2,40})$', stripped)
            if m2:
                sections.append({
                    "level": 4,
                    "title": m2.group(1) + " " + m2.group(2),
                    "line": i,
                    "ref": f"# L{i}"
                })
    
    return sections


def load_index():
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_index(data):
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_section_index(index_data, force=False):
    """为每个文档添加/更新章节索引"""
    updated = 0
    for doc in index_data.get("documents", []):
        md_rel = doc.get("paths", {}).get("markdown", "")
        md_path = os.path.join(KB_ROOT, md_rel)  # 相对路径拼接 KB_ROOT
        
        if not md_rel or not os.path.exists(md_path):
            continue
        
        # 检查是否已有章节索引
        has_sections = "sections" in doc and doc["sections"]
        
        if has_sections and not force:
            continue
        
        sections = extract_sections(md_path)
        doc["sections"] = sections
        
        # 保留前20个主要章节（避免索引过大）
        main_sections = [s for s in sections if s["level"] <= 3]
        doc["section_count"] = len(main_sections)
        doc["section_index"] = main_sections[:20]
        
        updated += 1
        sections_preview = " | ".join([s["title"][:20] for s in main_sections[:5]])
        print(f"  ✅ [{doc['id']}] {len(sections)} 节 | {sections_preview[:60]}")
    
    return updated


def main():
    print("=" * 60)
    print("📑 章节索引构建工具 v1.0.0")
    print("=" * 60)
    
    force = "--rebuild" in sys.argv
    
    index_data = load_index()
    total_docs = len(index_data.get("documents", []))
    print(f"\n索引文件: {INDEX_FILE}")
    print(f"文档总数: {total_docs}")
    print(f"模式: {'强制重建' if force else '增量（跳过已有章节的文档）'}")
    print()
    
    updated = build_section_index(index_data, force=force)
    
    save_index(index_data)
    
    print()
    print(f"完成: 更新了 {updated}/{total_docs} 个文档的章节索引")
    
    # 验证
    docs_with_sections = sum(1 for d in index_data.get("documents", []) if d.get("sections"))
    print(f"有章节索引的文档: {docs_with_sections}/{total_docs}")


if __name__ == "__main__":
    main()
