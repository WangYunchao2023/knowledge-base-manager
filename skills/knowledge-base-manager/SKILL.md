---
name: knowledge-base-manager
description: |
  法规指导原则知识库管理与同步工具。
  功能：原始文件归档 → opendataloader内容提取 → AI自动分类归档 → 更新本地索引 → 同步飞书Wiki
  触发条件：用户提到"知识库管理"、"更新知识库"、"同步法规"、"添加指导原则"时使用。
version: 1.0.0
version_date: 2026-04-02
---

# SKILL.md - 法规指导原则知识库管理器 (v1.0.0)

> 本 Skill 是「知识、信息层」的核心管理工具，实现知识库的**全自动化闭环维护**。

---

## 核心能力

```
用户: "把这个新指导原则加到知识库: /path/to/xxx.pdf"
                    │
                    ▼
┌──────────────────────────────────────────────────────────────┐
│  knowledge-base-manager (本 Skill)                           │
│                                                              │
│  Step 1: 原始文件归档                                         │
│          /path/to/xxx.pdf → 稳定性指导原则/原始文件/           │
│                                                              │
│  Step 2: opendataloader 内容提取                             │
│          → 稳定性指导原则/供AI用信息/xxx.md                   │
│          → 稳定性指导原则/供AI用信息/xxx.json                  │
│                                                              │
│  Step 3: AI 自动分类                                         │
│          category / status / doc_type / tags                  │
│                                                              │
│  Step 4: 更新 guidance_index.json                              │
│          新增索引条目，含所有元数据 + 路径信息                 │
│                                                              │
│  Step 5: 飞书 Wiki 同步（需 Cortana 调用 feishu_create_doc）   │
│          创建云端文档，回填 feishu_wiki_url                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 目录结构规范

```
法规指导原则规定知识库/
├── guidance_index.json              ← 全局索引文件
│
├── 稳定性指导原则/
│   ├── 原始文件/                   ← 原始 PDF/DOCX（不参与检索）
│   │   └── *.pdf, *.docx
│   └── 供AI用信息/                 ← opendataloader 提取的内容（AI 检索用）
│       ├── *.md                   ← 提取的 Markdown 正文
│       └── *.json                 ← 提取的结构化 JSON（含位置信息）
│
├── 参考模板/
└── 内部文件/
```

**关键设计**：
- **原始文件**与**提取内容**严格分离
- AI 只读取 `供AI用信息/*.md`，不读取原始 PDF
- 原始 PDF 存档备查，不参与任何自动化流程

---

## 核心索引结构 (guidance_index.json)

```json
{
  "version": "1.1",
  "last_updated": "2026-04-02",
  "kb_root": "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库",
  "total_docs": 14,
  "documents": [
    {
      "id": "guidance_化学药_20150205_main",
      "title": "化学药物（原料药和制剂）稳定性研究技术指导原则",
      "issue_date": "20150205",
      "status": "active",              // active | draft | reference
      "doc_type": "main",             // main | draft | explanation | feedback
      "scope": {
        "category": "化学药",        // 化学药 | 中药 | 生物制品 | 通用
        "type": ["原料药", "制剂"]
      },
      "tags": ["稳定性", "化学药", "制剂", "研究技术", "指导原则"],
      "paths": {
        "raw": "/path/to/原始文件/20150205 - ...pdf",
        "markdown": "/path/to/供AI用信息/20150205 - ....md",
        "json": "/path/to/供AI用信息/20150205 - ....json",
        "feishu_wiki_url": "https://www.feishu.cn/wiki/..."  // 同步后填充
      },
      "source_subdir": "稳定性指导原则"
    }
  ]
}
```

---

## 使用方式

### 方式一：增量检查（推荐日常工作流）
```
用户: "检查一下知识库有没有新的指导原则"
Cortana: python knowledge_base_manager.py
```

### 方式二：添加单个文件
```
用户: "把这个文件加入知识库: /path/to/新指导原则.pdf"
Cortana: python knowledge_base_manager.py /path/to/新指导原则.pdf
```

### 方式三：批量扫描目录
```
用户: "扫描这个目录，把所有新文件加入知识库"
Cortana: python knowledge_base_manager.py /path/to/directory/
```

### 方式四：重建索引
```
用户: "重建知识库索引"
Cortana: python knowledge_base_manager.py --rebuild
```

### 方式五：飞书同步（查看待同步列表）
```
用户: "哪些文档还没同步到飞书？"
Cortana: python knowledge_base_manager.py --sync-feishu
```

---

## 自动分类规则

分类由脚本根据文件名**自动推断**，无需人工指定：

| 维度 | 规则 |
|-----|------|
| **category** | 文件名含"化学药/化学药品"→化学药；含"中药/天然药物"→中药；含"生物制品"→生物制品 |
| **status** | 含"征求意见稿"→draft；含"反馈意见表/起草说明"→reference；其他→active |
| **doc_type** | 正文→main；征求意见稿→draft；起草说明→explanation；反馈表→feedback |
| **drug_types** | 文件名含"注射剂/原料药/制剂/口服"等 |

---

## 飞书 Wiki 同步机制

**Cortana 负责调用 OpenClaw 工具完成此步骤**，流程如下：

```
Step 5a: 读取 guidance_index.json 中的待同步文档
         条件: feishu_wiki_url 为空 AND doc_type 不在 SKIP_FEISHU_TYPES

Step 5b: 读取对应 .md 文件内容

Step 5c: 调用 feishu_create_doc(
           markdown=内容,
           title=文档标题,
           wiki_space=FEISHU_SPACE_ID
         )

Step 5d: 获取返回的 wiki_url，回填到 guidance_index.json
```

**SKIP_FEISHU_TYPES** = `["feedback", "explanation"]`
→ 反馈意见表、起草说明不主动同步到飞书 Wiki（仅本地存档）

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| **v1.0.0** | **2026-04-02** | **整合版：原始文件归档 + opendataloader 提取 + 索引更新 + 飞书同步全流程** |
| v0.1.0 | 2026-04-02 | 初始版本（仅索引更新） |

---

## 依赖

| 工具 | 作用 |
|-----|------|
| `opendataloader-pdf` Skill | PDF/Word 文档内容提取 |
| `feishu_create_doc` | 飞书 Wiki 文档创建 |
| `guidance_index.json` | 本地索引文件 |

---

## 配置项

```python
# 知识库根目录
KB_ROOT = "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库"

# 目录规范
DIR_RAW = "原始文件"           # 存放原始 PDF/DOCX
DIR_EXTRACTED = "供AI用信息"   # 存放提取的 Markdown/JSON

# 索引文件
INDEX_FILE = os.path.join(KB_ROOT, "guidance_index.json")

# opendataloader 脚本路径
OPENDATALOADER_SCRIPT = "/home/wangyc/.openclaw/workspace/skills/opendataloader-pdf/scripts/opendataloader_auto.py"

# 飞书 Wiki Space ID
FEISHU_SPACE_ID = "7624081815959014593"

# 同步到飞书时跳过的文档类型
SKIP_FEISHU_TYPES = ["feedback", "explanation"]
```