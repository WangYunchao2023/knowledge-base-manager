---
name: session-exporter
description: 按用户指定的规范（黄色高亮头尾、Session ID、完整问答流）将当前会话导出为 .md 文件。
---

# SKILL.md - 会话完整版导出 (Session Exporter)

## 🎯 核心目标
按用户指定的规范（黄色高亮头尾、Session ID、完整问答流）将当前会话导出为 `.md` 文件。

## ⚙️ 核心逻辑
- **导出路径**: 用户指定或 Skill 默认。
- **格式规范**: 
  - 开头/结尾必须包含黄色高亮的 Session ID、工作目录、起止时间。
  - 必须按原始问答顺序完整保存，不得缩略、不得截断。
- **执行方式**: 调用同目录下的 `export_session.py` 脚本进行处理。

## 🛠️ 调用流 (Workflows)
1. **识别需求**: 当用户要求“保存会话”、“完整导出”时。
2. **提取上下文**: 读取会话日志（来自系统日志目录或 API）。
3. **调用脚本**: 
   ```bash
   python3 export_session.py <session_id> <output_path> <workspace_path>
   ```
4. **验证输出**: 确保生成的文件包含所有要求的信息。

## ⚠️ 约束
- 严禁对回答内容进行总结或缩略。
- 必须包含所有决策细节。
