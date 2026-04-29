# Session: 2026-03-16 03:03:10 UTC

- **Session Key**: agent:cortana:main
- **Session ID**: 2c341ecf-0ca1-4259-9b79-1c41bef6fe7c
- **Source**: gateway:sessions.reset

## Conversation Summary

user: System: [2026-03-15 17:17:37 GMT+8] Exec failed (salty-wi, signal SIGTERM) :: /home/wangyc/.openclaw/agents/cortana2/sessions/sessions.json /home/wangyc/.openclaw/agents/cortana/sessions/sessions.json /home/wangyc/.openclaw/agents/policy-tracker/sessions/se…

Sender (untrusted metadata):
```json
{
  "label": "openclaw-tui (gateway-client)",
  "id": "gateway-client",
  "name": "openclaw-tui",
  "username": "openclaw-tui"
}
```

[Mon 2026-03-16 11:01 GMT+8] agent cortana (Cortana) | session main | unknown | tokens ?/200k 为什么打开TUI后显示这个，unknown等是错误吗？
assistant: 看到问题了！那个 `unknown/200k (?%)` **不是错误**，而是 token 统计暂时无法读取。

看表格里的数据：
- 有的 session 显示正常比例（如 `54%`, `23%`）
- 有的显示 `unknown/200k (?%)`

**可能原因：**

1. **Session 刚创建/结束** — 统计信息还没写入文件
2. **TUI 进程异常中断** — 没来得及写统计
3. **文件权限或读取问题** — 刚才那个 SIGTERM 可能导致部分 session 数据没保存

**这不影响正常使用** — 你的对话完全正常，只是统计展示有点延迟。

如果想强制刷新，可以重启 gateway：
```bash
openclaw gateway restart
```

要现在试试吗？💙
