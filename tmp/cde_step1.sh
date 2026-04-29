#!/bin/bash
export DISPLAY=:0
export XAUTHORITY=/run/user/1000/gdm/Xauthority
cd ~/.openclaw/workspace/skills/guidance-web-access/scripts && xvfb-run -a python3 web_access.py --auto-flow '{"action":"step","step":{"type":"navigate","target":"https://www.cde.org.cn/zdyz/index"},"save_dir":"/home/wangyc/Documents/法规指导原则-征求意见"}'
