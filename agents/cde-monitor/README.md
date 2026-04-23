# CDE指导原则监控Agent

## 基本信息
- **名称**: CDE Monitor
- **类型**: 定时任务Agent
- **用途**: 每日检查CDE官网新发布的指导原则,并自动阅读摘录

## 任务描述
详见 `task.md`

## Cron配置
- **运行时间**: 每天 08:30（北京时间）
- **状态**: 已启用

## 管理命令
```bash
# 手动运行
cron run --jobId <jobId>

# 查看cron任务
cron list

# 禁用/启用
cron update --jobId <jobId> --patch '{"enabled": false}'
```

## 更新日志
- 2026-03-16: 初始创建
