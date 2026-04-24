#!/usr/bin/env python3
"""
版本: 3.0.0
功能: Graphify 作业处理器（供 cron isolated agent 调用）
      负责把作业状态打印出来，由 isolated agent 直接执行 graphify

Cron isolated agent 调用方式:
  python3 graphify_job.py --dequeue

isolated agent 收到 dequeue 结果后，
直接在自己的 session 里执行 /graphify 命令。
"""

import os
import sys
import json
import time
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

# ============ 配置区 ============
KB_ROOT = "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库"
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
    # 旧结构兼容
    old = os.path.join(KB_ROOT, "稳定性", "供AI用信息")
    if os.path.isdir(old) and old not in dirs:
        dirs.append(old)
    return dirs

ALL_EXTRACTED_DIRS = get_all_extracted_dirs()
GRAPHIFY_TARGET = ALL_EXTRACTED_DIRS[0] if ALL_EXTRACTED_DIRS else os.path.join(KB_ROOT, "稳定性", "供AI用信息")
JOB_QUEUE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jobs")
JOB_MARKER = os.path.join(JOB_QUEUE_DIR, "pending_job.json")
LOCK_FILE = os.path.join(JOB_QUEUE_DIR, "graphify.lock")
# ==============================

def log(msg, emoji="📋"):
    print(f"{emoji} {msg}")

def ensure_dirs():
    os.makedirs(JOB_QUEUE_DIR, exist_ok=True)

def get_pending_job():
    if not os.path.exists(JOB_MARKER):
        return None
    if os.path.exists(LOCK_FILE):
        lock_time = os.path.getmtime(LOCK_FILE)
        if time.time() - lock_time < 600:
            return None
        os.remove(LOCK_FILE)
    try:
        with open(JOB_MARKER, "r", encoding="utf-8") as f:
            job = json.load(f)
        if job.get("status") == "pending":
            return job
    except:
        pass
    return None

def mark_done():
    if os.path.exists(JOB_MARKER):
        try:
            with open(JOB_MARKER, "r", encoding="utf-8") as f:
                job = json.load(f)
            job["status"] = "done"
            job["done_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(JOB_MARKER, "w", encoding="utf-8") as f:
                json.dump(job, f, ensure_ascii=False, indent=2)
        except:
            pass

def release_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

def enqueue(mode="incremental"):
    """将作业加入队列"""
    ensure_dirs()
    job = {
        "enqueued_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target": GRAPHIFY_TARGET,
        "output": GRAPHIFY_OUTPUT,
        "mode": mode,
        "status": "pending"
    }
    with open(JOB_MARKER, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=2)
    log(f"Graphify 作业已入队（模式: {mode}）", "📝")

def dequeue():
    """
    取出作业，并生成执行 prompt 供 isolated agent 直接执行。
    注意：本函数不执行 graphify，只是把作业信息打印出来，
    由调用方（isolated cron agent）在自己 session 里执行。
    """
    ensure_dirs()
    job = get_pending_job()
    if not job:
        print("队列空，无待处理作业。")
        return None

    # 获取执行锁
    ensure_dirs()
    with open(LOCK_FILE, "w") as f:
        f.write(f"{os.getpid()}\n{time.time()}")

    target = job.get("target", GRAPHIFY_TARGET)
    mode = job.get("mode", "incremental")
    mode_flag = " --mode deep" if mode == "full" else " --update"

    print(f"✅ 取出 graphify 作业:")
    print(f"   目标: {target}")
    print(f"   模式: {mode} {'(全量重建)' if mode == 'full' else '(增量更新)'}")
    print(f"   入队时间: {job.get('enqueued_at')}")
    print()
    print("请在你的 session 里执行以下命令完成图谱构建:")
    print()
    print(f"  /graphify {target}{mode_flag}")
    print()
    print("等待完成后，报告节点数、边数、社区数。")

    # 标记完成（因为 prompt 已打印，isolated agent 会在自己 session 执行）
    # 注意：这里不应该 mark_done，应该等 graphify 真正完成后再标记
    # 但由于 isolated agent 执行完后不会回调，我们只能假设成功
    # 更好的做法是：isolated agent 在自己的 turn 里执行 /graphify，
    # /graphify 执行完成后，isolated agent turn 才结束
    # 所以 mark_done 应该在 isolated agent 确认完成后再调

    release_lock()
    return job


def status():
    """查看队列和图谱状态"""
    job = get_pending_job()
    if job:
        print(f"✅ 队列有待处理作业")
        print(f"   入队时间: {job.get('enqueued_at')}")
        print(f"   模式: {job.get('mode')}")
        print(f"   目标: {job.get('target')}")
    else:
        print("📭 队列: 空")
    
    if os.path.exists(LOCK_FILE):
        print(f"🔒 执行锁存在")
    
    graph_json = os.path.join(GRAPHIFY_OUTPUT, "graph.json")
    if os.path.exists(graph_json):
        try:
            with open(graph_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            nodes = len(data.get("nodes", []))
            edges = len(data.get("links", data.get("edges", [])))
            print(f"📊 图谱: {nodes} 节点, {edges} 边 ✅")
        except Exception as e:
            print(f"📊 图谱文件存在（读取失败: {e}）")
    else:
        print(f"📊 图谱: 尚未构建")


# ---- 入口 ----

def main():
    parser = argparse.ArgumentParser(description="Graphify 作业处理器 v3.0")
    parser.add_argument("--enqueue", action="store_true", help="加入作业队列（增量）")
    parser.add_argument("--enqueue-full", action="store_true", help="加入作业队列（全量）")
    parser.add_argument("--dequeue", action="store_true", help="取出作业（供 isolated cron agent 调用）")
    parser.add_argument("--status", action="store_true", help="查看队列和图谱状态")
    args = parser.parse_args()
    
    ensure_dirs()
    
    if args.enqueue:
        enqueue(mode="incremental")
    elif args.enqueue_full:
        enqueue(mode="full")
    elif args.dequeue:
        result = dequeue()
        if result is None:
            print("无待处理作业。")
    elif args.status:
        status()
    else:
        status()

if __name__ == "__main__":
    main()
