#!/usr/bin/env python3
"""
版本: 2.8.0
功能: 知识库检索与信息提取工作流测试
      模拟 AI 收到任务后，如何从知识库中检索并提取信息

用法:
  python test_retrieval.py "化学药品注射剂"
  python test_retrieval.py "中药制剂"
  python test_retrieval.py "生物制品"
"""

import json
import os
import sys

# ============ 配置区 ============
KB_ROOT = "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库"
INDEX_FILE = os.path.join(KB_ROOT, "guidance_index.json")
# ==============================

def load_index():
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def search_guidance(query, index_data):
    """
    模拟 AI 的检索过程：
    1. 根据查询词过滤索引
    2. 按相关性排序
    3. 返回匹配的文档列表
    """
    query_lower = query.lower()
    results = []
    
    for doc in index_data.get("documents", []):
        score = 0
        matched_fields = []
        
        # 检查 category
        category = doc.get("scope", {}).get("category", "")
        if category and query_lower in category.lower():
            score += 10
            matched_fields.append(f"category={category}")
        
        # 检查 drug_types
        drug_types = doc.get("scope", {}).get("type", [])
        for dt in drug_types:
            if query_lower in dt.lower():
                score += 5
                matched_fields.append(f"type={dt}")
        
        # 检查 tags
        tags = doc.get("tags", [])
        for tag in tags:
            if query_lower in tag.lower():
                score += 3
                matched_fields.append(f"tag={tag}")
        
        # 检查 title
        title = doc.get("title", "")
        if query_lower in title.lower():
            score += 8
            matched_fields.append("title命中")
        
        # 跳过非 active 文档（除非正好是 draft）
        # status = doc.get("status", "")
        # if status == "reference":
        #     continue
        
        if score > 0:
            results.append({
                "id": doc["id"],
                "title": title,
                "score": score,
                "matched_fields": matched_fields,
                "status": doc.get("status", ""),
                "doc_type": doc.get("doc_type", ""),
                "paths": doc.get("paths", {}),
                "scope": doc.get("scope", {})
            })
    
    # 按相关性排序（考虑状态优先级）
    # active > draft > reference
    status_priority = {"active": 3, "draft": 2, "reference": 1}
    
    def sort_key(x):
        status_val = status_priority.get(x["status"], 0)
        return (x["score"], status_val)
    
    results.sort(key=sort_key, reverse=True)
    return results

def extract_key_info(md_path, keywords):
    """
    从 Markdown 文件中提取包含关键词的内容
    模拟 AI 阅读文档并提取关键信息
    """
    if not os.path.exists(md_path):
        return None
    
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    extracted = []
    lines = content.split("\n")
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        for kw in keywords:
            if kw.lower() in line_lower:
                # 获取上下文（前2行作为标题/背景）
                context_start = max(0, i - 2)
                context = lines[context_start:i+3]
                extracted.append({
                    "keyword": kw,
                    "context": "\n".join(context),
                    "line_number": i + 1
                })
                break
    
    return extracted

def simulate_ai_task(query):
    """
    模拟完整的工作流：
    1. AI 收到任务
    2. 检索知识库
    3. 阅读相关文档
    4. 提取关键信息
    """
    print("=" * 70)
    print(f"🤖 AI 任务: 为「{query}」生成稳定性研究计划")
    print("=" * 70)
    
    # Step 1: 加载索引
    index_data = load_index()
    print(f"\n📚 知识库加载完成: {len(index_data['documents'])} 个文档")
    
    # Step 2: 检索
    print(f"\n🔍 开始检索: '{query}'")
    results = search_guidance(query, index_data)
    print(f"   找到 {len(results)} 个相关文档\n")
    
    for i, r in enumerate(results[:3], 1):  # 只显示前3个
        print(f"  {i}. [{r['scope']['category']}] {r['title']}")
        print(f"     相关性得分: {r['score']}")
        print(f"     匹配字段: {', '.join(r['matched_fields'])}")
        print(f"     状态: {r['status']} | 类型: {r['doc_type']}")
        print()
    
    if not results:
        print("  ❌ 未找到相关文档")
        return
    
    # Step 3: 读取最相关的文档
    top_doc = results[0]
    relative_path = top_doc["paths"].get("markdown", "")
    
    # 转换相对路径为绝对路径
    md_path = os.path.join(KB_ROOT, relative_path)
    
    print("-" * 70)
    print(f"📖 阅读文档: {top_doc['title']}")
    print(f"   文件路径: {md_path}")
    print("-" * 70)
    
    # Step 4: 提取关键信息
    # 根据药物类型确定需要提取的关键词
    if "化学药" in query:
        keywords = ["加速试验", "长期试验", "影响因素", "温度", "湿度", "考察时间", "取样"]
    elif "中药" in query:
        keywords = ["加速试验", "长期试验", "高湿", "高热", "光照", "考察时间"]
    elif "生物制品" in query:
        keywords = ["加速试验", "长期试验", "冷冻", "运输", "生物学活性"]
    else:
        keywords = ["加速试验", "长期试验", "温度", "湿度", "考察"]
    
    print(f"\n🔑 提取关键词: {keywords}\n")
    
    extracted = extract_key_info(md_path, keywords)
    
    if extracted:
        # 去重并展示
        shown = set()
        for item in extracted[:10]:  # 最多显示10条
            context = item["context"][:200]  # 截断显示
            key = (item["keyword"], item["line_number"])
            if key not in shown:
                shown.add(key)
                print(f"  📌 [{item['keyword']}] 第{item['line_number']}行:")
                print(f"     {context}...")
                print()
    else:
        print("  ⚠️ 未提取到关键信息（可能关键词不匹配）")
    
    # Step 5: 总结
    print("=" * 70)
    print(f"📋 AI 总结:")
    print(f"   根据检索结果，最相关的指导原则是:")
    print(f"   「{top_doc['title']}」")
    print(f"   (状态: {top_doc['status']})")
    print(f"   ")
    print(f"   该文档已提取 {len(extracted) if extracted else 0} 条关键信息")
    print(f"   AI 可基于这些信息，结合药品特性，生成稳定性研究计划")
    print("=" * 70)

def main():
    if len(sys.argv) > 1:
        query = sys.argv[1]
    else:
        query = "化学药品注射剂"
    
    simulate_ai_task(query)

if __name__ == "__main__":
    main()
