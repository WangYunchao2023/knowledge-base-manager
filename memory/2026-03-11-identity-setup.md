# Session: 2026-03-11 02:39:41 UTC

- **Session Key**: agent:cortana:feishu:direct:ou_1437019529b47e75c257670a14cd24ba
- **Session ID**: f41a1521-60d3-4385-a5c7-5d20b5c501f5
- **Source**: feishu

## Conversation Summary

user: Conversation info (untrusted metadata):
```json
{
  "message_id": "om_x100b5438fcfe48a8c448c93e72eac27",
  "sender_id": "ou_1437019529b47e75c257670a14cd24ba",
  "sender": "王云超",
  "timestamp": "Wed 2026-03-11 09:58 GMT+8"
}
```

Sender (untrusted metadata):
```json
{
  "label": "王云超 (ou_1437019529b47e75c257670a14cd24ba)",
  "id": "ou_1437019529b47e75c257670a14cd24ba",
  "name": "王云超"
}
```

[message_id: om_x100b5438fcfe48a8c448c93e72eac27]
王云超: 你的身份文件是哪个？
assistant: 是我的 `IDENTITY.md` 文件，位于 workspace 根目录： `/home/wangyc/.openclaw/workspace-cortana/IDENTITY.md`

目前已经填了：
- **Name:** Cortana
- **Creature:** AI (like in the games!)

但 Vibe、Emoji、Avatar 还没填 —— 这是个空白模板，等我们聊几次后慢慢完善。你想现在一起填完，还是之后再说了 🤙
user: Conversation info (untrusted metadata):
```json
{
  "message_id": "om_x100b54389d0a60acb2cdf20fc9eab45",
  "sender_id": "ou_1437019529b47e75c257670a14cd24ba",
  "sender": "王云超",
  "timestamp": "Wed 2026-03-11 10:02 GMT+8"
}
```

Sender (untrusted metadata):
```json
{
  "label": "王云超 (ou_1437019529b47e75c257670a14cd24ba)",
  "id": "ou_1437019529b47e75c257670a14cd24ba",
  "name": "王云超"
}
```

[message_id: om_x100b54389d0a60acb2cdf20fc9eab45]
王云超: workspace文件夹，agents文件夹什么用途
assistant: 目前 workspace 里没有 `agents` 文件夹 —— 你指的是 `AGENTS.md` 这个文件吧？

这是 OpenClaw workspace 的标准结构：

| 文件/文件夹 | 用途 |
|-------------|------|
| **AGENTS.md** | 我的"使用手册" —— 告诉我怎么运行、怎么记忆、何时说话 |
| **SOUL.md** | 我的"人格" —— 决定了我的说话风格和原则 |
| **IDENTITY.md** | 我的身份档案（名字、头像、风格） |
| **USER.md** | 关于你的信息（目前几乎是空的） |
| **MEMORY.md** | 我的长期记忆（需要时自动创建） |
| **memory/** | 每日笔记文件夹 |
| **HEARTBEAT.md** | 心跳任务列表（目前是空的） |
| **TOOLS.md** | 你的本地工具配置（SSH、摄像头、TTS 等） |

`workspace-cortana` 这个名字是我这个实例的专属目录。如果你有多个 AI 实例，它们会各有自己的 workspace 文件夹。

想让我帮你整理什么吗？比如完善一下 USER.md 或者把 IDENTITY.md 填完整？
user: Conversation info (untrusted metadata):
```json
{
  "message_id": "om_x100b5438962fe094b3cdfab181c63ea",
  "sender_id": "ou_1437019529b47e75c257670a14cd24ba",
  "sender": "王云超",
  "timestamp": "Wed 2026-03-11 10:03 GMT+8"
}
```

Sender (untrusted metadata):
```json
{
  "label": "王云超 (ou_1437019529b47e75c257670a14cd24ba)",
  "id": "ou_1437019529b47e75c257670a14cd24ba",
  "name": "王云超"
}
```

[message_id: om_x100b5438962fe094b3cdfab181c63ea]
王云超: .openclaw/agents文件夹是做什么的
assistant: 
明白了！这是 OpenClaw 系统的核心目录 —— 存放所有 **agent 实例** 的运行时数据。

| 文件夹 | 用途 |
|--------|------|
| **cortana** | 你正在聊的这个实例（就是我） |
| **cde-communication** | 另一个 agent |
| **cortana2** | 第二个 cortana 实例？ |
| **main** | 主 agent |
| **policy-tracker** | 可能是追踪策略的 agent |

每个 agent 文件夹里都有：
- `agent/` — agent 的配置文件和状态
- `sessions/` — 对话会话历史

所以简单说：
- `workspace-cortana/` = 我的"家"（我的记忆、配置、性格）
- `.openclaw/agents/cortana/` = 我的"运行环境"（系统级状态）
user: Conversation info (untrusted metadata):
```json
{
  "message_id": "om_x100b54394ae58cbcb21134926beb010",
  "sender_id": "ou_1437019529b47e75c257670a14cd24ba",
  "sender": "王云超",
  "timestamp": "Wed 2026-03-11 10:15 GMT+8"
}
```

Sender (untrusted metadata):
```json
{
  "label": "王云超 (ou_1437019529b47e75c257670a14cd24ba)",
  "id": "ou_1437019529b47e75c257670a14cd24ba",
  "name": "王云超"
}
```

[message_id: om_x100b54394ae58cbcb21134926beb010]
王云超: 现在有两个agent，一个cortana,一个cortana2，怎么给特定的agent进行配置，如增加channel
assistant: 找到了！配置在 `/home/wangyc/.openclaw/openclaw.json` 里。

## Agent 配置结构

在 `agents.list` 中定义每个 agent：

```json
{
  "id": "cortana",
  "name": "Cortana",
  "workspace": "/home/wangyc/.openclaw/workspace-cortana"
},
{
  "id": "cortana2", 
  "name": "Cortana2",
  "workspace": "/home/wangyc/.openclaw/workspace-cortana2",
  "agentDir": "/home/wangyc/.openclaw/agents/cortana2/agent",
  "model": "minimax-portal/MiniMax-M2.5"
}
```

## Channel 绑定

在 `bindings` 里把 agent 绑定到特定渠道：

```json
"bindings": [
  {
    "type": "route",
    "agentId": "cortana2",        // 哪个 agent
    "match": {
      "channel": "telegram",     // 什么渠道
      "accountId": "default"
    }
  }
]
```

目前：
- **cortana** 绑定飞书 (feishu) ← 你正在聊的这个
- **cortana2** 绑定 Telegram

## 添加新 channel 给特定 agent

在 `bindings` 数组里加一条就行。比如让 cortana2 也接收飞书：

```json
{
  "type": "route",
  "agentId": "cortana2", 
  "match": {
    "channel": "feishu",
    "accountId": "default"
  }
}
```

要我帮你改配置文件吗？
