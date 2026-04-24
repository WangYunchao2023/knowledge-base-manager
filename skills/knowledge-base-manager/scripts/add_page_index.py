#!/usr/bin/env python3
"""
版本: 3.0.0
功能: 从 opendataloader 输出的 JSON（保留PDF段落+页码）提取页码索引，
      存入 guidance_index.json 的每个文档条目中。
      让 Cortana 回答时能给出「PDF第X页 → markdown第Y行」的精确定位。

用法:
  python3 add_page_index.py              # 增量构建
  python3 add_page_index.py --rebuild    # 强制重建
  python3 add_page_index.py --doc DOCID # 仅构建指定文档
"""

import json
import os
import re
import sys
from pathlib import Path

# ============ 配置区 ============
KB_ROOT = "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库"
INDEX_FILE = os.path.join(KB_ROOT, "guidance_index.json")
MD_DIR = os.path.join(KB_ROOT, "稳定性", "供AI用信息")
# ==============================

def load_index():
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_index(data):
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def normalize_text(text):
    """文本归一化：去空格标点，用于匹配"""
    if not text:
        return ""
    return re.sub(r'[\s\n\r\t·…\uff0e,，.]', '', text)

def get_md_line_for_text(md_path, text, max_lines=200):
    """在 markdown 中找到与给定文本最接近的行号"""
    if not os.path.exists(md_path):
        return None
    
    norm_target = normalize_text(text)
    if len(norm_target) < 10:
        return None
    
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    best_match = None
    best_ratio = 0
    
    for i, line in enumerate(lines, 1):
        norm_line = normalize_text(line)
        # 简单包含匹配
        if norm_target in norm_line or norm_line in norm_target:
            if len(norm_line) > best_ratio:
                best_match = i
                best_ratio = len(norm_line)
        if i > max_lines:
            break
    
    return best_match

def build_page_index(doc, force=False):
    """为一个文档构建页码索引"""
    doc_id = doc['id']
    json_path = doc.get('paths', {}).get('json', '')
    md_path = os.path.join(KB_ROOT, doc.get('paths', {}).get('markdown', ''))
    
    if not json_path:
        return None
    
    json_abs = os.path.join(KB_ROOT, json_path) if not os.path.isabs(json_path) else json_path
    
    if not os.path.exists(json_abs):
        return None
    
    # 检查是否已有页码索引
    if 'page_index' in doc and doc['page_index'] and not force:
        return None
    
    try:
        with open(json_abs, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return None
    
    kids = data.get('kids', [])
    paragraphs = [k for k in kids if k.get('type') == 'paragraph']
    
    if not paragraphs:
        return None
    
    page_index = []
    for para in paragraphs:
        text = para.get('content', '').strip()
        page = para.get('page number', 0)
        
        if not text or len(text) < 15:
            continue
        
        # 跳过标题性质的短文本
        if len(text) < 20:
            continue
        
        # 在 markdown 中找对应行
        md_line = get_md_line_for_text(md_path, text)
        
        page_index.append({
            'text': text[:80],          # 前80字符（用于匹配）
            'page': page,                # PDF 页码
            'md_line': md_line,          # markdown 行号
            'full_text_len': len(text)   # 全文长度
        })
    
    return page_index

def build_all_page_indexes(index_data, force=False, doc_filter=None):
    """为所有文档构建页码索引"""
    updated = 0
    
    for doc in index_data.get('documents', []):
        if doc_filter and doc['id'] != doc_filter:
            continue
        
        page_index = build_page_index(doc, force=force)
        if page_index is not None:
            doc['page_index'] = page_index
            doc['page_count'] = max((p['page'] for p in page_index), default=0)
            updated += 1
            print(f"  ✅ [{doc['id']}] {len(page_index)} 条索引 | 覆盖 {doc.get('page_count', 0)} 页")
        else:
            doc['page_index'] = []
            doc['page_count'] = 0
            print(f"  ⏭  [{doc['id']}] 无 JSON 或无需更新")
    
    return updated

def main():
    print("=" * 60)
    print("📖 页码索引构建工具 v1.0.0")
    print("=" * 60)
    
    force = "--rebuild" in sys.argv
    
    # 指定单个文档
    doc_filter = None
    if "--doc" in sys.argv:
        idx = sys.argv.index("--doc")
        doc_filter = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
    
    index_data = load_index()
    total_docs = len(index_data.get('documents', []))
    
    print(f"\n索引文件: {INDEX_FILE}")
    print(f"文档总数: {total_docs}")
    print(f"模式: {'强制重建' if force else '增量'}" + (f" | 仅文档: {doc_filter}" if doc_filter else ""))
    print()
    
    updated = build_all_page_indexes(index_data, force=force, doc_filter=doc_filter)
    
    save_index(index_data)
    
    docs_with_pages = sum(1 for d in index_data.get('documents', []) if d.get('page_index'))
    total_entries = sum(len(d.get('page_index', [])) for d in index_data.get('documents', []))
    
    print()
    print(f"完成: 更新了 {updated}/{total_docs} 个文档的页码索引")
    print(f"有页码索引的文档: {docs_with_pages}/{total_docs}")
    print(f"总索引条目: {total_entries} 条")


if __name__ == "__main__":
    main()
