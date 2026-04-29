#!/bin/bash
export DISPLAY=:0
export XAUTHORITY=/run/user/1000/gdm/Xauthority
cd ~/.openclaw/workspace/skills/guidance-web-access/scripts && xvfb-run -a python3 web_access.py --auto-flow '{"action":"perceive","initial_url":"https://www.cde.org.cn","save_dir":"/home/wangyc/Documents/法规指导原则-征求意见"}'
