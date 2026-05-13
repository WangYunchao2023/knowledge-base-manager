#!/usr/bin/env python3
"""
版本: 3.2.0
功能: llm_semantic_batch_processor - 完全独立的自循环批处理器（加固版）
      自己生成 trigger → 自己处理 → 自己更新 progress，不依赖任何外部进程

架构（v3.2.0 VRAM协调）:
  - VRAM调度接入：每个batch前后调用vram_switcher的mark_busy/mark_done
    确保与KB_manager的qwen2.5vl互斥协调，不互相evict对方模型
  - 连续失败计数：连续失败3次停止盲目跳过，触发告警
  - Ollama 健康检查：每批前验证服务可用性
  - 写入验证：保存后读取确认文件完整性
  - 优雅退出：SIGTERM 收到后完成当前 batch 再退出
  - 看门狗：crontab 5分钟检查一次，进程死掉自动重启
  - 中断自检：启动时发现 last_run 超过 5 分钟则打印中断提示
  - auto-release 5分钟超时：5分钟无新任务自动释放14B显存

用法:
  python3 llm_semantic_batch_processor.py --daemon   # 后台守护进程
  python3 llm_semantic_batch_processor.py --once    # 单次处理一个 batch
  python3 llm_semantic_batch_processor.py --status  # 查看进度
"""

import json, os, time, signal, subprocess, sys
from pathlib import Path
from datetime import datetime

# VRAM 调度（必须先于任何模型调用）
sys.path.insert(0, '/home/wangyc/.openclaw/scripts')
from vram_switcher import VSwitcher

# ============ 配置区 ============
KB_ROOT = "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库"
GRAPHIFY_OUT = os.path.join(KB_ROOT, "graphify-out")
PROGRESS_FILE = os.path.join(GRAPHIFY_OUT, "llm_semantic_progress.json")
OUTPUT_FILE = os.path.join(GRAPHIFY_OUT, "llm_semantic_edges.json")
BATCHES_FILE = os.path.join(GRAPHIFY_OUT, "llm_batch_queue", "batches.json")
INDEX_FILE = os.path.join(KB_ROOT, "guidance_index.json")
OLLAMA_MODEL = "qwen2.5:14b"          # 本地模型（qwen2.5:14b）
OLLAMA_API = "http://localhost:11434/api/generate"
POLL_INTERVAL = 30                      # 轮询间隔（秒）
MAX_CONSECUTIVE_FAILS = 3               # 连续失败超过此数则停止（防污染）
HEALTH_CHECK_INTERVAL = 5               # Ollama 健康检查间隔（批次数）
LOG_MAX_LINES = 2000                    # 日志最大行数，超出截断
# ==============================

# 全局状态
running = True
consecutive_fails = 0
batches_since_health_check = 0

# VRAM 调度器单例（daemon 生命周期内复用）
_vram = VSwitcher()

PROMPT_TEMPLATE = """## 任务：判断以下{n}对药品监管文档是否具有真实的监管语义关联

{docs_info}

## 待判断的{n}对：
{batch_lines}

## 判断标准（满足任一即为"有关联"，否则为"无关联"）：
- 有关联：①条款引用/对应关系；②同一监管概念的细化版与通用版；③同一品种/剂型/适应症的研发路径互补
- 无关联：仅共享通用术语（如"安全性研究"、"质量标准"）但实际监管要求无交集，或适用范围完全不同

## 输出格式（严格每对一行，不要任何其他文字）：
RESULT|序号|有关联/无关联|理由（10字内）

例如：
RESULT|1|无关联|适用完全不同
RESULT|2|有关联|同属注射剂"""

def log(msg, emoji="🤖"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{emoji} {ts} {msg}", flush=True)

def log_rotate(log_path, max_lines):
    """日志轮转：超出最大行数则截断前 N 行"""
    if not os.path.exists(log_path):
        return
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if len(lines) > max_lines:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"# 截断于 {datetime.now().isoformat()}，保留最近 {max_lines} 行\n")
            f.writelines(lines[-max_lines:])

LOG_FILE = "/tmp/llm_semantic_batch_processor.log"

def log_safe(msg, emoji="🤖"):
    """带日志轮转的写入"""
    log(msg, emoji)
    log_rotate(LOG_FILE, LOG_MAX_LINES)

def load_index():
    if os.path.exists(INDEX_FILE):
        return {d["id"]: d for d in json.load(open(INDEX_FILE)).get("documents", [])}
    return {}

def load_batches():
    with open(BATCHES_FILE, encoding="utf-8") as f:
        return json.load(f)

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        return json.load(open(PROGRESS_FILE))
    return {"total_batches": 0, "completed_batches": 0, "pending_batch_idx": 0}

def save_progress(data):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def check_ollama_health():
    """健康检查：验证 Ollama 服务可用"""
    try:
        result = subprocess.run(
            ["curl", "-s", "-m", "5", f"{OLLAMA_API.replace('/api/generate','')}/api/tags"],
            capture_output=True, text=True, timeout=6
        )
        if result.returncode == 0:
            d = json.loads(result.stdout)
            models = [m["name"] for m in d.get("models", [])]
            if OLLAMA_MODEL in models:
                return True, "healthy"
            return False, f"model {OLLAMA_MODEL} not found, available: {models}"
        return False, f"health check failed: {result.returncode}"
    except Exception as e:
        return False, str(e)

def call_ollama(prompt, timeout=90):
    """调用 Ollama qwen2.5:14b，返回原始文本"""
    try:
        result = subprocess.run(
            ["curl", "-s", OLLAMA_API,
             "-d", json.dumps({
                 "model": OLLAMA_MODEL,
                 "prompt": prompt,
                 "stream": False,
                 "options": {"temperature": 0.1, "num_predict": 600}
             })],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            return None, f"curl failed: {result.stderr[:100]}"
        d = json.loads(result.stdout)
        if "error" in d:
            return None, f"ollama error: {d['error']}"
        return d.get("response", "").strip(), None
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except Exception as e:
        return None, str(e)

def parse_results(text, batch_edges):
    """从 LLM 输出中提取 RESULT|xxx 行"""
    lines = [l.strip() for l in text.split("\n") if l.strip().startswith("RESULT|")]
    results = []
    for line in lines:
        parts = line.split("|")
        if len(parts) < 4 or parts[0] != "RESULT":
            continue
        try:
            idx = int(parts[1]) - 1
            if 0 <= idx < len(batch_edges):
                edge = batch_edges[idx].copy()
                edge["llm_decision"] = "有关联" if parts[2] == "有关联" else "无关联"
                edge["llm_reason"] = parts[3].strip()[:50]
                edge["llm_confidence"] = 1.0
                edge["relation_type"] = "llm_semantic_verified"
                edge["llm_batch_time"] = datetime.now().isoformat()
                results.append(edge)
        except (ValueError, IndexError):
            continue
    return results

def verify_write(path, expected_keys=None):
    """写入验证：保存后读取确认文件完整"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if expected_keys:
            for k in expected_keys:
                if k not in data:
                    return False, f"missing key: {k}"
        return True, "verified"
    except Exception as e:
        return False, f"verify failed: {e}"

def process_one_batch():
    """处理一个 batch"""
    global consecutive_fails, batches_since_health_check, running

    if not running:
        return False

    # 健康检查（每 HEALTH_CHECK_INTERVAL 批检查一次）
    if batches_since_health_check >= HEALTH_CHECK_INTERVAL:
        ok, msg = check_ollama_health()
        if not ok:
            log_safe(f"⚠️ Ollama 健康检查失败: {msg}，等待 30s 重试", "🏥")
            time.sleep(30)
            ok, _ = check_ollama_health()
            if not ok:
                log_safe(f"❌ Ollama 不可用，暂停处理", "🚫")
                time.sleep(60)
                return True  # 继续循环重试
        batches_since_health_check = 0

    batches_since_health_check += 1

    batches = load_batches()
    progress = load_progress()
    completed = progress.get("completed_batches", 0)
    total = len(batches)

    if completed >= total:
        log_safe(f"全部完成: {completed}/{total}", "✅")
        save_progress({"state": "completed", "total_batches": total, "completed_batches": completed})
        return False

    batch = batches[completed]
    batch_idx = completed
    batch_edges = batch.get("edges", [])
    doc_map = load_index()

    # 构建文档信息
    doc_ids = list(set(e["source"] for e in batch_edges) | set(e["target"] for e in batch_edges))
    docs_info_lines = []
    for did in doc_ids:
        info = doc_map.get(did, {})
        title = info.get("title", did)[:40]
        cat = info.get("scope", {}).get("category", "?")
        docs_info_lines.append(f"{len(docs_info_lines)+1}. {title} [{cat}]")

    docs_info = "\n".join(docs_info_lines)
    batch_lines = "\n".join(
        f"{j+1}|{e['source']}|{e['target']}|共享: {','.join(e['shared_concepts'][:5])}"
        for j, e in enumerate(batch_edges)
    )

    prompt = PROMPT_TEMPLATE.format(n=len(batch_edges), docs_info=docs_info, batch_lines=batch_lines)
    log_safe(f"处理 batch {batch_idx+1}/{total}，{len(batch_edges)} 对...", "📋")

    # VRAM: 告诉调度器"我在用"，取消 auto-release 计时
    _vram.mark_busy()
    try:
        response, err = call_ollama(prompt)
    finally:
        _vram.mark_done()  # 重置 auto-release 计时
    if err:
        consecutive_fails += 1
        log_safe(f"❌ LLM 调用失败 ({consecutive_fails}/{MAX_CONSECUTIVE_FAILS}): {err}", "❌")
        if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
            log_safe(f"🚨 连续失败 {consecutive_fails} 次，暂停处理等待人工介入", "🚨")
            save_progress({
                **progress,
                "state": "paused",
                "pause_reason": f"consecutive_llm_fails:{err}",
                "pause_time": datetime.now().isoformat(),
                "last_run": datetime.now().isoformat()
            })
            time.sleep(300)  # 5分钟后重试
            consecutive_fails = 0  # 重置计数
            return True
        # 未达阈值，仍推进进度（避免卡死）
        progress["completed_batches"] = completed + 1
        progress["pending_batch_idx"] = completed + 1
        progress["state"] = "running"
        progress["last_run"] = datetime.now().isoformat()
        save_progress(progress)
        return True

    # LLM 调用成功，重置失败计数
    consecutive_fails = 0

    # 解析结果
    new_edges = parse_results(response, batch_edges)
    log_safe(f"  → 解析到 {len(new_edges)} 条边 | 原始输出: {response[:100]}...", "📊")

    if not new_edges:
        log_safe(f"  ⚠️ 未解析到结果，用无关联填充", "⚠️")
        new_edges = []
        for i, edge in enumerate(batch_edges):
            e = edge.copy()
            e["llm_decision"] = "无关联"
            e["llm_reason"] = "解析失败"
            e["llm_confidence"] = 0.3
            e["relation_type"] = "llm_semantic_verified"
            e["llm_batch_time"] = datetime.now().isoformat()
            new_edges.append(e)

    # 追加到 edges 文件
    if os.path.exists(OUTPUT_FILE):
        data = json.load(open(OUTPUT_FILE))
    else:
        data = {"version": "3.2.0", "generated_at": datetime.now().isoformat(),
                "model": OLLAMA_MODEL, "edges": [], "total_edges": 0,
                "related_count": 0, "not_related_count": 0, "batches_completed": 0}

    existing_keys = {(e["source"], e["target"]) for e in data.get("edges", [])}
    related = data.get("related_count", 0)
    not_related = data.get("not_related_count", 0)
    added = 0

    for edge in new_edges:
        key = (edge["source"], edge["target"])
        if key not in existing_keys:
            data["edges"].append(edge)
            existing_keys.add(key)
            added += 1
            if edge.get("llm_decision") == "有关联":
                related += 1
            else:
                not_related += 1

    data["total_edges"] = len(data["edges"])
    data["related_count"] = related
    data["not_related_count"] = not_related
    data["batches_completed"] = batch_idx + 1
    data["last_updated"] = datetime.now().isoformat()

    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 写入验证
    ok, msg = verify_write(OUTPUT_FILE, ["edges", "total_edges", "related_count", "not_related_count"])
    if not ok:
        log_safe(f"⚠️ edges 文件写入验证失败: {msg}，重新保存", "⚠️")
        with open(OUTPUT_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    log_safe(f"  ✅ edges: +{added} 条 (共 {data['total_edges']} 条, {related} 有关联, {not_related} 无关联)", "📈")

    # 更新 progress
    progress["completed_batches"] = batch_idx + 1
    progress["pending_batch_idx"] = batch_idx + 1
    progress["total_batches"] = total
    progress["state"] = "running"
    progress["last_run"] = datetime.now().isoformat()
    progress["consecutive_fails"] = consecutive_fails
    save_progress(progress)

    return True

def shutdown_handler(signum, frame):
    """优雅退出：完成当前 batch 再退出"""
    global running
    log_safe(f"收到退出信号 (SIGTERM/SIGINT)，完成当前 batch 后退出...", "🛑")
    running = False

def daemon():
    """守护进程主循环"""
    global running

    # 注册信号处理
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    log_safe(f"🚀 启动自循环批处理器 v3.2（{OLLAMA_MODEL}，每 {POLL_INTERVAL}s）", "🚀")
    total = len(load_batches())
    log_safe(f"总批次: {total}，已完成: {load_progress().get('completed_batches', 0)}", "📊")

    # 启动时加载模型到 VRAM（确保 14B 常驻）
    _vram.load(OLLAMA_MODEL)


    # 启动时健康检查
    ok, msg = check_ollama_health()
    if ok:
        log_safe(f"✅ Ollama 健康检查通过 ({OLLAMA_MODEL})", "🏥")
    else:
        log_safe(f"⚠️ Ollama 启动健康检查: {msg}，继续启动", "🏥")

    # 启动时检查上次运行时间，如果超过 5 分钟未更新说明曾中断
    progress = load_progress()
    last_run_str = progress.get("last_run", "")
    if last_run_str and progress.get("state") == "running":
        try:
            last_run_dt = datetime.fromisoformat(last_run_str)
            elapsed = (datetime.now() - last_run_dt).total_seconds()
            if elapsed > 300:
                log_safe(f"检测到中断（上次运行 {int(elapsed)} 秒前），自动从 batch {progress.get('completed_batches',0)} 继续", "🔄")
        except Exception:
            pass

    while running:
        try:
            progress = load_progress()
            completed = progress.get("completed_batches", 0)
            state = progress.get("state", "running")

            # 暂停状态：每5分钟检查一次是否恢复
            if state == "paused":
                log_safe(f"⚠️ 处于暂停状态，等待恢复...", "⏸")
                time.sleep(300)
                progress = load_progress()
                if progress.get("state") != "running":
                    continue
                log_safe(f"✅ 状态已恢复，继续处理", "▶")
                global consecutive_fails
                consecutive_fails = 0

            if completed >= total:
                log_safe(f"全部完成！({total}/{total})", "🎉")
                break

            has_more = process_one_batch()
            if not has_more:
                break

            if running:
                time.sleep(POLL_INTERVAL)

        except Exception as e:
            log_safe(f"异常: {e}，10秒后重试", "❌")
            import traceback
            traceback.print_exc()
            time.sleep(10)

    log_safe(f"守护进程退出（completed={load_progress().get('completed_batches',0)}）", "👋")

def once():
    """单次模式：处理一个 batch"""
    global consecutive_fails, batches_since_health_check
    batches_since_health_check = HEALTH_CHECK_INTERVAL  # 强制健康检查
    progress = load_progress()
    completed = progress.get("completed_batches", 0)
    total = len(load_batches())
    log(f"batch {completed+1}/{total}", "📋")
    process_one_batch()

def status():
    progress = load_progress()
    total = len(load_batches())
    completed = progress.get("completed_batches", 0)
    pct = f"{completed*100//total}%" if total > 0 else "?"
    state = progress.get("state", "?")
    print(f"进度: {completed}/{total} ({pct})")
    print(f"状态: {state}")
    print(f"连续失败: {progress.get('consecutive_fails', 0)}/{MAX_CONSECUTIVE_FAILS}")
    print(f"最后运行: {progress.get('last_run', '?')}")
    if progress.get("pause_reason"):
        print(f"暂停原因: {progress.get('pause_reason')}")
    if os.path.exists(OUTPUT_FILE):
        d = json.load(open(OUTPUT_FILE))
        print(f"edges: {d.get('total_edges', '?')} 条, 有关联: {d.get('related_count', '?')}, 无关联: {d.get('not_related_count', '?')}")
    ok, _ = check_ollama_health()
    print(f"Ollama: {'✅ 可用' if ok else '❌ 不可用'}")

if __name__ == "__main__":
    if "--status" in sys.argv:
        status()
    elif "--once" in sys.argv:
        once()
    else:
        daemon()