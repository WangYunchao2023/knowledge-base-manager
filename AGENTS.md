# AGENTS.md - Workspace Protocol

## 核心准则 (Core Rules)
- **工具优先**: 网页访问、搜索、下载任务必须优先使用 `web-access` skill。
- **Skill 规范**: 严格执行 `SKILL.md` 指令，无需重复确认。任务开始前必须先读相关 Skill 文档。
- **文件操作**: `trash` > `rm`。严禁在未经许可的情况下外泄私有数据。
- **环境隔离**: 区分内部（工作空间内）与外部（发送邮件、公开贴）操作，外部操作需确认。

## 交流规范 (Communication)
- **群聊原则**: 仅在被提及、有价值输出、纠错或被要求总结时发言。保持社交礼仪，避免刷屏。
- **反应互动**: 自然使用 Emoji 回应。
- **格式要求**: Discord/WhatsApp 禁用 Markdown 表格，改用列表；WhatsApp 禁用标题级 Markdown。

## Workspace 根目录白名单（强制）

Workspace 根目录（`~/.openclaw/workspace/`）**只允许**以下文件/文件夹存在：

| 类型 | 白名单 |
|------|--------|
| 系统配置 | `SOUL.md`, `IDENTITY.md`, `USER.md`, `MEMORY.md`, `AGENTS.md`, `HEARTBEAT.md`, `BOOTSTRAP.md`, `TOOLS.md` |
| 核心目录 | `agents/`, `skills/`, `memory/`, `config/`, `docs/` |
| 辅助目录 | `avatars/`, `bin/`, `references/` |
| 临时工作 | `tmp/` |

**禁止在根目录出现的**：任何 `.py` 脚本、`*.skill/` 文件夹、`downloads/`、`graphify-out/`、`node_modules/`（保留现有）等临时/产物文件。

**规则**：
- 所有脚本执行、下载、网页抓取的产物，**必须**放在 `tmp/` 或 `~/Documents/工作/` 下
- 根目录出现白名单外文件时，**立即清理**，无需询问
- 如果某次任务需要新建持久目录（如 `outputs/`、`reports/`），统一放到 `~/Documents/工作/` 下，不要放在 workspace 根目录

## 任务与自动化 (Tasks & Automation)
- **Heartbeats**: 用于批量检查邮件、日历、天气等，非紧急情况不打扰。
- **Cron**: 用于精确时间提醒和隔离任务。
- **临时文件**: 存放在 `tmp/` 或 Skill 指定目录，任务结束后自动清理。

## 记忆维护 (Memory)
- **实时记录**: 存放在 `memory/YYYY-MM-DD.md`。
- **长期沉淀**: 定期提炼至 `MEMORY.md`。
- **原则**: 文本 > 大脑。所有重要决定、教训必须记录。

## 版本号管理 (Version Management)
- **三处必须同步**：每次升级版本号时，必须同时更新以下三处，缺一不可：
  1. **SKILL.md frontmatter** 的 `version:` 字段
  2. **scripts/*.py** 顶部的版本注释（如 `版本: x.x.x`）
  3. **Git**：执行 `git add → git commit → git tag v{x.x.x}`
- **Tag 永久性**：Tag 打完后不要再移动——每个版本 commit 都有唯一的永久标签
- **版本号递增**：禁止回退数字（如 3.9.1 废弃后，新开发从 3.9.2 开始）
- **版本一致即发布**：SKILL.md、web_access.py、Git tag 三者不一致时，视为"未发布"，必须先统一
