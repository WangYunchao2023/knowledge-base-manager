#!/usr/bin/env python3
"""
版本: 2.8.0
功能: Graphify 图谱对接模块
      通过 OpenClaw Agent 执行 /graphify skill 流程，构建法规库知识图谱
      支持多分类目录（化学药/中药/生物制品/通用）统一建图

工作原理:
  graphify CLI 只有查询功能，真正的图谱构建靠 AI Agent 执行 SKILL.md 步骤。
  本模块通过 sessions_spawn 启动 subagent → 执行 /graphify 完整流程 → 输出 graph.json

用法:
  python graphify_integration.py --rebuild        # 全量重建图谱（通过 subagent）
  python graphify_integration.py --incremental    # 增量更新（通过 subagent）
  python graphify_integration.py --summary        # 查看图谱摘要
  python graphify_integration.py --query "xxx"   # 查询（直接调 graphify CLI）

知识库管理器调用:
  python knowledge_base_manager.py --trigger-hook graphify

输出:
  graphify-out/graph.json     → Cortana 直接读取做语义推理
  graphify-out/GRAPH_REPORT.md → 图谱审计报告
"""

import os
import sys
import json
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

# ============ 配置区 ============
KB_ROOT = "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库"
GRAPHIFY_OUTPUT = os.path.join(KB_ROOT, "graphify-out")
GRAPHIFY_INDEX = os.path.join(GRAPHIFY_OUTPUT, "graph_index.json")
GRAPHIFY_GRAPH_JSON = os.path.join(GRAPHIFY_OUTPUT, "graph.json")

# 扫描所有分类目录（兼容新旧结构）
CATEGORY_SUBDIRS = ["化学药", "中药", "生物制品", "通用"]

def get_all_extracted_dirs():
    """获取所有含有供AI用信息的目录（遍历所有分类下的所有二级子目录）"""
    dirs = []
    for cat in CATEGORY_SUBDIRS:
        cat_path = os.path.join(KB_ROOT, cat)
        if not os.path.isdir(cat_path):
            continue
        for subdir in os.listdir(cat_path):
            p = os.path.join(cat_path, subdir, "供AI用信息")
            if os.path.isdir(p) and p not in dirs:
                dirs.append(p)
    # 旧结构兼容：如果稳定性/供AI用信息 不在上述结果中（文件仍在旧位置）
    old = os.path.join(KB_ROOT, "稳定性", "供AI用信息")
    if os.path.isdir(old) and old not in dirs:
        dirs.append(old)
    return dirs

# 默认 target 用于 /graphify 命令
# 指向 KB_ROOT 以扫描全部子目录（而非只扫"稳定性"一个子目录）
ALL_EXTRACTED_DIRS = get_all_extracted_dirs()
GRAPHIFY_TARGET = KB_ROOT  # 全量扫描
# ==============================

def log(msg, emoji="🕸️"):
    print(f"{emoji} {msg}")

def ensure_dirs():
    os.makedirs(GRAPHIFY_OUTPUT, exist_ok=True)

def load_graph_index():
    if os.path.exists(GRAPHIFY_INDEX):
        with open(GRAPHIFY_INDEX, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "version": "1.0",
        "last_full_rebuild": "",
        "last_incremental": "",
        "last_failed": "",
        "total_nodes": 0,
        "total_edges": 0,
        "files_processed": [],
        "method": ""
    }

def save_graph_index(idx):
    with open(GRAPHIFY_INDEX, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)

def get_all_md_files():
    """获取所有分类目录下的 .md 文件"""
    all_files = []
    for d in ALL_EXTRACTED_DIRS:
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.endswith(".md"):
                    all_files.append(os.path.join(d, f))
    return all_files

def spawn_graphify_agent(mode="full"):
    """
    通过 sessions_spawn 启动 subagent 执行 /graphify 流程。
    graphify SKILL.md 会让 AI 按步骤：
      1. detect 文件
      2. 提取实体+关系
      3. 建图 + 聚类
      4. 输出 graph.json + GRAPH_REPORT.md
    """
    mode_desc = "全量重建" if mode == "full" else "增量更新"
    
    log(f"启动 subagent 执行 /graphify（{mode_desc}）...", "⚡")
    log(f"扫描目录: {ALL_EXTRACTED_DIRS}", "📁")
    
    # 注意：/graphify 命令只接受单一路径，传入第一个目录（其余作为辅助）
    mode_flag = " --mode deep" if mode == "full" else " --update"
    
    log(f"提示：graphify 图谱构建需要 AI Agent 执行。", "💡")
    log(f"请在 OpenClaw 对话框中输入以下命令：", "📋")
    print()
    print(f"  /graphify {GRAPHIFY_TARGET}{mode_flag}")
    print()
    log(f"或者让 Cortana 执行 /graphify {GRAPHIFY_TARGET}", "💡")
    
    return False, "需要通过 OpenClaw Agent 界面执行 /graphify 命令"


def run_graphify_cli_query(query_text):
    """直接调用 graphify CLI 查询"""
    graphify_bin = os.path.join(os.path.expanduser("~"), ".local", "bin", "graphify")
    
    if not os.path.exists(GRAPHIFY_GRAPH_JSON):
        return None, "graph.json 不存在，请先构建图谱（/graphify " + GRAPHIFY_TARGET + "）"
    
    cmd = [graphify_bin, "query", query_text, "--graph", GRAPHIFY_GRAPH_JSON]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, result.stdout
        return False, result.stderr
    except Exception as e:
        return False, str(e)


def full_rebuild():
    """全量重建"""
    log("开始全量重建图谱（通过 OpenClaw Agent）...", "🔨")
    ensure_dirs()
    
    idx = load_graph_index()
    
    md_files = get_all_md_files()
    log(f"发现 {len(md_files)} 个 .md 文件", "📄")
    log(f"扫描目录: {ALL_EXTRACTED_DIRS}", "📁")
    print()
    
    success, msg = spawn_graphify_agent(mode="full")
    
    if success:
        idx["method"] = "subagent"
        idx["last_full_rebuild"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_graph_index(idx)
        log(f"✅ 图谱构建完成", "✅")
    else:
        idx["method"] = "subagent"
        idx["last_failed"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_graph_index(idx)
        log(f"⚠️  需要手动执行: /graphify {GRAPHIFY_TARGET}", "📋")
    
    return success, msg


def incremental_update():
    """增量更新"""
    log("增量更新图谱（通过 OpenClaw Agent）...", "🔄")
    ensure_dirs()
    success, msg = spawn_graphify_agent(mode="update")
    return success, msg


def print_summary():
    """打印图谱摘要"""
    idx = load_graph_index()
    
    if os.path.exists(GRAPHIFY_GRAPH_JSON):
        try:
            with open(GRAPHIFY_GRAPH_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            nodes = data.get("nodes", [])
            edges = data.get("links", data.get("edges", []))
            
            print("=" * 50)
            print("🕸️  Graphify 图谱摘要")
            print("=" * 50)
            print(f"图谱文件: {GRAPHIFY_GRAPH_JSON}")
            print(f"总节点数: {len(nodes)}")
            print(f"总边数:   {len(edges)}")
            print(f"构建方式: {idx.get('method', '未知')}")
            print(f"最后全量重建: {idx.get('last_full_rebuild', '从未')}")
            print(f"最后增量更新: {idx.get('last_incremental', '从未')}")
            print()
            print(f"覆盖分类目录:")
            for d in ALL_EXTRACTED_DIRS:
                files = [f for f in os.listdir(d) if f.endswith('.md')] if os.path.isdir(d) else []
                print(f"  {d}: {len(files)} 个 .md")
            print("=" * 50)
            return
        except Exception as e:
            print(f"⚠️  图谱文件读取失败: {e}")
    
    print("=" * 50)
    print("🕸️  Graphify 图谱摘要")
    print("=" * 50)
    print(f"⚠️  图谱尚未构建")
    print()
    print(f"覆盖分类目录:")
    for d in ALL_EXTRACTED_DIRS:
        files = [f for f in os.listdir(d)] if os.path.isdir(d) else []
        print(f"  {d}: {len(files)} 个文件")
    print()
    print(f"构建方式：通过 OpenClaw Agent 执行 /graphify 命令")
    print(f"命令: /graphify {GRAPHIFY_TARGET}")
    print()
    print(f"请在 OpenClaw 对话框中输入: /graphify {GRAPHIFY_TARGET}")
    print("=" * 50)


# ---- Cortana 检索接口 ----

def query_graph(query_text):
    """
    对图谱执行语义查询（供 Cortana 调用）
    """
    ok, msg = run_graphify_cli_query(query_text)
    if ok:
        return {"source": "graphify_cli", "result": msg}
    
    if not os.path.exists(GRAPHIFY_GRAPH_JSON):
        return {
            "source": "none",
            "error": "图谱不存在",
            "suggestion": f"请先执行 /graphify {GRAPHIFY_TARGET} 构建图谱"
        }
    
    try:
        with open(GRAPHIFY_GRAPH_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        nodes = data.get("nodes", [])
        edges = data.get("links", data.get("edges", []))
        
        query_lower = query_text.lower()
        matched = [n for n in nodes if query_lower in n.get("label", "").lower()]
        
        return {
            "source": "json_fallback",
            "query": query_text,
            "matched_count": len(matched),
            "matched_nodes": matched[:10],
            "total_nodes": len(nodes),
            "total_edges": len(edges)
        }
    except Exception as e:
        return {"source": "error", "error": str(e)}


# ---- 主入口 ----

def main():
    parser = argparse.ArgumentParser(description="Graphify 图谱对接模块 v3.0")
    parser.add_argument("--rebuild", action="store_true", help="全量重建图谱（通过 OpenClaw Agent）")
    parser.add_argument("--incremental", action="store_true", help="增量更新（通过 OpenClaw Agent）")
    parser.add_argument("--summary", action="store_true", help="打印图谱摘要")
    parser.add_argument("--query", type=str, help="查询图谱（直接调 CLI）")
    args = parser.parse_args()
    
    print("🕸️  Graphify 图谱对接模块 v3.0.0")
    print()
    
    if args.summary:
        print_summary()
    elif args.rebuild:
        success, msg = full_rebuild()
        if not success:
            print(f"\n{msg}")
    elif args.incremental:
        success, msg = incremental_update()
        if not success:
            print(f"\n{msg}")
    elif args.query:
        result = query_graph(args.query)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_summary()
        print()
        print("用法:")
        print("  --rebuild      全量重建图谱")
        print("  --incremental  增量更新")
        print("  --summary      查看摘要")
        print("  --query \"...\"  查询")


if __name__ == "__main__":
    main()