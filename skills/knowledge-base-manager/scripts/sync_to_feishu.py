#!/usr/bin/env python3
"""
版本: 1.0.0
功能: 将本地 Markdown 文档同步到飞书知识库
用法: python sync_to_feishu.py
依赖: 需要设置环境变量或直接在代码中配置飞书 API
"""

import json
import os
import re
import sys

# ============ 配置区 ============
KB_ROOT = "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库"
INDEX_FILE = os.path.join(KB_ROOT, "guidance_index.json")
FEISHU_SPACE_ID = "7624081815959014593"  # 飞书知识库 Space ID
# ==============================

def load_index():
    """加载本地索引"""
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_category_from_path(path):
    """从路径提取分类"""
    if "稳定性" in path:
        return "稳定性"
    elif "参考模板" in path:
        return "参考模板"
    elif "内部文件" in path:
        return "内部文件"
    return "其他"

def should_sync(doc_info):
    """判断是否应该同步到飞书（跳过参考类文档）"""
    if doc_info.get("doc_type") in ["feedback", "explanation"]:
        return False
    if doc_info.get("status") == "reference":
        return False
    return True

def main():
    print("=" * 60)
    print("飞书知识库同步工具")
    print("=" * 60)
    
    # 加载索引
    index_data = load_index()
    print(f"\n📖 从索引加载了 {index_data['total_docs']} 个文档")
    print(f"🏠 目标知识库 Space ID: {FEISHU_SPACE_ID}")
    print()
    
    # 待同步文档列表
    to_sync = [doc for doc in index_data["documents"] if should_sync(doc)]
    print(f"📋 待同步文档: {len(to_sync)} 个\n")
    
    print("-" * 60)
    for i, doc in enumerate(to_sync, 1):
        full_path = os.path.join(KB_ROOT, doc["paths"]["markdown"])
        print(f"{i}. [{doc['scope']['category']}] {doc['title']}")
        print(f"   本地路径: {full_path}")
        print(f"   状态: {doc['status']} | 类型: {doc['doc_type']}")
        print()
    
    print("-" * 60)
    print(f"\n✅ 共 {len(to_sync)} 个文档待同步到飞书")
    print("\n⚠️  注意: 由于飞书 API 限制，文件夹需要手动在 UI 中创建")
    print("   同步完成后，请手动将文档拖入对应的分类文件夹")
    print("\n📝 下一步: 请在终端中运行以下命令（需 Cortana AI 执行飞书 API）")

if __name__ == "__main__":
    main()
