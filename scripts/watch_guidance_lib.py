#!/usr/bin/env python3
"""
版本: 2.10.0
功能: 法规指导原则知识库 watchdog 监控进程
      监控知识库根目录，自动触发 knowledge_base_manager.py 处理新文件

设计原则（v2.10.0）:
  - 不硬编码目录列表，监控 KB_ROOT 根目录本身
  - 自动感知所有新增的原始文件目录（不限于已知的分类）
  - 通过文件扩展名过滤，只处理 .pdf/.doc/.docx
  - 排除不需要监控的目录（graphify-out、供AI用信息、_images 等）

触发流程:
  检测到新文件 → 等待写入完成（防截断）→ 调用 knowledge_base_manager.py
"""

import os
import sys
import time
import subprocess
import threading
import logging
import atexit
import re
from pathlib import Path

# ============ 配置区 ============
KB_ROOT = "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库"
KB_MANAGER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base_manager.py")
PID_FILE = "/tmp/watch_guidance_lib.pid"
LOG_FILE = "/tmp/watch_guidance_lib.log"
WRITE_COMPLETE_WAIT = 3

# 不需要监控的目录名称（完全匹配）或前缀
EXCLUDE_DIR_NAMES = {
    "供AI用信息",     # 提取结果目录
    "原始文件",       # 监控时只关心原始文件，但保留此名以便将来区分
    "graphify-out",   # 图谱输出目录
    "jobs",           # 作业队列目录
    "参考模板",       # 参考模板目录
    "内部文件",       # 内部文件目录
    "_images",        # 图像缓存目录
    "_table_pages_render",  # 表格渲染缓存
}

# 以这些结尾的目录名也排除（处理临时目录）
EXCLUDE_DIR_ENDSWITH = ("_render", "_images", "_cache", "_temp")

def _should_watch_dir(dirname):
    """判断目录是否应该被监控（只监控原始文件归档目标）"""
    # 完全匹配排除
    if dirname in EXCLUDE_DIR_NAMES:
        return False
    # 后缀排除
    for suffix in EXCLUDE_DIR_ENDSWITH:
        if dirname.endswith(suffix):
            return False
    return True

# ==============================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("watch_guidance_lib")

processing_lock = threading.Lock()
processing_files = set()

# ---- 文件写入完成检测 ----

class FileWriteChecker:
    def __init__(self, path, timeout=30, interval=0.5):
        self.path = path
        self.timeout = timeout
        self.interval = interval
    
    def is_write_complete(self):
        try:
            if not os.path.exists(self.path):
                return False
            size1 = os.path.getsize(self.path)
            time.sleep(self.interval)
            size2 = os.path.getsize(self.path)
            return size1 == size2 and size1 > 0
        except Exception:
            return False
    
    def wait_for_complete(self):
        start = time.time()
        while time.time() - start < self.timeout:
            if self.is_write_complete():
                return True
            time.sleep(self.interval)
        log.warning(f"文件写入完成检测超时: {self.path}")
        return os.path.exists(self.path)


# ---- watchdog 事件处理 ----

SUPPORTED_EXTS = {".pdf", ".doc", ".docx"}

def _is_valid_raw_file(filepath):
    """判断是否是需要处理的原始文件"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in SUPPORTED_EXTS:
        return False
    # 跳过临时文件
    if filepath.endswith(".tmp") or filepath.endswith(".crdownload"):
        return False
    return True

def _get_watch_parent(filepath):
    """获取 filepath 所属的"原始文件"目录层级，返回 None 表示不监控"""
    # 原始文件的路径结构: KB_ROOT/分类/子目录/原始文件/文件名
    # 我们只监控原始文件目录本身，而非其父目录
    # 因此检测 filepath 是否在某个"原始文件"目录下
    parts = filepath.split(os.sep)
    try:
        raw_idx = parts.index("原始文件")
        # 返回原始文件目录的路径
        return os.sep.join(parts[:raw_idx + 1])
    except ValueError:
        return None

def on_file_created(event):
    if event.is_directory:
        return
    
    filepath = event.src_path
    if not _is_valid_raw_file(filepath):
        return
    
    parent_raw = _get_watch_parent(filepath)
    if parent_raw is None:
        # 文件不在原始文件目录下（如在供AI用信息/目录），跳过
        return
    
    log.info(f"检测到新文件: {filepath}")
    
    with processing_lock:
        if filepath in processing_files:
            log.info(f"文件正在处理中，跳过: {filepath}")
            return
        processing_files.add(filepath)
    
    try:
        checker = FileWriteChecker(filepath)
        if checker.wait_for_complete():
            log.info(f"文件写入完成，开始处理: {filepath}")
            trigger_kb_manager(filepath)
        else:
            log.warning(f"文件写入未完成，跳过: {filepath}")
    finally:
        with processing_lock:
            processing_files.discard(filepath)


def on_file_modified(event):
    if event.is_directory:
        return
    
    filepath = event.src_path
    if not _is_valid_raw_file(filepath):
        return
    
    parent_raw = _get_watch_parent(filepath)
    if parent_raw is None:
        return
    
    log.info(f"检测到文件更新: {filepath}")
    
    with processing_lock:
        if filepath in processing_files:
            return
        processing_files.add(filepath)
    
    try:
        checker = FileWriteChecker(filepath)
        if checker.wait_for_complete():
            log.info(f"文件更新完成，重新处理: {filepath}")
            trigger_kb_manager(filepath)
        else:
            log.warning(f"文件更新未完成，跳过: {filepath}")
    finally:
        with processing_lock:
            processing_files.discard(filepath)


def trigger_kb_manager(filepath):
    try:
        log.info(f"调用知识库管理器: {filepath}")
        result = subprocess.run(
            ["python3", KB_MANAGER_SCRIPT, filepath],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            log.info(f"知识库管理器处理成功: {filepath}")
            log.debug(result.stdout)
        else:
            log.error(f"知识库管理器处理失败: {result.stderr}")
    except subprocess.TimeoutExpired:
        log.error(f"知识库管理器处理超时: {filepath}")
    except Exception as e:
        log.error(f"调用知识库管理器异常: {e}")


# ---- 守护进程管理 ----

def write_pid(pid):
    with open(PID_FILE, "w") as f:
        f.write(str(pid))

def read_pid():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                return int(f.read().strip())
        except Exception:
            return None
    return None

def is_running(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def daemon_stop():
    pid = read_pid()
    if pid and is_running(pid):
        log.info(f"停止守护进程 PID={pid}")
        os.kill(pid, 15)
        time.sleep(1)
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        print("✅ 守护进程已停止")
    else:
        print("⚠️  未找到运行中的守护进程")


# ---- 启动监控 ----

def start_watching():
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    
    handler = FileSystemEventHandler()
    handler.on_created = on_file_created
    handler.on_modified = on_file_modified
    
    observer = Observer()
    
    # 监控 KB_ROOT 根目录（recursive=True）
    # _get_watch_parent 在事件处理时过滤，只处理原始文件目录下的文件
    observer.schedule(handler, KB_ROOT, recursive=True)
    
    observer.start()
    
    log.info(f"✅ 监控启动: {KB_ROOT}（recursive=True，自动感知所有新增目录）")
    log.info(f"📋 PID: {os.getpid()}")
    log.info(f"📋 日志: {LOG_FILE}")
    log.info("按 Ctrl+C 停止")
    
    atexit.register(lambda: observer.stop())
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("收到停止信号")
        observer.stop()
    observer.join()
    log.info("监控已停止")


def start_daemon():
    pid = os.fork()
    if pid > 0:
        print(f"✅ 守护进程已启动，PID={pid}")
        write_pid(pid)
        sys.exit(0)
    elif pid == 0:
        os.setsid()
        with open("/dev/null", "r") as devnull:
            os.dup2(devnull.fileno(), 0)
        with open(LOG_FILE, "a") as logf:
            os.dup2(logf.fileno(), 1)
            os.dup2(logf.fileno(), 2)
        start_watching()
    else:
        print("❌ fork 失败")
        sys.exit(1)


# ---- 主入口 ----

def main():
    if "--stop" in sys.argv:
        daemon_stop()
        return
    
    if "--daemon" in sys.argv:
        start_daemon()
    else:
        if not os.path.isdir(KB_ROOT):
            print(f"⚠️  知识库目录不存在: {KB_ROOT}")
            return
        start_watching()


if __name__ == "__main__":
    main()
