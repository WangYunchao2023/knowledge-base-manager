#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime

def export_local_log(log_path, output_path, session_id, workspace_path):
    """
    直接读取 OpenClaw 本地日志文件 (jsonl 格式) 并渲染为规范的 Markdown
    """
    if not os.path.exists(log_path):
        print(f"Error: Log file {log_path} not found.")
        return

    start_time = "Unknown"
    messages = []

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    # 提取开始时间 (通常在第一条消息或 meta 中)
                    if not start_time and 'time' in data:
                        start_time = data['time']
                    
                    # 提取对话内容 (忽略工具调用细节，只保留用户和助手的正文)
                    if data.get('role') in ['user', 'assistant'] and data.get('content'):
                        messages.append({
                            'role': "用户" if data['role'] == 'user' else "助手",
                            'time': data.get('time', ''),
                            'content': data['content']
                        })
                except json.JSONDecodeError:
                    continue

        # 开始渲染 Markdown
        md_content = f"""# 📄 完整会话记录: {session_id}

<span style="background-color: yellow; color: black;">**Session ID**: {session_id}</span>
<span style="background-color: yellow; color: black;">**工作目录**: {workspace_path}</span>
<span style="background-color: yellow; color: black;">**开始时间**: {start_time}</span>
<span style="background-color: yellow; color: black;">**日期**: {datetime.now().strftime('%Y-%m-%d')}</span>

---

"""
        for msg in messages:
            md_content += f"### **[{msg['time']}] {msg['role']}**:\n{msg['content']}\n\n---\n\n"

        end_time = datetime.now().isoformat()
        md_content += f"""
<span style="background-color: yellow; color: black;">**会话结束**</span>
<span style="background-color: yellow; color: black;">**Session ID**: {session_id}</span>
<span style="background-color: yellow; color: black;">**结束时间**: {end_time}</span>
"""

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"Successfully exported {len(messages)} messages to {output_path}")

    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python3 exporter_engine.py <log_path> <output_path> <session_id> <workspace_path>")
    else:
        export_local_log(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
