#!/bin/bash
export DISPLAY=:0
export XAUTHORITY=/run/user/1000/gdm/Xauthority
cd ~/.openclaw/workspace/skills/guidance-web-access/scripts
python web_access.py --auto-flow '{
  "action": "perceive",
  "initial_url": "https://www.cde.org.cn/zdyz/index",
  "save_dir": "~/Documents/工作/指导原则更新",
  "task": "查找2026年4月25日至4月26日发布的指导原则"
}'
