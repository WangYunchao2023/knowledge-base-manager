# knowledge-base-manager

法规指导原则知识库管理与自动同步工具

## 功能

- **自动分类**：根据文件名自动分流到化学药/中药/生物制品/通用目录
- **内容提取**：opendataloader 自动提取 PDF/DOCX 内容生成 .md + .json
- **索引管理**：guidance_index.json 统一索引（含章节索引 + 页码索引）
- **知识图谱**：Graphify 自动构建 52节点/53边法规知识图谱
- **自动触发**：watchdog 监控 + graphify 后台增量更新

## 目录结构

```
知识库/
├── guidance_index.json          # 统一索引
├── graphify-out/                # 知识图谱
├── 化学药/
│   └── 稳定性指导原则/
│       ├── 原始文件/            # 原始 PDF/DOCX
│       └── 供AI用信息/          # .md + .json
├── 中药/
└── 生物制品/
```

## 核心脚本

| 脚本 | 功能 |
|------|------|
| `knowledge_base_manager.py` | 主管理器：归档→提取→索引→触发 graphify |
| `add_section_index.py` | 提取文档章节标题+行号 |
| `add_page_index.py` | 提取 PDF 页码→markdown 行号映射 |
| `graphify_integration.py` | Graphify 图谱对接 |
| `graphify_job.py` | 图谱作业队列处理器 |
| `watch_guidance_lib.py` | watchdog 监控进程 |
| `dify_integration.py` | Dify RAG 对接（骨架）|

## 版本

v3.0.0 (2026-04-24)

## 依赖

- `opendataloader-pdf` skill
- `graphify` (pip)
- `watchdog` (pip)
- Python 3.10+
