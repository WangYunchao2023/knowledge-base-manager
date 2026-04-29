import sys
import os
sys.path.insert(0, 'scripts')

from user_main import RatingUserSkill

skill = RatingUserSkill()

# 使用今天的实际对话数据
today_messages = [
    {'sender': {'id': 'ou_9b6700282aa925e38877623705a5c58e'}, 'content': '小秘，在不在', 'create_time': '2026-03-26T13:42:50+08:00'},
    {'sender': {'id': 'bot'}, 'content': '在的', 'create_time': '2026-03-26T13:43:00+08:00'},
    {'sender': {'id': 'ou_9b6700282aa925e38877623705a5c58e'}, 'content': '每日AI评分', 'create_time': '2026-03-26T13:43:59+08:00'},
    {'sender': {'id': 'ou_9b6700282aa925e38877623705a5c58e'}, 'content': '每日AI评分', 'create_time': '2026-03-26T13:44:36+08:00'},
    {'sender': {'id': 'ou_9b6700282aa925e38877623705a5c58e'}, 'content': '每日AI评分', 'create_time': '2026-03-26T13:51:40+08:00'},
    {'sender': {'id': 'ou_9b6700282aa925e38877623705a5c58e'}, 'content': '你是不是搞错了', 'create_time': '2026-03-26T13:54:51+08:00'},
    {'sender': {'id': 'ou_9b6700282aa925e38877623705a5c58e'}, 'content': '我们现在是在测试昨晚的做的Skill', 'create_time': '2026-03-26T13:55:30+08:00'},
    {'sender': {'id': 'ou_9b6700282aa925e38877623705a5c58e'}, 'content': '用户端和管理端的提示词是什么', 'create_time': '2026-03-26T13:55:30+08:00'},
    {'sender': {'id': 'ou_9b6700282aa925e38877623705a5c58e'}, 'content': '每日AI评分', 'create_time': '2026-03-26T13:55:30+08:00'},
    {'sender': {'id': 'ou_9b6700282aa925e38877623705a5c58e'}, 'content': 'Token写入配置表', 'create_time': '2026-03-26T13:58:43+08:00'},
    {'sender': {'id': 'ou_9b6700282aa925e38877623705a5c58e'}, 'content': '写入评分数据', 'create_time': '2026-03-26T14:00:13+08:00'},
    {'sender': {'id': 'ou_9b6700282aa925e38877623705a5c58e'}, 'content': '姓名怎么错了', 'create_time': '2026-03-26T14:02:20+08:00'},
    {'sender': {'id': 'ou_9b6700282aa925e38877623705a5c58e'}, 'content': '你要记住，不能用别名', 'create_time': '2026-03-26T14:02:55+08:00'},
    {'sender': {'id': 'ou_9b6700282aa925e38877623705a5c58e'}, 'content': '每日AI评分', 'create_time': '2026-03-26T14:03:25+08:00'},
]

data = skill.collect_user_data_from_messages(today_messages)
scores = skill.auto_calculate_score(data)

print('=== Daily AI Rating Report ===')
print()
print('User: 林丰丰')
print('Date: 2026-03-26')
print()
print('Usage Statistics:')
print('  Dialogues:', data['total_dialogues'])
print('  Frequency:', data['avg_daily_frequency'])
print('  Tools:', data['top3_tools'])
print('  Peak Hours:', data['peak_hours'])
print()
print('Task Completion:')
print('  Success:', data['success_tasks'])
print('  Failed:', data['failed_tasks'])
print('  Long-term:', data['ongoing_tasks'])
print()
print('Scores:')
print('  Activity:', scores['activity_score'], '/25')
print('  Depth:', scores['depth_score'], '/25')
print('  Continuity:', scores['continuity_score'], '/25')
print('  Innovation:', scores['innovation_score'], '/25')
print('  Total:', scores['total_score'], '/100')
print('  Rating:', scores['rating'])
print()
print('Evaluation:', scores['overall_eval'])

# Save results
result = {
    'user': '林丰丰',
    'open_id': 'ou_9b6700282aa925e38877623705a5c58e',
    'date': '2026-03-26',
    'data': data,
    'scores': scores
}

import json
with open('today_rating.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print()
print('Results saved to today_rating.json')
