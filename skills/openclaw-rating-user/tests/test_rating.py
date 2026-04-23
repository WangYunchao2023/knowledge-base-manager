#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评分系统测试脚本 - 简化版
"""

import sys
import os

# 添加scripts目录到路径
scripts_dir = os.path.join(os.path.dirname(__file__), '..', 'scripts')
sys.path.insert(0, scripts_dir)

from user_main import RatingUserSkill

def test_rating():
    """测试评分功能"""
    skill = RatingUserSkill()
    
    # 使用默认数据
    data = skill._get_default_data()
    data['total_dialogues'] = 15  # 今日对话次数
    data['avg_daily_frequency'] = '每天多次'
    data['top3_tools'] = 'feishu, file, search'
    data['peak_hours'] = '09:00-14:00'
    data['success_tasks'] = 12
    data['failed_tasks'] = 2
    data['ongoing_tasks'] = '有'
    data['cron_task_rate'] = '90%'
    data['main_scenario'] = '日常办公、自动化任务'
    data['run_duration'] = '5天'
    data['tools_count'] = 4
    
    scores = skill.auto_calculate_score(data)
    
    print('=== 每日AI评分测试报告 ===')
    print()
    print('自动收集的数据:')
    print(f'  对话次数: {data[\"total_dialogues\"]}')
    print(f'  使用频率: {data[\"avg_daily_frequency\"]}')
    print(f'  使用工具: {data[\"top3_tools\"]}')
    print(f'  运行时长: {data[\"run_duration\"]}')
    print(f'  成功任务: {data[\"success_tasks\"]}')
    print(f'  失败任务: {data[\"failed_tasks\"]}')
    print()
    print('自动计算的评分:')
    print(f'  活跃度: {scores[\"activity_score\"]}分')
    print(f'  深度: {scores[\"depth_score\"]}分')
    print(f'  持续性: {scores[\"continuity_score\"]}分')
    print(f'  创新度: {scores[\"innovation_score\"]}分')
    print(f'  总分: {scores[\"total_score\"]}分')
    print(f'  评级: {scores[\"rating\"]}')
    print()
    print('综合评价:')
    print(f'  {scores[\"overall_eval\"]}')
    print()
    print('=== 测试完成 ===')
    
    return scores

if __name__ == '__main__':
    scores = test_rating()
    # 保存到文件
    import json
    with open('test_result.json', 'w', encoding='utf-8') as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)
    print()
    print('评分结果已保存到 test_result.json')
