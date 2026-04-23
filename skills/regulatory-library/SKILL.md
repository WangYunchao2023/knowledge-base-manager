---
name: regulatory-library
description: 药品法规参考库管理。通过"双层参考+追溯"机制，为实验方案生成和申报资料撰写提供法规依据。
---

# SKILL.md - 药品法规参考库管理 (Regulatory Library Management)

## 核心定位
本 Skill 负责维护和检索本地药品法规库。它通过“双层参考+追溯”机制，为实验方案生成和申报资料撰写提供法规依据。

## 目录规范 (Standard Directory)
- **01_Sources/**: 原始文件 (PDF/Word)，按 [机构]/[领域]/[类型] 存放。
- **02_Reference/**: 结构化参考 (.md + .json)，包含核心条款摘要及原文页码追溯。
- **03_Index/**: 自动化生成的索引 (keywords_map.json)。

## 分类逻辑 (Classification)
1. **L1 (机构)**: `NMPA_CDE`, `ICH`, `FDA`, `EMA` 等。
2. **L2 (领域)**: `CMC`, `Pre-Clinical`, `Clinical`, `Regulatory` 等。
3. **L3 (类别)**: `00_General` (通用), `Chemical` (化药), `Biological` (生物药), `TCM` (中药)。

## 核心操作流 (Workflows)

### 1. 法规入库 (Ingestion)
1. 使用 `web-access` 下载法规 PDF 至 `01_Sources` 对应目录。
2. 在 `02_Reference` 对应目录下创建同名 `.json` 元数据文件。
3. 提取核心条款（带页码/章节号）至同名 `.md` 文件。

### 2. 法规检索 (Search)
1. **语义匹配**: 优先检索 `02_Reference/*.md` 的摘要。
2. **全文兜底**: 若摘要无匹配，使用 `ripgrep` 对 `01_Sources` 下的文本内容进行全量扫描。
3. **引用输出**: 必须包含 `[Source: 路径/页码]` 确保可追溯性。

## 自动化工具 (Future)
- `organize.py`: 自动根据 JSON 标签归类文件。
- `reindex.sh`: 重新生成全局索引。
