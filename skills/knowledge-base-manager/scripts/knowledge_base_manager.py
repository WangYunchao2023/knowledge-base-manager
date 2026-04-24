#!/usr/bin/env python3
"""
版本: 3.0.0
功能: 法规指导原则知识库管理器
      原始文件归档 → opendataloader内容提取 → AI自动分类 → 更新索引 → 触发 graphify 钩子

用法:
  python knowledge_base_manager.py                           # 增量检查
  python knowledge_base_manager.py /path/to/file.pdf       # 添加单个文件
  python knowledge_base_manager.py /path/to/dir/            # 添加目录下所有新文件
  python knowledge_base_manager.py --rebuild               # 重建索引（扫描所有文件）
  python knowledge_base_manager.py --trigger-hook HOOK     # 触发指定钩子（供 watchdog 调用）
  python knowledge_base_manager.py --status                # 查看索引状态

钩子触发（watchdog 监控后调用）:
  --trigger-hook graphify   → 触发 graphify 图谱更新
  --trigger-hook dify       → 触发 Dify 数据集重建
  --trigger-hook all        → 触发所有钩子
"""

import json
import os
import re
import shutil
import subprocess
import hashlib
import sys
from datetime import datetime
from pathlib import Path

# ============ 配置区 ============
KB_ROOT = "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库"
INDEX_FILE = os.path.join(KB_ROOT, "guidance_index.json")
OPENDATALOADER_SCRIPT = "/home/wangyc/.openclaw/workspace/skills/opendataloader-pdf/opendataloader_auto.py"

# 目录规范
DIR_RAW = "原始文件"
DIR_EXTRACTED = "供AI用信息"

# 默认扫描源（稳定指导原则的原始文件放入目录）
SRC_SCAN_DIRS = [
    "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库/稳定性",
]

# Graphify 配置
GRAPHIFY_TARGET = os.path.join(KB_ROOT, "稳定性", DIR_EXTRACTED)
GRAPHIFY_OUTPUT = os.path.join(KB_ROOT, "graphify-out")

# Dify 配置
DIFY_API_URL = os.environ.get("DIFY_API_URL", "http://localhost/v1")
DIFY_API_KEY = os.environ.get("DIFY_API_KEY", "")
DIFY_DATASET_ID = os.environ.get("DIFY_DATASET_ID", "")

# Hook 脚本路径
HOOK_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
GRAPHIFY_HOOK = os.path.join(HOOK_SCRIPTS_DIR, "graphify_integration.py")
GRAPHIFY_JOB = os.path.join(HOOK_SCRIPTS_DIR, "graphify_job.py")
DIFY_HOOK = os.path.join(HOOK_SCRIPTS_DIR, "dify_integration.py")
ADD_SECTION_INDEX = os.path.join(HOOK_SCRIPTS_DIR, "add_section_index.py")
ADD_PAGE_INDEX = os.path.join(HOOK_SCRIPTS_DIR, "add_page_index.py")

# ===== 自动分类配置 =====
# 一级分类目录（基于 metadata category）
CATEGORY_SUBDIRS = {
    "化学药": "化学药",
    "中药": "中药",
    "生物制品": "生物制品",
    "通用": "通用",
}

# 二级分类子目录（在每个一级分类下创建）
# 顺序：按匹配优先级排列（先匹配的先生效）
GUIDANCE_SUBDIRS = [
    "稳定性",
    "临床研究",
    "药理学",
    "毒理学",
    "质量标准",
    "申报注册",
    "其他",
]

# 关键词 → 二级子目录 映射（按优先级）
SUBDIR_KEYWORDS = [
    ("稳定性", "稳定性"),
    ("临床研发", "临床研究"),
    ("临床试验", "临床研究"),
    ("以患者为中心", "临床研究"),
    ("药理学", "药理学"),
    ("毒理学", "毒理学"),
    ("质量标准", "质量标准"),
    ("申报", "申报注册"),
    ("注册", "申报注册"),
    ("注射剂", "稳定性"),  # 注射剂常涉及配伍稳定性
    ("配伍", "稳定性"),
    ("原料药", "稳定性"),
    ("制剂", "稳定性"),
]

def _match_subdir(title):
    """根据文件名关键词匹配二级子目录（返回第一个匹配的）"""
    for kw, subdir in SUBDIR_KEYWORDS:
        if kw in title:
            return subdir
    return None  # 不匹配任何已知关键词
# ==============================

def log(msg, emoji="📋"):
    print(f"{emoji} {msg}")

# ---- 自动分类器 ----

def get_category_dir(category):
    """根据分类获取一级目录名"""
    return CATEGORY_SUBDIRS.get(category, "通用")


def get_guidance_subdir(title, category):
    """
    根据文档标题自动判断二级子目录。
    1. 先用关键词匹配（SUBDIR_KEYWORDS）
    2. 若匹配到的子目录不在当前 GUIDANCE_SUBDIRS 中，动态追加
    3. 若无匹配，返回「其他」
    """
    # 关键词匹配
    matched = _match_subdir(title)
    if matched is None:
        matched = "其他"
    
    # 动态追加：如果匹配到的子目录不在已知列表中，自动追加
    if matched not in GUIDANCE_SUBDIRS:
        GUIDANCE_SUBDIRS.append(matched)
        log(f"🆕 发现新二级目录类型「{matched}」，已自动追加到配置", "📁")
    
    return matched


def resolve_destination_dir(meta):
    """
    根据文档 metadata 决定目标目录结构。
    返回 (一级目录, 二级目录, 相对路径前缀)
    
    例如化学药 + 稳定性:
      一级: 化学药
      二级: 稳定性
      相对路径前缀: 化学药/稳定性/
    
    注意：动态创建的二级子目录（如「临床研究」）
    会在首次发现时自动在所有一级分类下创建对应目录。
    """
    cat_dir = get_category_dir(meta["category"])
    guidance_dir = get_guidance_subdir(meta["title"], meta["category"])
    
    # 若发现新二级子目录，立即在所有分类下创建其目录结构
    _ensure_new_subdir_all_categories(KB_ROOT, guidance_dir)
    
    # 相对 KB_ROOT 的路径前缀
    rel_prefix = os.path.join(cat_dir, guidance_dir)
    
    return cat_dir, guidance_dir, rel_prefix


def _ensure_new_subdir_all_categories(kb_root, new_subdir):
    """
    在所有一级分类目录下创建新二级子目录的完整结构（原始文件/ + 供AI用信息/）。
    仅在新二级子目录首次出现时调用。
    """
    state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jobs", "subdirs.json")
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    
    known = {}
    if os.path.exists(state_file):
        try:
            known = json.load(open(state_file))
        except:
            known = {}
    
    if new_subdir in known:
        return  # 已处理过
    
    known[new_subdir] = True
    json.dump(known, open(state_file, "w"), ensure_ascii=False)
    
    for cat in CATEGORY_SUBDIRS.values():
        for sub in [DIR_RAW, DIR_EXTRACTED]:
            path = os.path.join(kb_root, cat, new_subdir, sub)
            os.makedirs(path, exist_ok=True)
    log(f"🆕 自动创建新二级目录「{new_subdir}」（原始文件/ + 供AI用信息/）", "📁")


def ensure_category_dirs(kb_root, category):
    """确保某个分类下的标准目录结构存在"""
    cat_dir = get_category_dir(category)
    for subdir in GUIDANCE_SUBDIRS:
        for sub in [DIR_RAW, DIR_EXTRACTED]:
            path = os.path.join(kb_root, cat_dir, subdir, sub)
            os.makedirs(path, exist_ok=True)


# ---- opendataloader ----

def run_opendataloader(input_file, output_dir, force_mode=None):
    """
    调用 opendataloader 提取内容。
    若提取内容为空，自动升级模式重试：
      digital → hybrid（扫描 PDF 误判）
      fast    → hybrid（复杂文档）
    """
    for attempt in range(2):
        cmd = ["python3", OPENDATALOADER_SCRIPT, input_file, "-o", output_dir]
        if force_mode:
            cmd.extend(["--force-mode", force_mode])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                return False, result.stderr

            # 验证提取结果是否有效
            extracted_base = os.path.splitext(os.path.basename(input_file))[0]
            json_path = os.path.join(output_dir, extracted_base + ".json")
            md_path = os.path.join(output_dir, extracted_base + ".md")

            if not os.path.exists(json_path):
                return False, f"JSON 文件未生成: {json_path}"

            # 内容有效性检查
            with open(json_path, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read(500)
            if not raw.strip() or raw == "{\n}":
                raise ValueError("JSON 内容为空")

            try:
                data = json.loads(raw if len(raw) > 50 else open(json_path).read())
            except json.JSONDecodeError:
                raise ValueError("JSON 解析失败")

            # 检查 kids 是否为空（PDF）或 elements 是否为空（DOCX）
            kids = data.get("kids", data.get("flat_elements", []))
            if isinstance(kids, list) and len(kids) == 0:
                raise ValueError("JSON 无段落内容（kids/elements 均为空）")

            # 检查 .md 是否为空
            if os.path.exists(md_path):
                md_size = os.path.getsize(md_path)
                if md_size < 100:
                    raise ValueError(f".md 内容过少（{md_size} bytes）")

            return True, result.stdout

        except subprocess.TimeoutExpired:
            return False, "超时"
        except Exception as e:
            last_err = str(e)

        # 重试逻辑：digital → hybrid
        if force_mode is None:
            force_mode = "hybrid"
        else:
            break  # 第二次仍然失败，放弃

    return False, f"提取失败（已重试）: {last_err}"

# ---- 索引读写 ----

def load_index():
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "version": "3.0",
        "last_updated": "",
        "kb_root": KB_ROOT,
        "total_docs": 0,
        "documents": []
    }

def save_index(index_data):
    index_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    try:
        v = float(index_data.get("version", "1.0"))
        index_data["version"] = str(v + 0.1)
    except ValueError:
        index_data["version"] = "3.0"
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

def get_indexed_ids(index_data):
    return {d["id"] for d in index_data.get("documents", [])}

# ---- 文件名解析 ----

def parse_filename_for_meta(filename):
    name = os.path.splitext(filename)[0]
    date_match = re.match(r"^(\d{8})", name)
    issue_date = date_match.group(1) if date_match else ""
    title_part = re.sub(r"^\d{8}\s*[-—]\s*", "", name)
    
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
    
    category = "通用"
    if "化学药品" in title_part or "化学药物" in title_part:
        category = "化学药"
    elif "中药" in title_part or "天然药物" in title_part:
        category = "中药"
    elif "生物制品" in title_part:
        category = "生物制品"
    
    drug_types = []
    for kw in ["注射剂", "原料药", "制剂", "口服"]:
        if kw in title_part:
            drug_types.append(kw)
    if not drug_types:
        drug_types = ["通用"]
    
    doc_id = f"guidance_{category}_{issue_date}_{doc_type}" if issue_date else f"guidance_{category}_{doc_type}"
    
    tags = []
    for kw in ["稳定性", "配伍", "注射剂", "原料药", "制剂", "化学药", "中药", "生物制品", "研究技术", "指导原则"]:
        if kw in title_part:
            tags.append(kw)
    
    return {
        "id": doc_id,
        "title": title_part,
        "issue_date": issue_date,
        "status": status,
        "doc_type": doc_type,
        "category": category,
        "drug_types": drug_types,
        "tags": list(set(tags)),
        "source_filename": filename
    }

# ---- 目录保障 ----

def ensure_dirs(kb_root):
    """确保所有分类目录结构存在"""
    for cat in CATEGORY_SUBDIRS.values():
        for subdir in GUIDANCE_SUBDIRS:
            for sub in [DIR_RAW, DIR_EXTRACTED]:
                os.makedirs(os.path.join(kb_root, cat, subdir, sub), exist_ok=True)
    # graphify-out 目录
    os.makedirs(GRAPHIFY_OUTPUT, exist_ok=True)

# ---- 文件扫描 ----

def scan_for_new_files(scan_dirs, indexed_ids):
    new_files = []
    supported_exts = {".pdf", ".doc", ".docx"}
    for scan_dir in scan_dirs:
        if not os.path.exists(scan_dir):
            continue
        for root, dirs, files in os.walk(scan_dir):
            # 跳过已分类的子目录（化学药/中药/生物制品/通用）
            dirs[:] = [d for d in dirs if d not in CATEGORY_SUBDIRS.values() 
                       and d not in [DIR_RAW, DIR_EXTRACTED] 
                       and not d.endswith("_images")]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in supported_exts:
                    continue
                full_path = os.path.join(root, fname)
                meta = parse_filename_for_meta(fname)
                if meta["id"] in indexed_ids:
                    continue
                new_files.append({"path": full_path, "name": fname, "ext": ext})
    return new_files

# ---- 单文件处理 ----

def compute_page_hash(json_path, page_num):
    """
    从 opendataloader 的 JSON（带 PDF 页码）中提取指定页的纯文本段落，
    按 bounding box 顺序拼接后计算 SHA256。
    
    参数:
        json_path: opendataloader 输出的 .json 文件路径
        page_num:  PDF 页码（1-based）
    返回:
        字符串的 SHA256 哈希值；若页不存在或出错返回 None
    """
    if not os.path.exists(json_path):
        return None
    try:
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None

    # 从 kids 中提取该页的所有段落（paragraph type）
    paragraphs = []
    def extract_pages(item):
        if isinstance(item, dict):
            pn = item.get("page number") or item.get("page")
            if pn == page_num and item.get("type") == "paragraph":
                text = item.get("content", "").strip()
                if text:
                    paragraphs.append((item.get("bounding box", [0])[0], text))
            for child in item.get("kids", []):
                extract_pages(child)
        elif isinstance(item, list):
            for sub in item:
                extract_pages(sub)

    extract_pages(data)

    if not paragraphs:
        # fallback：尝试直接遍历 kids
        for item in data.get("kids", []):
            extract_pages(item)

    if not paragraphs:
        return None

    # 按 bounding box x 坐标排序（同一页内从左到右）
    paragraphs.sort(key=lambda x: x[0])
    combined = "\n".join(t for _, t in paragraphs)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def compute_pdf_byte_hash(json_path):
    """
    当 PDF 正文前两页均为图片/扫描页（无可提取文本）时，
    用 PDF 原始文件的 SHA256 作为保底哈希。
    精确度不如文本哈希，但能检测字节级相同的文件。
    """
    # 从 JSON 中找到对应的原始 PDF 路径
    try:
        data = json.load(open(json_path, encoding="utf-8", errors="replace"))
        fname = data.get("file name", "") or data.get("original_pdf", "")
        if not fname or not os.path.exists(fname):
            # 尝试从 json_path 反推原始 PDF
            md_basename = os.path.basename(json_path).replace(".json", ".pdf")
            candidates = [
                md_basename,
                md_basename.replace(" _images", ""),
            ]
            for c in candidates:
                # 在 KB_ROOT 下搜索
                import glob
                found = glob.glob(os.path.join(KB_ROOT, "**", c), recursive=True)
                if found:
                    fname = found[0]
                    break
        if fname and os.path.exists(fname):
            with open(fname, "rb") as fh:
                return hashlib.sha256(fh.read()).hexdigest()
    except Exception:
        pass
    return None


def compute_content_hash_from_pages(json_path):
    """
    对 PDF 正文前两页（第1页 + 第2页）分别计算内容哈希。
    返回 {"page1": hash, "page2": hash}；
    若某页不存在或无法提取，hash 为 None。
    若前两页均无可提取文本，自动补充 PDF 字节哈希作为保底。
    用于内容级去重（排版不同/表格提取差异不影响前两页的文本内容）。
    """
    p1 = compute_page_hash(json_path, 1)
    p2 = compute_page_hash(json_path, 2)
    result = {"page1": p1, "page2": p2}
    # 前两页均无文本 → 补充 PDF 字节哈希保底
    if p1 is None and p2 is None:
        pdf_hash = compute_pdf_byte_hash(json_path)
        if pdf_hash:
            result["pdf_byte"] = pdf_hash
    return result


def check_duplicate_by_hash(extracted_json, index_data):
    """
    基于 PDF 正文第1页 + 第2页的纯文本内容哈希进行去重。
    两页都与已有文档相同 → 判定为重复。
    仅第1页相同 → 不视为重复（可能是同一系列文件的封面相同）。

    返回 (is_duplicate, conflicting_doc)
    """
    hashes = compute_content_hash_from_pages(extracted_json)
    if not hashes:
        return False, None  # 无法提取，无从对比，不拦截

    # 优先用文本哈希比对（前两页内容哈希）
    for doc in index_data.get("documents", []):
        stored = doc.get("content_hash", {})
        if not stored or not isinstance(stored, dict):
            continue

        p1_match = hashes["page1"] and stored.get("page1") == hashes["page1"]
        p2_match = hashes["page2"] and stored.get("page2") == hashes["page2"]

        if p1_match and p2_match:
            return True, doc  # 两页文本均相同，判定为重复
    
    # 保底：PDF 字节哈希比对（全扫描文档，无可提取文本时）
    pdf_byte = hashes.get("pdf_byte")
    if pdf_byte:
        for doc in index_data.get("documents", []):
            stored = doc.get("content_hash", {})
            if stored.get("pdf_byte") == pdf_byte:
                return True, doc  # PDF 字节完全相同，判定为重复

    return False, None


def process_new_file(f, index_data):
    log(f"处理文件: {f['name']}", "📄")
    meta = parse_filename_for_meta(f['name'])
    print(f"  自动分类: {meta['category']} | 状态: {meta['status']} | 类型: {meta['doc_type']}")
    
    # 解析目标目录
    cat_dir, guidance_subdir, rel_prefix = resolve_destination_dir(meta)
    
    # 目标子目录路径（相对 KB_ROOT）
    raw_dir = os.path.join(rel_prefix, DIR_RAW)
    extracted_dir = os.path.join(rel_prefix, DIR_EXTRACTED)
    raw_abs = os.path.join(KB_ROOT, raw_dir)
    extracted_abs = os.path.join(KB_ROOT, extracted_dir)
    
    os.makedirs(raw_abs, exist_ok=True)
    os.makedirs(extracted_abs, exist_ok=True)
    
    # 1. 归档原始文件（按分类存放）
    raw_dest = os.path.join(raw_abs, f['name'])
    if not os.path.exists(raw_dest):
        shutil.copy2(f['path'], raw_dest)
        log(f"  → 原始文件已归档: {raw_dir}/{f['name']}", "📦")
    else:
        log(f"  → 原始文件已存在，跳过归档", "⏭")
    
    # 2. opendataloader 提取
    extracted_base = os.path.splitext(f['name'])[0]
    extracted_md = os.path.join(extracted_abs, extracted_base + ".md")
    extracted_json = os.path.join(extracted_abs, extracted_base + ".json")
    
    if os.path.exists(extracted_md) and os.path.exists(extracted_json):
        log(f"  → 提取文件已存在，跳过 opendataloader", "⏭")
    else:
        log(f"  → 调用 opendataloader 提取内容...", "🔄")
        success, result = run_opendataloader(raw_dest, extracted_abs)
        if success:
            log(f"  → 内容提取完成", "✅")
        else:
            log(f"  → 提取失败: {result}", "⚠️")
    
    # 2.5 内容哈希去重检查（基于 PDF 正文第1+2页纯文本）
    if os.path.exists(extracted_json):
        is_dup, dup_doc = check_duplicate_by_hash(extracted_json, index_data)
        if is_dup:
            log(f"  ⚠️  内容与已有文档重复，已跳过入库", "🔄")
            print(f"  重复文档: {dup_doc['title']}（{dup_doc.get('issue_date', '无日期')}）")
            return None  # 跳过入库
    
    # 3. 构建索引条目（路径为相对路径）
    content_hash = compute_content_hash_from_pages(extracted_json) if os.path.exists(extracted_json) else None
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
        "content_hash": content_hash,
        "paths": {
            "raw": os.path.join(rel_prefix, DIR_RAW, f['name']),
            "markdown": os.path.join(rel_prefix, DIR_EXTRACTED, extracted_base + ".md"),
            "json": os.path.join(rel_prefix, DIR_EXTRACTED, extracted_base + ".json"),
            "graph_url": ""
        },
        "source_subdir": os.path.join(cat_dir, guidance_subdir)
    }
    
    # 4. 写入索引
    existing_ids = [d['id'] for d in index_data['documents']]
    if meta['id'] not in existing_ids:
        index_data['documents'].append(index_entry)
        log(f"  → 索引: ✅ 新增 [{rel_prefix}]", "📝")
    else:
        for i, doc in enumerate(index_data['documents']):
            if doc['id'] == meta['id']:
                index_data['documents'][i] = index_entry
                log(f"  → 索引: 🔄 更新", "🔄")
                break
    
    return meta

# ---- 钩子触发 ----

def trigger_graphify_hook():
    """
    立即后台启动 graphify 增量更新（无 cron 轮询）。
    watchdog 触发 → 索引更新 → 立即后台启动 graphify。
    """
    try:
        subprocess.run(
            ["python3", GRAPHIFY_JOB, "--enqueue"],
            capture_output=True, timeout=10
        )
    except Exception as e:
        log(f"graphify 作业入队失败: {e}，继续直接启动", "⚠️")

    mode_flag = " --update"
    cmd = (
        f"cd {GRAPHIFY_TARGET} && "
        f"nohup openclaw agent --message "
        f"'请执行 graphify 图谱增量更新：/graphify {GRAPHIFY_TARGET}{mode_flag}。"
        f"完成后报告节点数、边数。' "
        f"--timeout 600 > /tmp/graphify_bg.log 2>&1 &"
    )
    try:
        subprocess.run(["bash", "-c", cmd], timeout=10)
        log("Graphify 已在后台启动（增量更新）", "🕸️")
        return True, "后台启动完成"
    except Exception as e:
        log(f"Graphify 后台启动失败: {e}", "⚠️")
        return False, str(e)

def trigger_dify_hook():
    log("触发 Dify 数据集更新...", "🔍")
    try:
        result = subprocess.run(
            ["python3", DIFY_HOOK, "--sync"],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            log("Dify 数据集更新完成", "✅")
            return True, result.stdout
        else:
            log(f"Dify 更新失败: {result.stderr}", "⚠️")
            return False, result.stderr
    except Exception as e:
        log(f"Dify 钩子执行异常: {e}", "❌")
        return False, str(e)

def trigger_hooks(hook_names):
    results = {}
    for hook in hook_names:
        if hook == "graphify":
            results["graphify"] = trigger_graphify_hook()
        elif hook == "dify":
            results["dify"] = trigger_dify_hook()
    return results

# ---- 报告打印 ----

def print_report(new_files, index_data, processed, hook_results=None):
    print()
    print("=" * 60)
    print("📦 知识库更新报告  v3.0.0")
    print("=" * 60)
    
    if not new_files:
        print("✅ 没有发现新增文件，知识库已是最新")
    else:
        print(f"🆕 新增/更新文件: {len(new_files)} 个")
        print()
        for meta in processed:
            cat_dir, guidance_subdir, rel_prefix = resolve_destination_dir(meta)
            print(f"  [{meta['category']}] {meta['title']}")
            print(f"    ID: {meta['id']} | 状态: {meta['status']} | 类型: {meta['doc_type']}")
            print(f"    分类路径: {rel_prefix}/")
            print()
    
    if hook_results:
        print("-" * 60)
        print("🔗 钩子触发结果:")
        for name, (ok, msg) in hook_results.items():
            status = "✅" if ok else "❌"
            print(f"  {status} {name}: {msg[:80] if msg else '完成'}")
    
    print("-" * 60)
    print(f"💾 索引: {INDEX_FILE}")
    print(f"   版本: {index_data['version']} | 文档总数: {len(index_data['documents'])} 个")
    print(f"   最后更新: {index_data['last_updated']}")
    print("=" * 60)

def print_status(index_data):
    print("=" * 60)
    print("📊 知识库状态")
    print("=" * 60)
    print(f"索引文件: {INDEX_FILE}")
    print(f"版本: {index_data['version']}")
    print(f"最后更新: {index_data['last_updated']}")
    print(f"文档总数: {len(index_data['documents'])} 个")
    print()
    
    from collections import Counter
    cats = Counter(d.get("scope", {}).get("category", "未知") for d in index_data["documents"])
    print("按类别:")
    for cat, cnt in cats.most_common():
        print(f"  {cat}: {cnt} 个")
    
    types = Counter(d.get("doc_type", "未知") for d in index_data["documents"])
    print("按类型:")
    for t, cnt in types.most_common():
        print(f"  {t}: {cnt} 个")
    
    print()
    print("目录结构预览:")
    for cat in CATEGORY_SUBDIRS.values():
        dirs_exist = []
        for subdir in GUIDANCE_SUBDIRS:
            raw = os.path.join(KB_ROOT, cat, subdir, DIR_RAW)
            if os.path.exists(raw):
                files = os.listdir(raw)
                if files:
                    dirs_exist.append(f"{subdir}({len(files)})")
        if dirs_exist:
            print(f"  {cat}/: {', '.join(dirs_exist)}")
    
    print("=" * 60)

# ---- 主入口 ----

def main():
    print("=" * 60)
    print("📦 法规指导原则知识库管理器 v3.0.0")
    print("=" * 60)
    
    args = sys.argv[1:]
    
    if "--help" in args or "-h" in args:
        print(__doc__)
        return
    
    if "--trigger-hook" in args:
        idx = args.index("--trigger-hook")
        hook_name = args[idx + 1] if idx + 1 < len(args) else "all"
        hooks = hook_name.split(",")
        log(f"触发钩子: {hooks}", "⚡")
        results = trigger_hooks(hooks)
        for name, (ok, msg) in results.items():
            print(f"  {'✅' if ok else '❌'} {name}: {msg[:100] if msg else '完成'}")
        return
    
    if "--status" in args:
        index_data = load_index()
        print_status(index_data)
        return
    
    if "--rebuild" in args:
        log("重建索引模式", "🔨")
        index_data = {
            "version": "3.0",
            "last_updated": "",
            "kb_root": KB_ROOT,
            "total_docs": 0,
            "documents": []
        }
        new_files = scan_for_new_files(SRC_SCAN_DIRS, set())
    elif len(args) > 0:
        input_path = args[0]
        if os.path.isfile(input_path):
            fname = os.path.basename(input_path)
            new_files = [{"path": input_path, "name": fname, "ext": os.path.splitext(fname)[1].lower()}]
            log(f"添加指定文件: {input_path}", "📂")
            index_data = load_index()  # 加载索引（单文件模式也需要）
        elif os.path.isdir(input_path):
            new_files = scan_for_new_files([input_path], set())
            log(f"扫描目录: {input_path}", "📂")
        else:
            log(f"路径不存在: {input_path}", "❌")
            return
    else:
        log("执行增量检查", "🔍")
        index_data = load_index()
        indexed_ids = get_indexed_ids(index_data)
        new_files = scan_for_new_files(SRC_SCAN_DIRS, indexed_ids)
    
    if not new_files:
        log("没有发现新增文件，知识库已是最新", "✅")
        if "--hooks" in args:
            hook_name = args[args.index("--hooks") + 1] if args.index("--hooks") + 1 < len(args) else "all"
            results = trigger_hooks(hook_name.split(","))
            print_report(new_files, index_data, [], results)
        return
    
    log(f"发现 {len(new_files)} 个新文件", "🆕")
    print()
    
    ensure_dirs(KB_ROOT)
    
    processed = []
    for i, f in enumerate(new_files, 1):
        print(f"\n--- [{i}/{len(new_files)}] ---")
        meta = process_new_file(f, index_data)
        processed.append(meta)
    
    save_index(index_data)
    
    # 更新章节索引和页码索引
    if processed:
        try:
            subprocess.run(
                ["python3", ADD_SECTION_INDEX, "--rebuild"],
                capture_output=True, timeout=30
            )
            log("章节索引已更新", "📑")
        except Exception as e:
            log(f"章节索引更新失败: {e}", "⚠️")
        try:
            subprocess.run(
                ["python3", ADD_PAGE_INDEX, "--rebuild"],
                capture_output=True, timeout=60
            )
            log("页码索引已更新", "📖")
        except Exception as e:
            log(f"页码索引更新失败: {e}", "⚠️")
    
    hook_results = {}
    if processed:
        hook_results = trigger_hooks(["graphify"])
    
    print_report(new_files, index_data, processed, hook_results)

if __name__ == "__main__":
    main()