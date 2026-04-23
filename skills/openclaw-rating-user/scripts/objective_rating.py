#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
客观评分算法 - 基于真实交互记录
"""

from datetime import datetime
import json

def calculate_objective_rating(messages_data):
    """
    基于真实交互数据计算客观评分
    
    评分维度：
    1. 活跃度 (25分): 基于对话次数、交互频率
    2. 深度 (25分): 基于使用的工具/功能种类
    3. 持续性 (25分): 基于使用时长和历史记录
    4. 创新度 (25分): 基于是否使用高级功能
    """
    
    # 1. 活跃度计算 (0-25分)
    # 基于对话次数和频率
    user_message_count = messages_data.get('user_message_count', 0)
    bot_response_count = messages_data.get('bot_response_count', 0)
    interaction_rounds = min(user_message_count, bot_response_count)
    
    if interaction_rounds >= 15:
        activity_score = 23  # 高频使用
    elif interaction_rounds >= 10:
        activity_score = 20  # 较高频
    elif interaction_rounds >= 6:
        activity_score = 16  # 中等
    elif interaction_rounds >= 3:
        activity_score = 12  # 较低
    else:
        activity_score = 8   # 低频
    
    # 2. 深度计算 (0-25分)
    # 基于使用的工具种类
    tools_used = messages_data.get('tools_used', [])
    tool_count = len(set(tools_used))
    
    if tool_count >= 5:
        depth_score = 22
    elif tool_count >= 4:
        depth_score = 19
    elif tool_count >= 3:
        depth_score = 16
    elif tool_count >= 2:
        depth_score = 13
    else:
        depth_score = 10
    
    # 3. 持续性计算 (0-25分)
    # 基于使用时长
    days_since_start = messages_data.get('days_since_start', 1)
    
    if days_since_start >= 30:
        continuity_score = 23
    elif days_since_start >= 14:
        continuity_score = 19
    elif days_since_start >= 7:
        continuity_score = 16
    else:
        continuity_score = 13
    
    # 4. 创新度计算 (0-25分)
    # 基于高级功能使用
    advanced_features = messages_data.get('advanced_features', [])
    has_cron = 'cron' in advanced_features
    has_long_term = 'long_term' in advanced_features
    has_custom_skill = 'custom_skill' in advanced_features
    
    innovation_score = 10  # 基础分
    if has_cron:
        innovation_score += 5
    if has_long_term:
        innovation_score += 5
    if has_custom_skill:
        innovation_score += 5
    
    # 根据工具深度额外加分
    if tool_count >= 3:
        innovation_score += 3
    if tool_count >= 5:
        innovation_score += 2
    
    innovation_score = min(innovation_score, 25)  # 封顶25分
    
    # 计算总分
    total_score = activity_score + depth_score + continuity_score + innovation_score
    
    # 确定评级
    if total_score >= 85:
        rating = 'A'
        rating_desc = '优秀'
    elif total_score >= 70:
        rating = 'B'
        rating_desc = '良好'
    elif total_score >= 55:
        rating = 'C'
        rating_desc = '一般'
    else:
        rating = 'D'
        rating_desc = '待提升'
    
    # 生成综合评价
    evaluations = []
    
    # 活跃度评价
    if activity_score >= 20:
        evaluations.append("使用频繁")
    elif activity_score >= 15:
        evaluations.append("使用活跃")
    else:
        evaluations.append("使用较少")
    
    # 深度评价
    if depth_score >= 18:
        evaluations.append("工具运用深入")
    elif depth_score >= 14:
        evaluations.append("工具运用适中")
    else:
        evaluations.append("工具运用较浅")
    
    # 创新度评价
    if innovation_score >= 18:
        evaluations.append("善用高级功能")
    elif innovation_score >= 12:
        evaluations.append("有一定创新")
    else:
        evaluations.append("可尝试更多功能")
    
    overall_eval = "，".join(evaluations) + "。"
    
    return {
        'activity_score': activity_score,
        'depth_score': depth_score,
        'continuity_score': continuity_score,
        'innovation_score': innovation_score,
        'total_score': total_score,
        'rating': rating,
        'rating_desc': rating_desc,
        'overall_eval': overall_eval,
        'details': {
            'user_messages': user_message_count,
            'bot_responses': bot_response_count,
            'tools_used': list(set(tools_used)),
            'tool_count': tool_count,
            'days_active': days_since_start,
            'advanced_features': advanced_features
        }
    }


def analyze_today_interactions():
    """
    分析今天实际的交互数据
    """
    # 今天实际的交互记录
    today_interactions = [
        {'time': '13:42:50', 'type': 'user', 'content': '小秘，在不在'},
        {'time': '13:43:00', 'type': 'bot', 'content': '在的'},
        {'time': '13:43:59', 'type': 'user', 'content': '每日AI评分'},
        {'time': '13:44:36', 'type': 'user', 'content': '每日AI评分'},
        {'time': '13:51:40', 'type': 'user', 'content': '每日AI评分'},
        {'time': '13:54:51', 'type': 'user', 'content': '你是不是搞错了'},
        {'time': '13:55:30', 'type': 'user', 'content': '我们现在是在测试昨晚的做的Skill'},
        {'time': '13:55:30', 'type': 'user', 'content': '用户端和管理端的提示词是什么'},
        {'time': '13:55:30', 'type': 'user', 'content': '每日AI评分'},
        {'time': '13:58:43', 'type': 'user', 'content': 'Token写入配置表'},
        {'time': '14:00:13', 'type': 'user', 'content': '写入评分数据'},
        {'time': '14:02:20', 'type': 'user', 'content': '姓名怎么错了'},
        {'time': '14:02:55', 'type': 'user', 'content': '你要记住，不能用别名'},
        {'time': '14:03:25', 'type': 'user', 'content': '每日AI评分'},
        {'time': '14:05:34', 'type': 'user', 'content': '不是写入MEMORY.md'},
        {'time': '14:06:27', 'type': 'user', 'content': '这个SKILL要分发给其他评分的'},
        {'time': '14:07:53', 'type': 'user', 'content': '你这个评分的分数要客观一些'},
    ]
    
    # 统计用户消息数
    user_messages = [m for m in today_interactions if m['type'] == 'user']
    bot_responses = [m for m in today_interactions if m['type'] == 'bot']
    
    # 检测使用的工具/功能
    tools_used = []
    advanced_features = []
    
    for msg in today_interactions:
        content = msg['content']
        
        # 检测工具使用
        if '评分' in content or 'Skill' in content:
            tools_used.append('rating_skill')
        if 'Token' in content or '配置表' in content:
            tools_used.append('feishu_bitable')
        if 'MEMORY' in content or 'SKILL' in content:
            tools_used.append('skill_management')
        if '评分' in content and ('分' in content or '数据' in content):
            tools_used.append('data_analysis')
        if '写入' in content or '更新' in content:
            tools_used.append('file_operation')
    
    # 检测高级功能
    if any('定时' in m['content'] or 'cron' in m['content'].lower() for m in user_messages):
        advanced_features.append('cron')
    if any('长期' in m['content'] for m in user_messages):
        advanced_features.append('long_term')
    if any('Skill开发' in m['content'] or 'SKILL' in m['content'] for m in user_messages):
        advanced_features.append('custom_skill')
    
    return {
        'user_message_count': len(user_messages),
        'bot_response_count': len(bot_responses),
        'tools_used': tools_used,
        'advanced_features': advanced_features,
        'days_since_start': 6  # 从2026-03-20开始
    }


if __name__ == '__main__':
    # 分析今天的实际交互
    data = analyze_today_interactions()
    
    # 计算客观评分
    result = calculate_objective_rating(data)
    
    print('=== 客观评分报告 ===')
    print()
    print('用户: 林丰丰')
    print('日期: 2026-03-26')
    print()
    print('实际交互统计:')
    print('  用户消息数:', result['details']['user_messages'])
    print('  机器人回复:', result['details']['bot_responses'])
    print('  交互轮次:', min(result['details']['user_messages'], result['details']['bot_responses']))
    print()
    print('使用的工具/功能:')
    for tool in result['details']['tools_used']:
        print('   -', tool)
    print('  工具种类数:', result['details']['tool_count'])
    print()
    print('高级功能:')
    for feat in result['details']['advanced_features']:
        print('   -', feat)
    print()
    print('评分结果:')
    print('  活跃度:', result['activity_score'], '/25')
    print('  深度:', result['depth_score'], '/25')
    print('  持续性:', result['continuity_score'], '/25')
    print('  创新度:', result['innovation_score'], '/25')
    print('  总分:', result['total_score'], '/100')
    print('  评级:', result['rating'], '(', result['rating_desc'], ')')
    print()
    print('综合评价:', result['overall_eval'])
    
    # 保存结果
    with open('objective_rating.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
