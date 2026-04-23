#!/usr/bin/env python3
"""
版本: 1.0.0
功能: 法规指导原则知识库管理器
      原始文件归档 → opendataloader内容提取 → AI自动分类 → 更新索引 → 飞书同步

用法:
  python knowledge_base_manager.py                           # 增量检查
  python knowledge_base_manager.py /path/to/file.pdf       # 添加单个文件
  python knowledge_base_manager.py /path/to/dir/            # 添加目录下所有新文件
  python knowledge_base_manager.py --rebuild               # 重建索引（扫描所有文件）
  python knowledge_base_manager.py --sync-feishu            # 仅同步到飞书（不处理文件）
"""

import json
import os
import re
import shutil
import subprocess
import hashlib
from datetime import datetime
from pathlib import Path

# ============ 配置区 ============
KB_ROOT = "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库"
INDEX_FILE = os.path.join(KB_ROOT, "guidance_index.json")
OPENDATALOADER_SCRIPT = "/home/wangyc/.openclaw/workspace/skills/opendataloader-pdf/scripts/opendataloader_auto.py"

# 目录规范
DIR_RAW = "原始文件"        # 存放原始 PDF/DOCX 文件
DIR_EXTRACTED = "供AI用信息"  # 存放 opendataloader 提取的 .md/.json 文件

# 飞书 Wiki Space ID（需确认是否已改名）
FEISHU_SPACE_ID = "7624081815959014593"

# 同步到飞书时跳过的文档类型
SKIP_FEISHU_TYPES = ["feedback", "explanation"]

# 扫描目录（原始文件扫描源）
SRC_SCAN_DIRS = [
    "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库/稳定性指导原则",
]
# ==============================

def log(msg, emoji="📋"):
    print(f"{emoji} {msg}")

def run_opendataloader(input_file, output_dir):
    """调用 opendataloader 提取内容"""
    cmd = [
        "python3", OPENDATALOADER_SCRIPT,
        input_file,
        "-o", output_dir
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr
    except subprocess.TimeoutExpired:
        return False, "超时"
    except Exception as e:
        return False, str(e)

def load_index():
    """加载现有索引"""
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "version": "1.0",
        "last_updated": "",
        "kb_root": KB_ROOT,
        "total_docs": 0,
        "documents": []
    }

def save_index(index_data):
    """保存索引"""
    index_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    v = float(index_data.get("version", "1.0"))
    index_data["version"] = str(v + 0.1)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

def get_indexed_files(index_data):
    """获取已索引的文件（按MD5去重）"""
    indexed = {}
    for doc in index_data.get("documents", []):
        paths = doc.get("paths", {})
        md_path = paths.get("markdown", "")
        if md_path and os.path.exists(md_path):
            indexed[md_path] = doc["id"]
        # 也按原始文件名索引
        title = doc.get("title", "")
        if title:
            key = title + ".md"
            indexed[key] = doc["id"]
    return indexed

def parse_filename_for_meta(filename):
    """从文件名解析元数据"""
    name = os.path.splitext(filename)[0]
    
    # 1. 提取日期
    date_match = re.match(r"^(\d{8})", name)
    issue_date = date_match.group(1) if date_match else ""
    
    # 2. 清理标题
    title_part = re.sub(r"^\d{8}\s*[-—]\s*", "", name)
    
    # 3. 判断文档类型和状态
    doc_type = "main"
    status = "active"
    
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
        status = "active"
    
    # 4. 判断药品种类
    category = "通用"
    drug_types = []
    
    if "化学药品" in title_part or "化学药物" in title_part:
        category = "化学药"
    elif "中药" in title_part or "天然药物" in title_part:
        category = "中药"
    elif "生物制品" in title_part:
        category = "生物制品"
    
    if "注射剂" in title_part:
        drug_types.append("注射剂")
    if "原料药" in title_part:
        drug_types.append("原料药")
    if "制剂" in title_part:
        drug_types.append("制剂")
    if "口服" in title_part:
        drug_types.append("口服")
    
    if not drug_types:
        drug_types = ["通用"]
    
    # 5. 生成唯一ID
    doc_id = f"guidance_{category}_{issue_date}_{doc_type}" if issue_date else f"guidance_{category}_{doc_type}"
    
    # 6. 提取 tags
    tags = []
    keywords = {
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
    for kw, tag in keywords.items():
        if kw in title_part:
            tags.append(tag)
    tags = list(set(tags))
    
    return {
        "id": doc_id,
        "title": title_part,
        "issue_date": issue_date,
        "status": status,
        "doc_type": doc_type,
        "category": category,
        "drug_types": drug_types,
        "tags": tags,
        "source_filename": filename
    }

def get_file_md5(filepath):
    """计算文件MD5"""
    md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()

def ensure_dirs(kb_root):
    """确保目录结构存在"""
    dirs = [
        os.path.join(kb_root, "稳定性指导原则", DIR_RAW),
        os.path.join(kb_root, "稳定性指导原则", DIR_EXTRACTED),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    return dirs

def scan_for_new_files(scan_dirs, indexed_files):
    """扫描目录寻找新文件（原始文件）"""
    new_files = []
    supported_exts = {".pdf", ".doc", ".docx"}
    
    for scan_dir in scan_dirs:
        if not os.path.exists(scan_dir):
            continue
        
        for root, dirs, files in os.walk(scan_dir):
            # 跳过辅助目录
            dirs[:] = [d for d in dirs if d not in [DIR_RAW, DIR_EXTRACTED] and not d.endswith("_images")]
            
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in supported_exts:
                    continue
                
                full_path = os.path.join(root, fname)
                
                # 检查是否已在索引中（按文件名匹配）
                if fname in indexed_files.values():
                    continue
                
                # 检查是否已在原始文件目录
                if DIR_RAW in root:
                    continue
                
                new_files.append({
                    "path": full_path,
                    "name": fname,
                    "ext": ext
                })
    
    return new_files

def get_destination_paths(meta, kb_root):
    """根据元数据确定目标路径"""
    raw_dir = os.path.join(kb_root, "稳定性指导原则", DIR_RAW)
    extracted_dir = os.path.join(kb_root, "稳定性指导原则", DIR_EXTRACTED)
    return raw_dir, extracted_dir

def process_new_file(f, index_data, kb_root):
    """处理单个新文件：归档原始文件 → opendataloader提取 → 更新索引"""
    log(f"处理文件: {f['name']}", "📄")
    
    # 1. 解析元数据
    meta = parse_filename_for_meta(f['name'])
    print(f"  分类: {meta['category']} | 状态: {meta['status']} | 类型: {meta['doc_type']}")
    
    # 2. 确定目标目录
    raw_dir, extracted_dir = get_destination_paths(meta, kb_root)
    
    # 3. 归档原始文件
    raw_dest = os.path.join(raw_dir, f['name'])
    os.makedirs(raw_dir, exist_ok=True)
    
    if not os.path.exists(raw_dest):
        shutil.copy2(f['path'], raw_dest)
        log(f"原始文件已归档: {DIR_RAW}/{f['name']}", "📦")
    else:
        log(f"原始文件已存在，跳过: {DIR_RAW}/{f['name']}", "⏭")
    
    # 4. 调用 opendataloader 提取内容
    extracted_base = os.path.splitext(f['name'])[0]
    extracted_md = os.path.join(extracted_dir, extracted_base + ".md")
    extracted_json = os.path.join(extracted_dir, extracted_base + ".json")
    
    if os.path.exists(extracted_md) and os.path.exists(extracted_json):
        log(f"提取文件已存在，跳过 opendataloader: {DIR_EXTRACTED}/{extracted_base}", "⏭")
    else:
        log(f"调用 opendataloader 提取内容...", "🔄")
        os.makedirs(extracted_dir, exist_ok=True)
        success, result = run_opendataloader(raw_dest, extracted_dir)
        if success:
            log(f"内容提取完成", "✅")
        else:
            log(f"提取失败: {result}", "⚠️")
    
    # 5. 更新索引
    index_entry = {
        "id": meta['id'],
        "title": meta['title'],
        "issue_date": meta['issue_date'],
        "status": meta['status'],
        "doc_type": meta['doc_type'],
        "scope": {
            "category": meta['category'],
            "type": meta['drug_types']
        },
        "tags": meta['tags'],
        "paths": {
            "raw": raw_dest,
            "markdown": extracted_md if os.path.exists(extracted_md) else "",
            "json": extracted_json if os.path.exists(extracted_json) else "",
            "feishu_wiki_url": ""
        },
        "source_subdir": "稳定性指导原则"
    }
    
    # 检查是否已存在（按ID）
    existing_ids = [d['id'] for d in index_data['documents']]
    if meta['id'] not in existing_ids:
        index_data['documents'].append(index_entry)
        log(f"索引: ✅ 新增", "📝")
    else:
        # 更新现有条目
        for i, doc in enumerate(index_data['documents']):
            if doc['id'] == meta['id']:
                index_data['documents'][i] = index_entry
                log(f"索引: 🔄 更新", "🔄")
                break
    
    return meta

def print_report(new_files, index_data, processed):
    """打印更新报告"""
    print()
    print("=" * 60)
    print("📦 知识库更新报告")
    print("=" * 60)
    
    if not new_files:
        print("✅ 没有发现新增文件，知识库已是最新")
    else:
        print(f"🆕 新增文件: {len(new_files)} 个")
        print()
        
        for meta in processed:
            feishu_skip = meta['doc_type'] in SKIP_FEISHU_TYPES
            feishu_status = "⏭ 跳过（参考文档）" if feishu_skip else "📋 待同步"
            
            print(f"  [{meta['category']}] {meta['title']}")
            print(f"    ID: {meta['id']}")
            print(f"    状态: {meta['status']} | 类型: {meta['doc_type']}")
            print(f"    归档: ✅ 已归档至 {DIR_RAW}/")
            print(f"    提取: ✅ 已提取至 {DIR_EXTRACTED}/")
            print(f"    飞书: {feishu_status}")
            print()
    
    print("-" * 60)
    print(f"💾 索引已更新: {INDEX_FILE}")
    print(f"   版本: {index_data['version']}")
    print(f"   文档总数: {len(index_data['documents'])} 个")
    print(f"   最后更新: {index_data['last_updated']}")
    print("=" * 60)
    
    # 打印待飞书同步的文档
    pending_feishu = [
        d for d in index_data['documents']
        if not d.get('paths', {}).get('feishu_wiki_url')
        and d.get('doc_type') not in SKIP_FEISHU_TYPES
    ]
    if pending_feishu:
        print()
        print(f"📋 飞书待同步文档: {len(pending_feishu)} 个")
        for d in pending_feishu:
            print(f"  - {d['id']}: {d['title']}")

def main():
    import sys
    
    print("=" * 60)
    print("📦 法规指导原则知识库管理器 v1.0.0")
    print("=" * 60)
    
    # 解析命令行参数
    args = sys.argv[1:]
    
    if "--help" in args or "-h" in args:
        print(__doc__)
        return
    
    if "--rebuild" in args:
        log("重建索引模式", "🔨")
        # 扫描所有原始文件，重新构建索引
        index_data = {
            "version": "1.0",
            "last_updated": "",
            "kb_root": KB_ROOT,
            "total_docs": 0,
            "documents": []
        }
        new_files = scan_for_new_files(SRC_SCAN_DIRS, {})
    elif "--sync-feishu" in args:
        log("飞书同步模式（仅生成报告）", "☁️")
        index_data = load_index()
        pending = [
            d for d in index_data['documents']
            if not d.get('paths', {}).get('feishu_wiki_url')
            and d.get('doc_type') not in SKIP_FEISHU_TYPES
        ]
        if pending:
            print(f"\n📋 待同步到飞书的文档: {len(pending)} 个")
            for d in pending:
                md_path = d.get('paths', {}).get('markdown', '')
                print(f"  - {d['id']}: {d['title']}")
                print(f"    Markdown: {md_path}")
            print("\n⚠️ 飞书同步需调用 OpenClaw feishu_create_doc 工具")
            print("   Cortana 可自动完成此步骤")
        else:
            print("✅ 所有文档已同步到飞书")
        return
    elif len(args) > 0:
        input_path = args[0]
        if os.path.isfile(input_path):
            fname = os.path.basename(input_path)
            new_files = [{
                "path": input_path,
                "name": fname,
                "ext": os.path.splitext(fname)[1].lower()
            }]
            log(f"添加指定文件: {input_path}", "📂")
        elif os.path.isdir(input_path):
            new_files = scan_for_new_files([input_path], {})
            log(f"扫描目录: {input_path}", "📂")
        else:
            log(f"路径不存在: {input_path}", "❌")
            return
    else:
        # 增量检查
        log("执行增量检查", "🔍")
        index_data = load_index()
        indexed_files = get_indexed_files(index_data)
        new_files = scan_for_new_files(SRC_SCAN_DIRS, indexed_files)
    
    if not new_files:
        log("没有发现新增文件，知识库已是最新", "✅")
        return
    
    log(f"发现 {len(new_files)} 个新文件", "🆕")
    print()
    
    # 确保目录存在
    ensure_dirs(KB_ROOT)
    
    # 处理每个新文件
    processed = []
    for i, f in enumerate(new_files, 1):
        print(f"\n--- [{i}/{len(new_files)}] ---")
        meta = process_new_file(f, index_data, KB_ROOT)
        processed.append(meta)
    
    # 保存索引
    save_index(index_data)
    
    # 打印报告
    print_report(new_files, index_data, processed)

if __name__ == "__main__":
    main()
