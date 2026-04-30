#!/usr/bin/env python3
"""
版本: 2.14.0
功能: 法规指导原则知识库管理器（v2.14.0 新增: 标题相似度三级判断——identical/small/large；small差异常见于（试行）/（征求意见稿）等标注，去括号后相同视同 identical；large 差异即使哈希相同也判定为非重复。v2.13.0 新增: 内容哈希比对前增加标题过滤——不同标题直接跳过哈希比对，解决同一日期不同文件碰巧封面相同导致的假误判）
      v2.12.0 新增: graphify 钩子同步等待修复——轮询 session age 直到 agent 结束
      v2.11.0 新增: 同名不同日期不判定为重复; 源文件未更新则跳过重提取
      v2.10.0 新增磁盘恢复 + 每文件保存 + 崩溃恢复
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
import time
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

def _validate_extraction(extracted_base, output_dir):
    """
    验证 opendataloader 提取结果是否有效。
    返回 (is_valid, error_msg)。
    """
    json_path = os.path.join(output_dir, extracted_base + ".json")
    md_path = os.path.join(output_dir, extracted_base + ".md")

    if not os.path.exists(json_path):
        return False, f"JSON 文件未生成: {json_path}"

    # 内容有效性检查（读全文，避免截断导致解析失败）
    with open(json_path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()
    if not raw.strip() or raw == "{\n}":
        return False, "JSON 内容为空"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False, "JSON 解析失败"

    # 检查 kids 是否为空（PDF）或 elements 是否为空（DOCX）
    kids = data.get("kids", data.get("flat_elements", []))
    if isinstance(kids, list) and len(kids) == 0:
        return False, "JSON 无段落内容（kids/elements 均为空）"

    # 检查 .md 是否为空
    if os.path.exists(md_path):
        md_size = os.path.getsize(md_path)
        if md_size < 100:
            return False, f".md 内容过少（{md_size} bytes）"

    return True, "OK"


def run_opendataloader(input_file, output_dir, force_mode=None, skip_qwen=False, best_quality=True):
    """
    调用 opendataloader 提取内容。

    PDF 使用逐页自适应处理（process_pdf_per_page）：
      - 每页独立判断：digital（有文字）→ opendataloader 快速提取
      - scanned（纯图像）→ qwen2.5vl OCR（skip_qwen=True 时跳过，仅用 Fast）
      - 混合 PDF → 两种方式结合，保留最佳文本
      - skip_qwen=True 时完全跳过 qwen2.5vl，用于批量处理数字 PDF 为主的场景
      - best_quality=True 时强制所有页走 qwen2.5vl，不降级，失败即报错

    DOCX 沿用 subprocess 调用（opendataloader CLI）。
    """
    ext = os.path.splitext(input_file)[1].lower()
    extracted_base = os.path.splitext(os.path.basename(input_file))[0]

    # ---- PDF：逐页自适应处理 ----
    if ext == ".pdf":
        import sys as _sys
        _od_dir = str(Path(OPENDATALOADER_SCRIPT).parent)
        if _od_dir not in _sys.path:
            _sys.path.insert(0, _od_dir)

        try:
            from opendataloader_auto import process_pdf_per_page
        except ImportError as e:
            return False, f"无法导入 process_pdf_per_page: {e}"

        try:
            od_result = process_pdf_per_page(
                pdf_path=input_file,
                output_dir=output_dir,
                output_format="markdown,json",
                force_qwen=False,
                skip_server=False,
                skip_qwen=skip_qwen,
                best_quality=best_quality
            )
        except Exception as e:
            return False, f"process_pdf_per_page 异常: {e}"

        if not od_result.get("success"):
            mode_used = od_result.get("mode_used", "unknown")
            err_msg = od_result.get("error", "")
            ocr_failed = od_result.get("ocr_failed_pages", [])
            detail = err_msg or f"per-page 提取失败（mode={mode_used}）"
            if ocr_failed:
                detail += f"；qwen2.5vl 失败页面: {', '.join(f'第{p}页' for p in ocr_failed)}"
            return False, detail

        # 验证输出文件
        is_valid, err = _validate_extraction(extracted_base, output_dir)
        if not is_valid:
            return False, f"per-page 提取结果验证失败: {err}"

        return True, f"per-page（{od_result.get('mode_used', 'adaptive')}）"

    # ---- DOCX/DOC：subprocess 调用 ----
    for attempt in range(2):
        cmd = ["python3", OPENDATALOADER_SCRIPT, input_file, "-o", output_dir]
        if force_mode:
            cmd.extend(["--force-mode", force_mode])
        if best_quality:
            cmd.append("--best-quality")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                return False, result.stderr

            is_valid, err = _validate_extraction(extracted_base, output_dir)
            if not is_valid:
                raise ValueError(err)

            return True, result.stdout

        except subprocess.TimeoutExpired:
            return False, "超时"
        except Exception as e:
            last_err = str(e)

        # 重试：digital → hybrid
        if force_mode is None:
            force_mode = "hybrid"
        else:
            break

    return False, f"提取失败（已重试）: {last_err}"

# ---- 索引读写 ----

def load_index():
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "version": "3.1",
        "last_updated": "",
        "kb_root": KB_ROOT,
        "total_docs": 0,
        "documents": []
    }

def save_index(index_data):
    index_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    try:
        v_str = str(index_data.get("version", "1.0"))
        if "." in v_str:
            v = float(v_str)
            if v < 10:  # 小版本号（如 1.3, 2.9）
                index_data["version"] = str(round(v + 0.1, 1))
            else:  # 大版本号（如 780）
                index_data["version"] = str(int(v_str) + 1)
    except ValueError:
        index_data["version"] = "1.0"
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

def rebuild_index_from_disk(kb_root, index_data):
    """扫描 KB 目录下所有已提取的 .md/.json，将缺少索引条目的文件补入 index_data。"""
    CATEGORY_SUBDIRS_LOCAL = ['化学药', '中药', '生物制品', '通用']
    DOC_TYPES_LOCAL = ['稳定性', '临床研究', '药理学', '毒理学', '质量标准', '申报注册', '其他']
    added = []
    existing_ids = {d['id'] for d in index_data['documents']}

    for cat in CATEGORY_SUBDIRS_LOCAL:
        cat_path = os.path.join(kb_root, cat)
        if not os.path.isdir(cat_path):
            continue
        for sub in DOC_TYPES_LOCAL:
            md_dir = os.path.join(cat_path, sub, DIR_EXTRACTED)
            if not os.path.isdir(md_dir):
                continue
            for fname in os.listdir(md_dir):
                if not fname.endswith('.md'):
                    continue
                meta = parse_filename_for_meta(fname)
                if meta['id'] in existing_ids:
                    continue
                json_path = os.path.join(md_dir, fname.replace('.md', '.json'))
                if not os.path.exists(json_path):
                    continue
                rel_prefix = os.path.join(cat, sub)
                content_hash = compute_content_hash_from_pages(json_path) if os.path.exists(json_path) else None
                entry = {
                    'id': meta['id'],
                    'title': meta['title'],
                    'issue_date': meta['issue_date'],
                    'status': meta['status'],
                    'doc_type': meta['doc_type'],
                    'scope': {'category': meta['category'], 'type': meta['drug_types']},
                    'tags': meta['tags'],
                    'content_hash': content_hash,
                    'paths': {
                        'raw': '',
                        'markdown': os.path.join(rel_prefix, DIR_EXTRACTED, fname),
                        'json': os.path.join(rel_prefix, DIR_EXTRACTED, fname.replace('.md', '.json')),
                        'graph_url': ''
                    },
                    'source_subdir': os.path.join(cat, sub)
                }
                index_data['documents'].append(entry)
                existing_ids.add(meta['id'])
                added.append(meta['title'])
                print(f'  🔧 [磁盘恢复] {meta["title"]} [{cat}/{sub}]')
    return added

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


def _strip_title_suffix(title):
    """
    去除标题中的【后缀级小差异】标注，返回核心标题。
    这些小差异属于同一文件的不同发布状态，不影响实质性判断：
    - （试行）/ 【试行】/ [试行]
    - （征求意见稿）/ 【征求意见稿】/ [征求意见稿]
    - （修订）/ 【修订】
    - （第一次修订）
    - （2007版）/ （2008版）等年份版本标注
    - （上）/ （下）等分册标注
    - 以及上述各项的英文括号变体
    """
    if not title:
        return ""
    import re
    t = title.strip()
    # 匹配各种括号包裹的短标注（括号内≤6个字符，或包含"试行"/"征求意见"/"修订"/"版"/"上册"/"下册"等关键词）
    # 括号的类型：中文（）、【】、英文()、[]
    patterns = [
        r'[（\(【\[]([^)）\]\]]{0,8}?(?:试行|征求意见|修订|版|上册|下册|第.{0,4}次)[^)）\]\]]{0,8})[）\)】\]]',
        r'[（\(【\[]([^)）\]\]]{0,6})[）\)】\]]',  # 通用短标注（≤6字）
    ]
    for pat in patterns:
        t = re.sub(pat, '', t)
    return t.strip()


def _title_similarity_level(t1, t2):
    """
    判断两个标题的相似度级别。
    【v2.14.0】新增标题相似度判断，解决"小差异 + 哈希相同 = 重复"与"大差异 + 哈希相同 = 非重复"的区分。

    返回值：
    - "identical": 标题完全相同
    - "small":      小差异（去括号后相同，或仅差一个短标注），哈希相同时视为重复
    - "large":      大差异（去括号后仍不同），哈希相同时为巧合碰撞，非重复
    - "none":       无法比较（某一方为空）
    """
    if not t1 or not t2:
        return "none"
    if t1 == t2:
        return "identical"

    s1 = _strip_title_suffix(t1)
    s2 = _strip_title_suffix(t2)

    # 去标注后相同 → 小差异
    if s1 and s2 and s1 == s2:
        return "small"

    # 计算编辑距离相似率（不依赖外部库）
    # 简单实现：最长公共子串比例
    def lcs_ratio(a, b):
        # 找到最长公共子串长度（朴素实现，适用于中文）
        m, n = len(a), len(b)
        if m == 0 or n == 0:
            return 0.0
        # 限制最大长度以避免性能问题（取前100字）
        a, b = a[:100], b[:100]
        m, n = len(a), len(b)
        # 简单的 LCS DP 表
        dp = [[0] * (n + 1) for _ in range(2)]
        max_len = 0
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if a[i-1] == b[j-1]:
                    dp[i % 2][j] = dp[(i-1) % 2][j-1] + 1
                    max_len = max(max_len, dp[i % 2][j])
                else:
                    dp[i % 2][j] = 0
        return max_len / max(m, n)

    ratio = lcs_ratio(s1, s2)
    # 若相似率 ≥ 0.75，认为是小的文字差异
    return "small" if ratio >= 0.75 else "large"


def check_duplicate_by_hash(extracted_json, index_data, current_title=None, current_date=None):
    """
    基于【标题 + 内容哈希】的综合去重。

    去重逻辑矩阵（v2.14.0 新版）：
    ┌──────────────────┬─────────────┬────────────┬──────────────────────────────────┐
    │ 标题关系          │ 哈希相同     │ 判定        │ 场景                              │
    ├──────────────────┼─────────────┼────────────┼──────────────────────────────────┤
    │ identical        │ ✅          │ 重复        │ 同一文件的不同格式               │
    │ small            │ ✅          │ 重复        │ 试行版vs正式版/不同年份版本       │
    │ large            │ ✅          │ 不重复      │ 大幅不同标题+哈希相同=巧合碰撞    │
    │ any              │ ❌          │ 不重复      │ 正常                              │
    └──────────────────┴─────────────┴────────────┴──────────────────────────────────┘

    【v2.14.0】标题关系细分：identical / small / large。
    - small: 标题去标注后相同（LCS相似率≥75%）
    - large: 标题差异大，即使哈希相同也视为非重复
    【v2.13.0】标题过滤作为第一道门槛：标题差异大则不进行哈希比对。

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

        # 【v2.14.0】第一道门槛：标题相似度必须为 identical 或 small，才继续比哈希
        doc_title = doc.get("title", "")
        sim = _title_similarity_level(current_title or "", doc_title or "")
        if sim in ("large", "none"):
            continue  # 标题差异大或某一方为空，不比哈希（避免哈希碰撞误判）

        p1_match = hashes["page1"] and stored.get("page1") == hashes["page1"]
        p2_match = hashes["page2"] and stored.get("page2") == hashes["page2"]

        if p1_match and p2_match:
            # 【v2.11.0】同名不同日期 → 不视为重复（新版本指导原则）
            doc_date = doc.get("issue_date")
            if current_date and doc_date and current_date != doc_date:
                continue  # 跳过，继续寻找真正的重复
            return True, doc  # 标题相同 + 两页文本均相同，判定为重复

    # 保底：PDF 字节哈希比对（全扫描文档，无可提取文本时）
    pdf_byte = hashes.get("pdf_byte")
    if pdf_byte:
        for doc in index_data.get("documents", []):
            stored = doc.get("content_hash", {})
            if stored is None or not isinstance(stored, dict):
                continue
            # 【v2.14.0】同样先检查标题相似度
            doc_title = doc.get("title", "")
            sim = _title_similarity_level(current_title or "", doc_title or "")
            if sim in ("large", "none"):
                continue
            if stored.get("pdf_byte") == pdf_byte:
                # 同样检查日期
                doc_date = doc.get("issue_date")
                if current_date and doc_date and current_date != doc_date:
                    continue
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
    
    # 【v2.11.0】智能跳过：JSON/MD 存在 且 源文件未更新（mtime）→ 跳过提取
    json_exists = os.path.exists(extracted_json)
    md_exists = os.path.exists(extracted_md)
    source_mtime = os.path.getmtime(raw_dest) if os.path.exists(raw_dest) else 0
    json_mtime = os.path.getmtime(extracted_json) if json_exists else 0
    skip_extraction = json_exists and md_exists and (source_mtime <= json_mtime)

    if skip_extraction:
        log(f"  → 提取文件已存在且源文件未更新，跳过 opendataloader", "⏭")
    else:
        if json_exists or md_exists:
            log(f"  → 重新提取（源文件有更新或部分文件缺失）", "🔄")
        else:
            log(f"  → 调用 opendataloader 提取内容...", "🔄")
        success, result = run_opendataloader(raw_dest, extracted_abs, skip_qwen=False, best_quality=True)
        if success:
            log(f"  → 内容提取完成", "✅")
        else:
            log(f"  → 提取失败: {result}", "⚠️")
    
    # 2.5 内容哈希去重检查（基于 PDF 正文第1+2页纯文本）
    # 【v2.11.0】新增：传入 current_title 和 current_date，用于过滤同名不同日期的合法版本
    if os.path.exists(extracted_json):
        is_dup, dup_doc = check_duplicate_by_hash(
            extracted_json, index_data,
            current_title=meta.get('title'),
            current_date=meta.get('issue_date')
        )
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

def _get_session_age_seconds(session_key_pattern):
    """
    从 openclaw sessions JSON 中查找匹配 session_key_pattern 的会话，
    返回其 ageMs（毫秒）。找不到返回 None。
    """
    try:
        result = subprocess.run(
            ["timeout", "5", "openclaw", "sessions", "--json"],
            capture_output=True, text=True, timeout=8
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        now_ms = datetime.now().timestamp() * 1000
        for s in data.get("sessions", []):
            key = s.get("key", "")
            if session_key_pattern in key:
                updated = s.get("updatedAt", 0)
                return (now_ms - updated) / 1000.0
        return None
    except Exception:
        return None


def trigger_graphify_hook(mode="rebuild"):
    """
    启动 graphify agent 并同步等待其完成。
    使用独立 session id 追踪进度，轮询 sessions 列表直到 agent 结束。
    最多等待 20 分钟，超时则放弃（batch 场景仍可继续）。

    v2.12.0: 修复 graphify 钩子从未自动完成的 bug。
    旧 bug 根因: openclaw agent --message 非阻塞，CLI 立即返回，
    但 agent 在 gateway 后台异步执行，原来的 nohup 路径无法追踪完成状态。
    修复：改用固定 session id + 线程轮询 age 直到 agent 结束。
    """
    import threading

    # 生成唯一 session label
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    session_label = f"gf-hook-{ts}"
    marker_file = f"/tmp/graphify_hook_{ts}.done"

    # 构建 prompt（扫描全量知识库，不再只扫"稳定性"子目录）
    if mode == "rebuild":
        prompt = (
            f"请对以下目录执行 graphify 全量重建（扫描全部子目录）：/graphify "
            f"/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库 "
            f"--mode deep。"
            f"完成后请汇报：节点数、边数、社区数。"
        )
        timeout_secs = 1200  # 20 分钟
    else:
        prompt = (
            f"请执行 graphify 增量更新（扫描全部子目录）：/graphify "
            f"/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库 "
            f"--update。完成后请汇报：节点数、边数。"
        )
        timeout_secs = 600  # 10 分钟

    log(f"Graphify 启动（session={session_label}，等待≤{timeout_secs//60}分钟）...", "🕸️")

    # 在后台线程启动 agent（不让 subprocess 阻塞主线程）
    log_file = f"/tmp/graphify_hook_{ts}.log"

    def run_agent():
        # nohup 方式：CLI 立即返回，agent 在 gateway 后台运行
        cmd = [
            "nohup", "openclaw", "agent",
            "--session-id", session_label,
            "--message", prompt,
            "--timeout", str(timeout_secs - 60),
        ]
        with open(log_file, "w") as f:
            proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
        proc.wait()  # 等待 CLI 返回（不等 agent 完成）

    thread = threading.Thread(target=run_agent, daemon=True)
    thread.start()

    # 等待 agent 在 gateway 完成：轮询 session 直到它出现且 age 稳定
    # 策略：session 出现后，等待 age > 30s（说明 agent 已处理完不再更新）
    POLL_INTERVAL = 30  # 每 30 秒轮询一次
    MAX_WAIT = timeout_secs
    start_time = time.time()
    session_found = False
    last_age = None

    while time.time() - start_time < MAX_WAIT:
        time.sleep(POLL_INTERVAL)
        age = _get_session_age_seconds(session_label)
        elapsed = time.time() - start_time

        if age is not None:
            session_found = True
            if age > 30:
                # age 超过 30s 不更新，说明 agent 已结束
                log(f"Graphify 完成（session age={age:.0f}s，耗时约{elapsed:.0f}s）✅", "🕸️")
                # 写完成标记
                with open(marker_file, "w") as f:
                    f.write(f"done\n")
                return True, f"完成，session age={age:.0f}s"
            else:
                log(f"Graphify 运行中（session age={age:.0f}s，elapsed={elapsed:.0f}s）...", "🕸️")
                last_age = age
        else:
            if session_found:
                # 之前找到过，现在找不到了 → 已结束
                log(f"Graphify 完成（session 已消失，耗时约{elapsed:.0f}s）✅", "🕸️")
                with open(marker_file, "w") as f:
                    f.write("done\n")
                return True, f"完成，session 已消失"

    # 超时
    log(f"Graphify 超时（>{MAX_WAIT//60}分钟），请手动检查图谱状态", "⚠️")
    return False, f"超时（>{MAX_WAIT//60}分钟）"

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
            if meta is None:
                continue
            cat_dir, guidance_subdir, rel_prefix = resolve_destination_dir(meta)
            scope = meta.get("scope", {})
            cat = scope.get("category", meta.get("category", "未知"))
            print(f"  [{cat}] {meta['title']}")
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
        index_data = load_index()
        print(f"  当前索引: {len(index_data['documents'])} 条记录")
        added = rebuild_index_from_disk(KB_ROOT, index_data)
        print(f"  磁盘恢复: {len(added)} 条新增")
        new_files = scan_for_new_files(SRC_SCAN_DIRS, set())
        print(f"  新增文件: {len(new_files)} 个")
    elif "--recover" in args:
        index_data = load_index()
        print(f"  当前索引: {len(index_data['documents'])} 条记录")
        added = rebuild_index_from_disk(KB_ROOT, index_data)
        print(f"  磁盘恢复: {len(added)} 条新增入库")
        save_index(index_data)
        print(f"  索引已保存（共 {len(index_data['documents'])} 条）")
        return
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
            index_data = load_index()  # 加载索引
        else:
            log(f"路径不存在: {input_path}", "❌")
            return
    else:
        log("执行增量检查", "🔍")
        index_data = load_index()
        indexed_ids = get_indexed_ids(index_data)
        new_files = scan_for_new_files(SRC_SCAN_DIRS, indexed_ids)
    
    if not new_files:
        log(f"没有发现新增文件，知识库已是最新", "✅")
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
        try:
            meta = process_new_file(f, index_data)
            processed.append(meta)
        except Exception as e:
            print(f"  ❌ 处理失败: {f['name']}，错误: {e}", file=sys.stderr)
            continue
        # 每处理1个文件保存一次（崩溃不丢进度）
        save_index(index_data)
        # 每处理10个文件输出进度
        if i % 10 == 0:
            print(f"\n💾 [进度] 已处理 {i}/{len(new_files)} 个文件", flush=True)

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