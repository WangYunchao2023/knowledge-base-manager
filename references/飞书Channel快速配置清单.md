# 飞书 Channel 快速配置清单

## 当前环境信息

```
工作目录: ~/workspace-cortana
Gateway 配置文件: ~/.openclaw/openclaw.json
Gateway 服务文件: ~/.config/systemd/user/openclaw-gateway.service
飞书日志: /tmp/openclaw/openclaw-YYYY-MM-DD.log
```

## 快速配置检查 (Agent 可执行)

### 1. 确认正确的 App ID

当前配置 (cortana):
- App ID: `cli_a92660c6cf781cc4`
- App Secret: `KKEPmlfu6TVA3dZsl2TJwcVf6QLQX4dL`

检查命令:
```bash
cat ~/.openclaw/openclaw.json | jq '.channels.feishu.appId'
```

### 2. 清除代理问题

检查是否有 29290 代理:
```bash
grep "29290" ~/.config/kioslaverc
grep "29290" ~/.config/systemd/user/openclaw-gateway.service
grep "ECONNREFUSED.*29290" /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log
```

清除代理:
```bash
# 1. 清理 kioslaverc
sed -i 's|httpProxy=|#httpProxy=|g; s|httpsProxy=|#httpsProxy=|g' ~/.config/kioslaverc

# 2. 重写 Gateway 服务，确保有 NO_PROXY=*
cat > ~/.config/systemd/user/openclaw-gateway.service << 'EOF'
[Service]
ExecStart=...
Environment=NO_PROXY=*
...
EOF

# 3. 重启
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway
```

### 3. 验证飞书连接

检查日志:
```bash
# 无代理错误
grep "ECONNREFUSED.*29290" /tmp/openclaw/openclaw-*.log | tail -3

# WebSocket 连接成功
grep "websocket started" /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log | tail -3

# 消息接收成功
grep "received message" /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log | tail -3
```

### 4. 飞书开放平台配置确认

需要确认:
- [ ] 应用类型: 自建应用 (self-build)
- [ ] 权限: im:message, im:message:send_as_bot
- [ ] 事件订阅方式: 长连接模式
- [ ] 事件: im.message.receive_v1
- [ ] 已发布

---

## 修复流程 (按顺序执行)

1. 检查 appId 是否正确 (`cli_a92660c6cf781cc4`)
2. 检查并清除代理 (29290 端口问题)
3. 确认飞书后台长连接配置
4. 重启 Gateway
5. 验证消息接收
