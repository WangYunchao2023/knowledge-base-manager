#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime

def export_session(session_id, output_path, workspace_path):
    # 注意：在 OpenClaw 环境中，会话通常存储在 ~/.codex/sessions/ 或通过 API 获取
    # 此脚本作为一个模板，演示如何按用户要求的格式组装 Markdown
    
    # 模拟获取会话数据 (实际运行时由 Skill 注入或读取日志)
    # 这里我们定义导出的结构规范
    
    start_time = datetime.now().isoformat() # 示例
    
    md_output = f"""# 📄 完整会话记录: {session_id}

<span style="background-color: yellow; color: black;">**Session ID**: {session_id}</span>
<span style="background-color: yellow; color: black;">**工作目录**: {workspace_path}</span>
<span style="background-color: yellow; color: black;">**开始时间**: {start_time}</span>
<span style="background-color: yellow; color: black;">**日期**: {datetime.now().strftime('%Y-%m-%d')}</span>

---

"""
    # 这里逻辑上应该循环处理消息队列
    # for msg in messages:
    #     role = "用户" if msg['role'] == 'user' else "助手"
    #     md_output += f"### **[{msg['time']}] {role}**:\n{msg['content']}\n\n---\n\n"

    md_output += f"""
<span style="background-color: yellow; color: black;">**会话结束**</span>
<span style="background-color: yellow; color: black;">**Session ID**: {session_id}</span>
<span style="background-color: yellow; color: black;">**结束时间**: {datetime.now().isoformat()}</span>
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_output)
    
    print(f"Successfully exported session to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: export_session.py <session_id> <output_path> <workspace_path>")
    else:
        export_session(sys.argv[1], sys.argv[2], sys.argv[3])
