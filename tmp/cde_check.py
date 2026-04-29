#!/usr/bin/env python3
import sys
import os

os.environ['DISPLAY'] = ':0'
os.environ['XAUTHORITY'] = '/run/user/1000/gdm/Xauthority'

sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/skills/guidance-web-access/scripts'))

from web_access import cortana_auto_flow
import json

result = cortana_auto_flow({
    'action': 'perceive',
    'initial_url': 'https://www.cde.org.cn/zdyz/index',
    'save_dir': os.path.expanduser('~/Documents/工作/指导原则更新'),
    'task': '查找2026年4月25日至4月26日发布的指导原则'
})

print(json.dumps(result, ensure_ascii=False, indent=2))
