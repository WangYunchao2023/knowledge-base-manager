import json
import os

def generate_reference_md(source_name, title, clauses):
    """
    生成 Reference 目录下的 .md 摘要
    """
    md_content = f"# {title}\n\n"
    md_content += f"## 核心条款摘要 (Core Clauses)\n\n"
    for clause in clauses:
        md_content += f"- **{clause['title']}**: {clause['content']} [Source: {clause['source']}]\n"
    
    return md_content

def generate_reference_json(id, title, org, category, tags, source_file):
    """
    生成 Reference 目录下的 .json 元数据
    """
    data = {
        "id": id,
        "title": title,
        "org": org,
        "category": category,
        "tags": tags,
        "source_file": source_file,
        "version": "Current",
        "status": "现行"
    }
    return json.dumps(data, indent=2, ensure_ascii=False)

# 示例数据 (假设解析出的内容)
clauses_stability = [
    {"title": "长期试验条件", "content": "25°C ± 2°C / 60% RH ± 5% RH，12个月", "source": "P5, Section 2.1.7"},
    {"title": "加速试验条件", "content": "40°C ± 2°C / 75% RH ± 5% RH，6个月", "source": "P6, Section 2.1.8"},
    {"title": "批次要求", "content": "至少3个生产规模批次", "source": "P4, Section 2.1.2"}
]

# 准备写入示例
# 实际工作中，这将由解析逻辑驱动
