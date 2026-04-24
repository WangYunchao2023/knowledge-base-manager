#!/usr/bin/env python3
"""
版本: 3.0.0
功能: 法规指导原则知识库 watchdog 监控进程
      监控原始文件目录，自动触发 knowledge_base_manager.py 处理新文件

用法:
  python watch_guidance_lib.py              # 启动监控（前台）
  python watch_guidance_lib.py --daemon    # 启动监控（后台守护进程）
  python watch_guidance_lib.py --stop      # 停止守护进程

监控目录:
  /home/wangyc/Documents/工作/0 库/法规指导原则规定知识库/稳定性/
  （只监控此目录下的新 PDF/DOCX 文件）

触发流程:
  检测到新文件 → 等待写入完成（防截断）→ 调用 knowledge_base_manager.py --trigger-hook graphify
"""

import os
import sys
import time
import subprocess
import threading
import logging
import atexit
from pathlib import Path

# ============ 配置区 ============
WATCH_DIR = "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库/稳定性"
KB_MANAGER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base_manager.py")
PID_FILE = "/tmp/watch_guidance_lib.pid"
LOG_FILE = "/tmp/watch_guidance_lib.log"
# 写入完成后等待秒数（防文件截断）
WRITE_COMPLETE_WAIT = 3
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

# ---- 文件写入完成检测 ----

class FileWriteChecker:
    """检测文件是否已写入完成（通过文件大小稳定）"""
    def __init__(self, path, timeout=30, interval=0.5):
        self.path = path
        self.timeout = timeout
        self.interval = interval
    
    def is_write_complete(self):
        """文件大小连续两次不变则认为写完"""
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
        """等待文件写入完成"""
        start = time.time()
        while time.time() - start < self.timeout:
            if self.is_write_complete():
                return True
            time.sleep(self.interval)
        log.warning(f"文件写入完成检测超时: {self.path}")
        return os.path.exists(self.path)


# ---- watchdog 事件处理 ----

SUPPORTED_EXTS = {".pdf", ".doc", ".docx"}

# 全局锁，防止并发处理同一文件
processing_lock = threading.Lock()
processing_files = set()

def on_file_created(event):
    """新文件创建事件"""
    if event.is_directory:
        return
    
    filepath = event.src_path
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in SUPPORTED_EXTS:
        return
    
    # 跳过临时文件
    if filepath.endswith(".tmp") or filepath.endswith(".crdownload"):
        return
    
    log.info(f"检测到新文件: {filepath}")
    
    # 检查是否已在处理中
    with processing_lock:
        if filepath in processing_files:
            log.info(f"文件正在处理中，跳过: {filepath}")
            return
        processing_files.add(filepath)
    
    try:
        # 等待写入完成
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
    """文件修改事件（已存在的文件被更新）"""
    if event.is_directory:
        return
    
    filepath = event.src_path
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in SUPPORTED_EXTS:
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
    """调用 knowledge_base_manager.py 处理文件"""
    try:
        log.info(f"调用知识库管理器: {filepath}")
        result = subprocess.run(
            ["python3", KB_MANAGER_SCRIPT, filepath],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            log.info(f"知识库管理器处理成功: {filepath}")
            log.debug(result.stdout)
            # graphify 作业已通过 knowledge_base_manager.py 自动入队
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
    observer.schedule(handler, WATCH_DIR, recursive=True)
    observer.start()
    
    log.info(f"✅ 监控启动: {WATCH_DIR}")
    log.info(f"📋 PID: {os.getpid()}")
    log.info(f"📋 日志: {LOG_FILE}")
    log.info("按 Ctrl+C 停止")
    
    # 注册退出清理
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
        # 重定向标准输出/错误
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
    import argparse
    parser = argparse.ArgumentParser(description="法规指导原则知识库监控进程")
    parser.add_argument("--daemon", action="store_true", help="后台守护进程模式")
    parser.add_argument("--stop", action="store_true", help="停止守护进程")
    args = parser.parse_args()
    
    if args.stop:
        daemon_stop()
        return
    
    # 确保目录存在
    os.makedirs(WATCH_DIR, exist_ok=True)
    
    if args.daemon:
        start_daemon()
    else:
        print(f"📦 法规指导原则知识库监控进程 v1.0.0")
        print(f"监控目录: {WATCH_DIR}")
        print(f"支持类型: PDF, DOC, DOCX")
        print()
        start_watching()

if __name__ == "__main__":
    main()
