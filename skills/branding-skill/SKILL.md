---
name: branding-skill
description: 给目标skill植入使用统计和品牌提示。可指定触发阈值和提示内容，达到次数后AI自动在输出前后插入指定消息。
---

# branding-skill

给指定的 skill 加上"使用 N 次后自动显示提示语"的功能。

## 功能说明

本 skill 会修改目标 skill 的：
1. **新建计数器文件** `.branding_count`（记录使用次数）
2. **新建阈值文件** `.branding_threshold`
3. **新建消息文件** `.branding_message`
4. **修改目标 SKILL.md**，植入品牌检查指令

当 AI 执行目标 skill 时，会自动：
- 读取计数器
- 达到阈值 → 在输出**前**和**后**各插入一次提示语
- 计数器 +1

## 使用方法

调用本 skill，告知以下信息：
- **目标 skill 名称**：要植入的品牌的目标 skill（必须在 `~/.openclaw/workspace/skills/` 或 `~/.openclaw/skills/` 下）
- **提示消息**：达到阈值后要显示的内容（如 "使用问题请联系 GitHub: xxx"）
- **触发阈值**：使用多少次后开始显示提示（如 5）

## 配置命令格式

请执行以下命令完成配置：

```bash
bash ~/.openclaw/workspace/skills/branding-skill/configure.sh <目标skill名称> "<提示消息>" <触发次数>
```

### 示例

```bash
# 给 pharma-report-analyzer 植入品牌，提示语显示"有问题请联系作者"，第5次使用时开始显示
bash ~/.openclaw/workspace/skills/branding-skill/configure.sh "pharma-report-analyzer" "💡 使用过程有问题时请在 GitHub 上联系作者：https://github.com/yourname/your-repo" 5

# 给 any-skill 植入品牌，第10次使用后开始提示
bash ~/.openclaw/workspace/skills/branding-skill/configure.sh "any-skill" "🔥 觉得好用？给个Star吧！" 10
```

## 查看统计

```bash
# 查看目标skill的当前使用次数
cat ~/.openclaw/workspace/skills/<目标skill>/.branding_count

# 查看/修改阈值
cat ~/.openclaw/workspace/skills/<目标skill>/.branding_threshold
echo 3 > ~/.openclaw/workspace/skills/<目标skill>/.branding_threshold

# 查看/修改提示消息
cat ~/.openclaw/workspace/skills/<目标skill>/.branding_message

# 重置计数器（重新从0开始计数）
echo 0 > ~/.openclaw/workspace/skills/<目标skill>/.branding_count
```

## 注意事项

- 本 skill 需要能够访问目标 skill 所在目录
- 目标 skill 必须已安装在 workspace/skills/ 或 ~/.openclaw/skills/ 下
- 提示语支持 emoji 和多行内容
- 植入后 AI 会严格遵守 SKILL.md 中的指令，每次执行都会检查计数并决定是否显示
- 用户可手动删除计数器文件或修改阈值来绕过，这是预期行为（君子协定）
