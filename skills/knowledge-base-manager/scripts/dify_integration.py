#!/usr/bin/env python3
"""
版本: 3.0.0
功能: Dify RAG 对接模块（骨架实现，待 Docker/Dify 安装后完善）
      将法规指导原则库的 .md 文件同步到 Dify 数据集

触发方式:
  python dify_integration.py --sync         # 同步所有 .md 到 Dify
  python dify_integration.py --status       # 查看 Dify 连接状态
  python dify_integration.py --add FILE.md  # 添加单个文件
  python dify_integration.py --check         # 检查 Dify 是否可用

知识库管理器调用:
  python knowledge_base_manager.py --trigger-hook dify

Dify API 文档: https://docs.dify.ai/api-reference/datasets
"""

import os
import sys
import json
import time
import hashlib
import requests
import argparse
from datetime import datetime
from pathlib import Path

# ============ 配置区 ============
KB_ROOT = "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库"
DIFY_EXTRACTED_DIR = os.path.join(KB_ROOT, "稳定性", "供AI用信息")

# Dify 配置（环境变量 / 这里硬编码二选一）
DIFY_API_URL = os.environ.get("DIFY_API_URL", "http://localhost/v1")
DIFY_API_KEY = os.environ.get("DIFY_API_KEY", "")
DIFY_DATASET_ID = os.environ.get("DIFY_DATASET_ID", "")

# 本地状态文件
DIFY_STATE_FILE = os.path.join(KB_ROOT, "dify_sync_state.json")

# 超时配置
REQUEST_TIMEOUT = 30
# ==============================

def log(msg, emoji="🔍"):
    print(f"{emoji} {msg}")


# ---- Dify API 封装 ----

class DifyClient:
    """Dify API 客户端（待完善，具体接口等安装 Dify 后补充）"""
    
    def __init__(self, api_url, api_key):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def is_available(self):
        """检查 Dify 服务是否可达"""
        if not self.api_key:
            return False, "DIFY_API_KEY 未设置"
        try:
            resp = requests.get(
                f"{self.api_url}/datasets",
                headers=self.headers,
                timeout=REQUEST_TIMEOUT
            )
            if resp.status_code == 200:
                return True, "连接正常"
            else:
                return False, f"HTTP {resp.status_code}: {resp.text[:100]}"
        except requests.ConnectionError:
            return False, "无法连接到 Dify 服务（请确认 Docker 容器是否运行）"
        except Exception as e:
            return False, str(e)
    
    def list_datasets(self):
        """列出所有数据集"""
        try:
            resp = requests.get(
                f"{self.api_url}/datasets",
                headers=self.headers,
                timeout=REQUEST_TIMEOUT
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", [])
            return []
        except Exception as e:
            return []
    
    def create_dataset(self, name, description=""):
        """创建数据集"""
        try:
            resp = requests.post(
                f"{self.api_url}/datasets",
                headers=self.headers,
                json={"name": name, "description": description},
                timeout=REQUEST_TIMEOUT
            )
            if resp.status_code == 200:
                return resp.json().get("data", {}).get("id")
            return None
        except Exception:
            return None
    
    def upload_document(self, dataset_id, file_path, chunk_size=500):
        """
        上传文档到数据集
        Dify 支持通过 multipart/form-data 上传，
        文档上传后会进行embedding处理
        """
        if not os.path.exists(file_path):
            return None, "文件不存在"
        
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f, "text/markdown")}
                data = {
                    "dataset_id": dataset_id,
                    "process_rule": json.dumps({
                        "mode": "auto",
                        "chunk_size": chunk_size,
                        "pre_processing_rules": [
                            {"id": "remove_extra_spaces", "enabled": True},
                            {"id": "remove_urls_emails", "enabled": False}
                        ]
                    })
                }
                resp = requests.post(
                    f"{self.api_url}/datasets/{dataset_id}/documents",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files=files,
                    data=data,
                    timeout=120
                )
            
            if resp.status_code == 200:
                result = resp.json()
                doc_id = result.get("data", {}).get("id")
                return doc_id, "上传成功"
            else:
                return None, f"上传失败: {resp.status_code} {resp.text[:100]}"
        except Exception as e:
            return None, str(e)
    
    def get_document_status(self, dataset_id, document_id):
        """查询文档 embedding 状态"""
        try:
            resp = requests.get(
                f"{self.api_url}/datasets/{dataset_id}/documents/{document_id}",
                headers=self.headers,
                timeout=REQUEST_TIMEOUT
            )
            if resp.status_code == 200:
                return resp.json().get("data", {})
            return None
        except Exception:
            return None
    
    def delete_document(self, dataset_id, document_id):
        """删除文档"""
        try:
            resp = requests.delete(
                f"{self.api_url}/datasets/{dataset_id}/documents/{document_id}",
                headers=self.headers,
                timeout=REQUEST_TIMEOUT
            )
            return resp.status_code in (200, 204)
        except Exception:
            return False


# ---- 状态管理 ----

def load_sync_state():
    """加载同步状态"""
    if os.path.exists(DIFY_STATE_FILE):
        with open(DIFY_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "version": "1.0",
        "last_sync": "",
        "dataset_id": "",
        "dataset_name": "法规指导原则知识库",
        "synced_files": {},  # {文件名: {md5, document_id, status}}
        "total_synced": 0
    }

def save_sync_state(state):
    with open(DIFY_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def file_md5(filepath):
    m = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            m.update(chunk)
    return m.hexdigest()


# ---- 核心同步逻辑 ----

def sync_all(dify_client, state):
    """将所有 .md 文件同步到 Dify"""
    log("开始同步 .md 文件到 Dify...", "🔄")
    
    # 确保数据集存在
    dataset_id = state.get("dataset_id")
    if not dataset_id:
        # 尝试找同名数据集
        datasets = dify_client.list_datasets()
        for ds in datasets:
            if ds.get("name") == state["dataset_name"]:
                dataset_id = ds["id"]
                break
        
        if not dataset_id:
            log("创建新数据集...", "🆕")
            dataset_id = dify_client.create_dataset(state["dataset_name"], "法规指导原则知识库")
            if not dataset_id:
                log("❌ 数据集创建失败", "❌")
                return state
            log(f"数据集已创建 ID={dataset_id}", "✅")
        
        state["dataset_id"] = dataset_id
    
    # 扫描待同步文件
    md_files = []
    if os.path.exists(DIFY_EXTRACTED_DIR):
        for fname in os.listdir(DIFY_EXTRACTED_DIR):
            if fname.endswith(".md"):
                md_files.append(os.path.join(DIFY_EXTRACTED_DIR, fname))
    
    log(f"发现 {len(md_files)} 个 .md 文件", "📄")
    
    synced = 0
    skipped = 0
    failed = 0
    
    for fpath in md_files:
        fname = os.path.basename(fpath)
        fmd5 = file_md5(fpath)
        
        # 检查是否已同步（MD5 一致则跳过）
        if fname in state["synced_files"]:
            prev = state["synced_files"][fname]
            if prev.get("md5") == fmd5 and prev.get("status") == "completed":
                skipped += 1
                continue
        
        log(f"上传: {fname}", "⬆️")
        doc_id, msg = dify_client.upload_document(dataset_id, fpath)
        
        if doc_id:
            state["synced_files"][fname] = {
                "md5": fmd5,
                "document_id": doc_id,
                "status": "completed",
                "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            synced += 1
            log(f"✅ {fname} → {doc_id}", "✅")
        else:
            state["synced_files"][fname] = {
                "md5": fmd5,
                "status": "failed",
                "error": msg
            }
            failed += 1
            log(f"❌ {fname}: {msg}", "❌")
    
    state["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    state["total_synced"] = len(state["synced_files"])
    save_sync_state(state)
    
    print()
    print("=" * 50)
    print(f"✅ 同步完成: {synced} 个 | ⏭ 跳过: {skipped} 个 | ❌ 失败: {failed} 个")
    print(f"📋 Dify Dataset ID: {dataset_id}")
    print(f"⏰ 最后同步: {state['last_sync']}")
    print("=" * 50)
    
    return state


# ---- 主入口 ----

def main():
    parser = argparse.ArgumentParser(description="Dify RAG 对接模块（骨架版）")
    parser.add_argument("--sync", action="store_true", help="同步所有 .md 到 Dify")
    parser.add_argument("--status", action="store_true", help="查看 Dify 连接状态")
    parser.add_argument("--add", type=str, help="添加单个 .md 文件")
    parser.add_argument("--check", action="store_true", help="检查 Dify 是否可用")
    args = parser.parse_args()
    
    print("🔍 Dify RAG 对接模块 v1.0.0（骨架版）")
    print()
    
    # 检查 Dify 配置
    if not DIFY_API_KEY:
        print("⚠️  未配置 DIFY_API_KEY 环境变量")
        print("   请在 Docker 安装 Dify 后设置:")
        print("   export DIFY_API_KEY=your-api-key")
        print("   export DIFY_API_URL=http://localhost/v1")
        print()
    
    # 状态查看
    if args.status:
        state = load_sync_state()
        print("同步状态:")
        print(f"  数据集ID: {state.get('dataset_id', '未设置')}")
        print(f"  最后同步: {state.get('last_sync', '从未')}")
        print(f"  已同步文件: {state.get('total_synced', 0)} 个")
        print()
        
        if DIFY_API_KEY:
            client = DifyClient(DIFY_API_URL, DIFY_API_KEY)
            ok, msg = client.is_available()
            print(f"Dify 连接: {'✅' if ok else '❌'} {msg}")
        return
    
    # 连接检查
    if args.check:
        if not DIFY_API_KEY:
            print("❌ DIFY_API_KEY 未设置")
            sys.exit(1)
        client = DifyClient(DIFY_API_URL, DIFY_API_KEY)
        ok, msg = client.is_available()
        print(f"{'✅' if ok else '❌'} Dify: {msg}")
        if ok:
            datasets = client.list_datasets()
            print(f"已有数据集: {len(datasets)} 个")
            for ds in datasets[:5]:
                print(f"  - {ds.get('name')} ({ds.get('id')})")
        sys.exit(0 if ok else 1)
    
    # 同步
    if args.sync:
        if not DIFY_API_KEY:
            print("❌ 需要设置 DIFY_API_KEY")
            sys.exit(1)
        client = DifyClient(DIFY_API_URL, DIFY_API_KEY)
        ok, msg = client.is_available()
        if not ok:
            print(f"❌ Dify 不可用: {msg}")
            sys.exit(1)
        state = load_sync_state()
        sync_all(client, state)
        return
    
    # 单文件添加
    if args.add:
        if not DIFY_API_KEY:
            print("❌ 需要设置 DIFY_API_KEY")
            sys.exit(1)
        client = DifyClient(DIFY_API_URL, DIFY_API_KEY)
        state = load_sync_state()
        dataset_id = state.get("dataset_id")
        if not dataset_id:
            print("❌ 未找到数据集ID，请先 --sync")
            sys.exit(1)
        doc_id, msg = client.upload_document(dataset_id, args.add)
        if doc_id:
            print(f"✅ 上传成功: {doc_id}")
        else:
            print(f"❌ 上传失败: {msg}")
        sys.exit(0 if doc_id else 1)
    
    # 默认：打印帮助 + 状态
    print(__doc__)
    print()
    state = load_sync_state()
    print(f"当前状态: 已同步 {state.get('total_synced', 0)} 个文件")
    print(f"最后同步: {state.get('last_sync', '从未')}")


if __name__ == "__main__":
    main()
