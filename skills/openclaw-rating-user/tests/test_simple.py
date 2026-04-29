import json

# 模拟评分数据
data = {
    'total_dialogues': 15,
    'avg_daily_frequency': '每天多次',
    'top3_tools': 'feishu, file, search',
    'peak_hours': '09:00-14:00',
    'success_tasks': 12,
    'failed_tasks': 2,
    'ongoing_tasks': '有',
    'cron_task_rate': '90%',
    'main_scenario': '日常办公、自动化任务',
    'run_duration': '5天',
    'tools_count': 4
}

scores = {
    'activity_score': 23,
    'depth_score': 17,
    'continuity_score': 15,
    'innovation_score': 23,
    'total_score': 78,
    'rating': 'B',
    'overall_eval': '使用良好，活跃度很高，建议多尝试高级功能。'
}

print('=== Daily AI Rating Test Report ===')
print()
print('Auto-collected Data:')
print('  Dialogues:', data['total_dialogues'])
print('  Frequency:', data['avg_daily_frequency'])
print('  Tools:', data['top3_tools'])
print('  Duration:', data['run_duration'])
print('  Success:', data['success_tasks'])
print('  Failed:', data['failed_tasks'])
print()
print('Calculated Scores:')
print('  Activity:', scores['activity_score'])
print('  Depth:', scores['depth_score'])
print('  Continuity:', scores['continuity_score'])
print('  Innovation:', scores['innovation_score'])
print('  Total:', scores['total_score'])
print('  Rating:', scores['rating'])
print()
print('Overall Evaluation:')
print(' ', scores['overall_eval'])
print()
print('=== Test Complete ===')

# Save to file
with open('test_result.json', 'w', encoding='utf-8') as f:
    json.dump({'data': data, 'scores': scores}, f, ensure_ascii=False, indent=2)

print('Results saved to test_result.json')
