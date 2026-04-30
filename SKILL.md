---
name: knowledge-base-manager
version: 2.13.0
version_date: 2026-04-30
description: |
  v2.13.0: 内容哈希比对前增加标题过滤——不同标题直接跳过哈希比对，解决同日发布的不同文档碰巧封面相同导致的假误判。
  v2.12.0: graphify 钩子同步等待修复 — 旧版 openclaw agent 立即返回导致钩子失效；改用唯一 session id + 线程轮询 session age，直到 agent 完成（最多20分钟）。
  v2.11.0: 批量入库 skip_qwen 优化 — 数字 PDF 跳过 qwen2.5vl，批量速度提升 40 倍。
  v2.10.0: 修复 check_duplicate_by_hash stored=None 崩溃、每文件保存、--recover 恢复。
  法规指导原则知识库管理与自动同步工具。
  功能：原始文件归档 → opendataloader内容提取 → AI自动分类 → 更新索引 → 自动触发 graphify 图谱构建（后台agent执行）
  触发条件：用户提到"知识库管理"、"更新知识库"、"添加指导原则"、"检查知识库"时使用。
---

# SKILL.md - 法规指导原则知识库管理器 (v2.12.0)

> 本 Skill 是「知识、信息层」的核心管理工具，实现知识库的**全自动化闭环维护**。
> 支持三种入库方式，自动触发 graphify 图谱后台构建。

---

## 目录结构规范

```
法规指导原则规定知识库/
├── guidance_index.json              ← 全局索引文件（AI 检索用）
│
├── graphify-out/                     ← Graphify 图谱输出
│   ├── graph.json                    ← 可查询知识图谱
│   ├── graph.html                   ← 人类可读交互图谱
│   ├── GRAPH_REPORT.md              ← 图谱审计报告
│   └── graph_index.json             ← 图谱元数据
│
├── jobs/                             ← 作业队列（内部使用）
│   ├── pending_job.json             ← 待处理的 graphify 作业
│   └── graphify.lock                ← 执行锁（防止并发）
│
├── dify_sync_state.json              ← Dify 同步状态（待 Dify 安装后启用）
│
├── 稳定性指导原则/
│   ├── 原始文件/                    ← 原始 PDF/DOCX（不参与检索）
│   └── 供AI用信息/                  ← opendataloader 提取的内容（AI 检索用）
│
├── 参考模板/
└── 内部文件/
```

---

## 核心索引结构 (guidance_index.json)

```json
{
  "version": "2.0",
  "last_updated": "2026-04-24",
  "kb_root": "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库",
  "total_docs": 14,
  "documents": [
    {
      "id": "guidance_化学药_20150205_main",
      "title": "化学药物（原料药和制剂）稳定性研究技术指导原则",
      "issue_date": "20150205",
      "status": "active",
      "doc_type": "main",
      "scope": {
        "category": "化学药",
        "type": ["原料药", "制剂"]
      },
      "tags": ["稳定性", "化学药", "制剂", "研究技术", "指导原则"],
      "paths": {
        "raw": "/path/to/原始文件/xxx.pdf",
        "markdown": "/path/to/供AI用信息/xxx.md",
        "json": "/path/to/供AI用信息/xxx.json"
      },
      "source_subdir": "稳定性指导原则"
    }
  ]
}
```

---

## 全自动工作流

```
┌─────────────────────────────────────────────────────────────────────┐
│                        三种触发入口                                  │
│  1. 用户触发："把这个指导原则加到知识库"                                │
│  2. 手动放入：PDF → 稳定性指导原则/原始文件/                            │
│  3. Agent发现：其它skill监测到新发布 → 调用本skill                    │
└─────────────────────────────┬───────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│              knowledge_base_manager.py（统一处理）                      │
│                                                                      │
│  Step 1: 原始文件归档                                                 │
│  Step 2: opendataloader 内容提取                                      │
│  Step 3: AI 自动分类（category/status/doc_type/tags）                 │
│  Step 4: 更新 guidance_index.json                                     │
│  Step 5: graphify_job.py --enqueue（作业入队）                         │
└─────────────────────────────┬───────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│              cron job（每分钟检查队列）                                │
│              graphify_job.py --dequeue                              │
│              → 取出作业，触发 openclaw agent                         │
└─────────────────────────────┬───────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│              openclaw agent（后台执行 /graphify 流程）                 │
│              → 实体提取 → 建图 → 聚类 → 输出 graph.json             │
│              → 预计 3-10 分钟完成                                     │
└─────────────────────────────────────────────────────────────────────┘
                              ▼
              graphify-out/graph.json（知识图谱就绪）
```

---

## 自动监控模式（watchdog）

watchdog 监控进程已注册为 systemd 用户服务，开机自启：

```bash
# 启动
systemctl --user start watch-guidance-lib.service

# 停止
systemctl --user stop watch-guidance-lib.service

# 查看状态
systemctl --user status watch-guidance-lib.service

# 查看日志
tail -f /tmp/watch_guidance_lib.log
```

**监控目录**: `稳定性指导原则/`（递归监控子目录）
**触发流程**: 检测到新 PDF/DOCX → 等待写入完成 → 触发处理管道

---

## 作业队列管理

| 操作 | 命令 |
|------|------|
| 查看队列状态 | `python3 graphify_job.py --status` |
| 手动加入作业 | `python3 graphify_job.py --enqueue` |
| 手动触发执行 | `python3 graphify_job.py --dequeue` |
| 强制全量重建 | `python3 graphify_job.py --run-now` |
| 清空队列 | `rm jobs/pending_job.json` |

---

## 使用方式

| 场景 | 命令 |
|------|------|
| 用户触发：增量检查 | `python3 knowledge_base_manager.py` |
| 用户触发：添加文件 | `python3 knowledge_base_manager.py /path/to/xxx.pdf` |
| 用户触发：批量入库 | `python3 knowledge_base_manager.py /path/to/dir/` |
| 用户触发：重建索引 | `python3 knowledge_base_manager.py --rebuild` |
| 用户触发：查看状态 | `python3 knowledge_base_manager.py --status` |
| cron/agent 触发 | `python3 knowledge_base_manager.py --trigger-hook graphify` |

---

## graphify 图谱集成

### Cortana 检索接口

```python
# 读取 guidance_index.json 快速检索
python3 knowledge_base_manager.py --status

# 读取 graph.json 做语义推理
python3 graphify_integration.py --summary

# 查询图谱
python3 graphify_integration.py --query "注射剂稳定性"
```

### graphify agent 能力
```
/graphify query "注射剂稳定性研究需要做哪些试验"   # BFS 宽范围检索
/graphify query "哪些指导原则提到长期试验" --dfs     # DFS 深度追溯
/graphify path "影响因素试验" "长期稳定性"           # 找两节点最短路径
/graphify explain "含量测定"                        # 解释节点所有连接
```

---

## Dify RAG 集成（待 Docker/Dify 安装后启用）

```bash
export DIFY_API_URL=http://localhost/v1
export DIFY_API_KEY=your-api-key
python3 dify_integration.py --check     # 检查连接
python3 dify_integration.py --sync      # 同步所有 .md 到 Dify
```

---

## 自动分类规则

| 维度 | 规则 |
|-----|------|
| **category** | 文件名含"化学药/化学药品"→化学药；含"中药/天然药物"→中药；含"生物制品"→生物制品 |
| **status** | 含"征求意见稿"→draft；含"反馈意见表/起草说明"→reference；其他→active |
| **doc_type** | 正文→main；征求意见稿→draft；起草说明→explanation；反馈表→feedback |
| **drug_types** | 文件名含"注射剂/原料药/制剂/口服"等 |

---

## 依赖

| 工具 | 作用 |
|-----|------|
| `opendataloader-pdf` Skill | PDF/Word 文档内容提取 |
| `graphify` (pip 包) | 知识图谱构建与查询 |
| `watchdog` (pip 包) | 文件系统监控，自动触发更新 |
| `openclaw agent` CLI | 后台执行 graphify 多步骤流程 |
| `graphify_job.py` | 作业队列管理 |
| `graphify_integration.py` | 图谱对接脚本 |
| `dify_integration.py` | Dify 对接脚本（骨架）|

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| **v2.8.0** | **2026-04-26** | **与opendataloader-pdf v2.8.0同步：Word真实页码/数字PDF逐页感知/Excel合并单元格/opendataloader升级** |
| **v3.0.0** | **2026-04-24** | **知识库管理器大版本升级（见commit 256e6f5）** |
| **v3.1.0** | **2026-04-25** | **内容哈希升级：PDF前两页逐页比对 + 提取失败自动重试** |
| **v2.12.0** | **2026-04-30** | **默认 --best-quality：所有入库文档强制 qwen2.5vl，不降级，失败即报错，确保知识库信息完整** |
| **v3.2.0** | **2026-04-25** | **PDF逐页自适应：digital页→opendataloader，scanned页→qwen2.5vl，混合页自动结合** |
| v2.1.0 | 2026-04-24 | 全自动 graphify 触发：job queue + cron + openclaw agent 后台执行 |
| v2.0.0 | 2026-04-24 | 去飞书 + graphify/dify 钩子 + watchdog 监控进程 |
| v1.0.0 | 2026-04-02 | 整合版：原始文件归档 + opendataloader 提取 + 索引更新 + 飞书同步 |
| v0.1.0 | 2026-04-02 | 初始版本（仅索引更新）|

---

## 配置项

```python
KB_ROOT = "/home/wangyc/Documents/工作/0 库/法规指导原则规定知识库"
DIR_RAW = "原始文件"
DIR_EXTRACTED = "供AI用信息"
INDEX_FILE = os.path.join(KB_ROOT, "guidance_index.json")
OPENDATALOADER_SCRIPT = "/home/wangyc/.openclaw/workspace/skills/opendataloader-pdf/scripts/opendataloader_auto.py"
GRAPHIFY_OUTPUT = os.path.join(KB_ROOT, "graphify-out")
JOB_QUEUE_DIR = os.path.join(os.path.dirname(__file__), "..", "jobs")
```
