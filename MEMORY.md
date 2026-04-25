# MEMORY.md - 长期记忆

---

## 已建立的专属Agent

| Agent名称 | 路径 | 功能定位 |
|-----------|------|---------|
| **nonclinical-study-manager** | `~/.openclaw/workspace/agents/nonclinical-study-manager/` | 药品非临床试验项目管理，含方案生成、文档管理、进度跟踪、QA文件管理 |
| **auto-stability-scheme** | `~/.openclaw/workspace/agents/auto-stability-scheme/` | 药品稳定性研究自动化系统 |
| **cde-monitor** | `~/.openclaw/workspace/agents/cde-monitor/` | CDE指导原则监控 |

---

## 核心执行原则（最高优先级）

- 接到任何任务后，必须先查看 available_skills 清单
- 存在相关 Skill 时，先读取对应 SKILL.md，按其说明执行
- 只有 Skill 明确执行失败才允许手动操作
- **自动状态同步**：关于药品稳定性研究自动化系统（auto-stability-scheme），只要在对话中进行了代码开发、调整或决策，**必须在任务完成时主动更新** `~/.openclaw/workspace/agents/auto-stability-scheme/Project_Blueprint.md` 的状态和日志，无需等待用户提醒。

## 文件保存位置偏好

| 类型 | 位置 | 说明 |
|------|------|------|
| 医药研发相关主目录 | `~/Documents/工作/` | |
| AI能力测试与优化 | `~/Documents/AI测试优化/Cortana/` | 自动决定是否建立子目录及名称 |


## 凭证密钥

| 服务 | 用途 | 密钥 |
|------|------|------|
| Notion API | 读写 Notion 数据 | `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` |

## 重要教训

| 日期 | 教训 |
|------|------|
| 2026-03-17 | **会话导出保存要求**：用户要求保存完整对话时，必须：1)按问答顺序完整保存 2)开头结尾加黄色高亮标记Session ID 3)不截断内容 4)包含工作目录和开始/结束时间 |
| 2026-04-24 | **PDF处理架构**：混合PDF必须逐页判断（digital vs scanned），不能整文档一刀切；内容哈希比对应在提取后而非提取前 |
| 2026-04-24 | **VRAM协调**：qwen2.5vl OCR前必须调用vram_manager让出显存，否则OOM；VRAM恢复用try/finally确保执行 |
| 2026-04-24 | **opendataloader --pages参数**：会导致所有元素page_number=None，需要后处理补全页码（文本匹配+顺序分配） |
| 2026-04-24 | **vram_manager调用**：路径`/home/wangyc/.openclaw/scripts/vram_manager.py`；推荐CLI模式`python3 ~/.openclaw/scripts/vram_manager.py acquire|release|status`跨session调用 |
| 2026-04-25 | **数据展示禁止主动推测**：检索和展示数据时，只呈现文件原文提取的原始值和标签，不得推测、填补或脑补附加信息（如温度、浓度、实验条件等未在原文中明确的内容） |

## 会话保存规范

### 用户要求
用户要求保存完整对话时，必须遵循以下格式：

**文件命名**: `session-YYYY-MM-DD.md` 或 `session-YYYY-MM-DD-raw.md`

**开头必须包含（黄色高亮）**:
```html
<span style="background-color: yellow; color: black;">**Session ID**: xxx</span>
<span style="background-color: yellow; color: black;">**工作目录**: /path/to/workspace</span>
<span style="background-color: yellow; color: black;">**开始时间**: 2026-03-17T08:21:07.000Z</span>
<span style="background-color: yellow; color: black;">**日期**: 2026-03-17</span>
```

**结尾必须包含（黄色高亮）**:
```html
<span style="background-color: yellow; color: black;">**会话结束**</span>
<span style="background-color: yellow; color: black;">**Session ID**: xxx</span>
<span style="background-color: yellow; color: black;">**结束时间**: 2026-03-17T17:44:00.000Z</span>
```

**内容要求**:
- 按原始问答顺序交替保存（用户→助手→用户→助手...）
- 不截断任何内容
- 从jsonl文件中提取GMT+8时间戳后的实际内容
- 跳过Exec completed等系统消息

