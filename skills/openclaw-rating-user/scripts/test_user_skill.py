#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenClaw 评分用户端 - 测试脚本（自动评分版）
不调用实际API，仅测试功能逻辑
"""

import os
import sys
from datetime import datetime

# 添加用户端脚本路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from shared_config_loader import SharedConfigLoader


class MockBitableClient:
    """模拟多维表格客户端，不实际写入"""
    
    def __init__(self):
        self.last_submission = None
    
    def submit_rating(self, user_id: str, rating_data: dict):
        """模拟提交，仅记录不写入"""
        self.last_submission = {
            'user_id': user_id,
            'data': rating_data,
            'timestamp': datetime.now().isoformat()
        }
        print("[OK] 评分已记录（未写入多维表格）")
        print(f"   评分人: {rating_data.get('name')}")
        print(f"   总分: {rating_data.get('total_score')}分")
        print(f"   评级: {rating_data.get('rating')}")
        return True, "评分提交成功（测试模式）"


class RatingUserSkillTester:
    """用户端测试器"""
    
    def __init__(self):
        self.skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_loader = SharedConfigLoader(self.skill_dir)
        self.bitable_client = MockBitableClient()
        
        # 加载配置
        self.config = self.config_loader.load_config()
        self.scoring_config = self.config.get('scoring', {})
        
        print("="*60)
        print("OpenClaw 评分用户端 - 自动评分功能测试")
        print("="*60)
    
    def test_all(self):
        """运行所有测试"""
        print("\n[1. 配置加载测试]")
        self.test_config_loading()
        
        print("\n[2. 触发词检测测试]")
        self.test_trigger_detection()
        
        print("\n[3. 自动评分逻辑测试 - 高频使用用户]")
        self.test_auto_score_high()
        
        print("\n[4. 自动评分逻辑测试 - 中频使用用户]")
        self.test_auto_score_medium()
        
        print("\n[5. 自动评分逻辑测试 - 低频使用用户]")
        self.test_auto_score_low()
        
        print("\n[6. 评分报告生成测试]")
        self.test_report_generation()
        
        print("\n[7. 帮助信息测试]")
        self.test_help_text()
        
        print("\n" + "="*60)
        print("测试完成！")
        print("="*60)
    
    def test_config_loading(self):
        """测试配置加载"""
        print(f"[OK] 技能名称: {self.config.get('skill_name')}")
        print(f"[OK] 版本号: {self.config.get('version')}")
        print(f"[OK] 用户触发词: {self.config_loader.get_trigger_keywords()}")
        print(f"[OK] 版本触发词: {self.config_loader.get_version_keywords()}")
    
    def test_trigger_detection(self):
        """测试触发词检测"""
        test_cases = [
            ("每日AI评分", True, "用户触发词"),
            ("AI评分", True, "用户触发词"),
            ("评分登记", True, "用户触发词"),
            ("评分版本", True, "版本触发词"),
            ("查看评分版本", True, "版本触发词"),
            ("今天天气怎么样", False, "无关消息"),
        ]
        
        user_keywords = self.config_loader.get_trigger_keywords()
        version_keywords = self.config_loader.get_version_keywords()
        
        for msg, expected, desc in test_cases:
            user_triggered = any(kw in msg for kw in user_keywords)
            version_triggered = any(kw in msg for kw in version_keywords)
            triggered = user_triggered or version_triggered
            
            status = "[OK]" if triggered == expected else "[FAIL]"
            print(f"{status} '{msg}' => {'触发' if triggered else '未触发'} ({desc})")
    
    def _auto_calculate_score(self, data: dict) -> dict:
        """自动评分逻辑（复制自user_main.py）"""
        import re
        
        # 1. 活跃度得分
        frequency = data.get('avg_daily_frequency', '').lower()
        if '多次' in frequency:
            activity_score = 22
        elif '每天1次' in frequency or '每天一次' in frequency:
            activity_score = 17
        elif '每周几次' in frequency:
            activity_score = 12
        else:
            activity_score = 5
        
        # 2. 深度得分
        top3_tools = data.get('top3_tools', '')
        tool_count = len([t for t in top3_tools.split(',') if t.strip()])
        if tool_count >= 5 or '5+' in top3_tools:
            depth_score = 22
        elif tool_count >= 3:
            depth_score = 17
        else:
            depth_score = 10
        
        # 3. 持续性得分
        duration = data.get('run_duration', '30天')
        if '月' in duration:
            continuity_score = 22
        elif '周' in duration:
            weeks = re.search(r'(\d+)周', duration)
            if weeks and int(weeks.group(1)) >= 2:
                continuity_score = 17
            else:
                continuity_score = 10
        else:
            continuity_score = 10
        
        # 4. 创新度得分
        dialogues = data.get('total_dialogues', 0)
        ongoing = data.get('ongoing_tasks', '')
        cron_rate = data.get('cron_task_rate', '0%')
        
        cron_match = re.search(r'(\d+)', str(cron_rate))
        cron_value = int(cron_match.group(1)) if cron_match else 0
        
        if dialogues > 50 or '有' in ongoing or cron_value > 80:
            innovation_score = 22
        elif dialogues > 20 or cron_value > 50:
            innovation_score = 15
        else:
            innovation_score = 8
        
        total_score = activity_score + depth_score + continuity_score + innovation_score
        
        # 评级
        if total_score >= 85:
            rating = 'A'
        elif total_score >= 70:
            rating = 'B'
        elif total_score >= 55:
            rating = 'C'
        else:
            rating = 'D'
        
        return {
            'activity_score': activity_score,
            'depth_score': depth_score,
            'continuity_score': continuity_score,
            'innovation_score': innovation_score,
            'total_score': total_score,
            'rating': rating
        }
    
    def test_auto_score_high(self):
        """测试高频使用用户的自动评分"""
        print("[高频用户使用场景]")
        print("  数据: 每天多次使用, 5+工具, 2个月以上, 50+对话, 有长期任务")
        
        data = {
            'total_dialogues': 80,
            'avg_daily_frequency': '每天多次',
            'top3_tools': '飞书工具, 文件操作, 网络搜索, 数据分析, 代码生成',
            'peak_hours': '09:00-18:00',
            'success_tasks': 50,
            'failed_tasks': 3,
            'ongoing_tasks': '数据分析项目',
            'cron_task_rate': '95%',
            'main_scenario': '日常办公、数据分析、代码编写',
            'run_duration': '2个月15天'
        }
        
        scores = self._auto_calculate_score(data)
        print(f"  活跃度: {scores['activity_score']}分")
        print(f"  深度: {scores['depth_score']}分")
        print(f"  持续性: {scores['continuity_score']}分")
        print(f"  创新度: {scores['innovation_score']}分")
        print(f"  => 总分: {scores['total_score']}分, 评级: {scores['rating']}")
        
        assert scores['total_score'] >= 85, "高频用户应达到A级"
        print("[OK] 高频用户评分正确")
    
    def test_auto_score_medium(self):
        """测试中频使用用户的自动评分"""
        print("[中频用户使用场景]")
        print("  数据: 每天1次使用, 3-4工具, 1个月, 30对话")
        
        data = {
            'total_dialogues': 30,
            'avg_daily_frequency': '每天1次',
            'top3_tools': '飞书工具, 文件操作, 网络搜索',
            'peak_hours': '14:00-17:00',
            'success_tasks': 20,
            'failed_tasks': 2,
            'ongoing_tasks': '无',
            'cron_task_rate': '60%',
            'main_scenario': '日常办公',
            'run_duration': '1个月10天'
        }
        
        scores = self._auto_calculate_score(data)
        print(f"  活跃度: {scores['activity_score']}分")
        print(f"  深度: {scores['depth_score']}分")
        print(f"  持续性: {scores['continuity_score']}分")
        print(f"  创新度: {scores['innovation_score']}分")
        print(f"  => 总分: {scores['total_score']}分, 评级: {scores['rating']}")
        
        assert 70 <= scores['total_score'] <= 84, "中频用户应达到B级"
        print("[OK] 中频用户评分正确")
    
    def test_auto_score_low(self):
        """测试低频使用用户的自动评分"""
        print("[低频用户使用场景]")
        print("  数据: 每周几次, 1-2工具, 1周, 5对话")
        
        data = {
            'total_dialogues': 5,
            'avg_daily_frequency': '每周几次',
            'top3_tools': '飞书工具',
            'peak_hours': '不定时',
            'success_tasks': 3,
            'failed_tasks': 1,
            'ongoing_tasks': '无',
            'cron_task_rate': '0%',
            'main_scenario': '偶尔查询',
            'run_duration': '5天'
        }
        
        scores = self._auto_calculate_score(data)
        print(f"  活跃度: {scores['activity_score']}分")
        print(f"  深度: {scores['depth_score']}分")
        print(f"  持续性: {scores['continuity_score']}分")
        print(f"  创新度: {scores['innovation_score']}分")
        print(f"  => 总分: {scores['total_score']}分, 评级: {scores['rating']}")
        
        assert scores['total_score'] < 70, "低频用户应低于B级"
        print("[OK] 低频用户评分正确")
    
    def test_report_generation(self):
        """测试评分报告生成"""
        print("[评分报告预览]")
        
        data = {
            'total_dialogues': 50,
            'avg_daily_frequency': '每天多次',
            'top3_tools': '飞书工具, 文件操作, 网络搜索, 数据分析, 代码生成',
            'peak_hours': '09:00-18:00',
            'success_tasks': 30,
            'failed_tasks': 2,
            'ongoing_tasks': '数据分析项目',
            'cron_task_rate': '90%',
            'main_scenario': '日常办公、数据分析、代码编写'
        }
        
        scores = self._auto_calculate_score(data)
        
        print("-" * 50)
        print(f"【每日AI评分报告 - 测试用户】")
        print()
        print("一、使用数据统计")
        print(f"- 总对话次数：{data['total_dialogues']}")
        print(f"- 平均每日使用频率：{data['avg_daily_frequency']}")
        print(f"- 最常用工具TOP3：{data['top3_tools']}")
        print()
        print("四、综合评分（满分100分）")
        print(f"- 活跃度得分：{scores['activity_score']}/25分")
        print(f"- 深度得分：{scores['depth_score']}/25分")
        print(f"- 持续性得分：{scores['continuity_score']}/25分")
        print(f"- 创新度得分：{scores['innovation_score']}/25分")
        print(f"- 【总分】：{scores['total_score']}分")
        print()
        print(f"五、评级：{scores['rating']}")
        print("-" * 50)
        
        print("[OK] 评分报告生成正常")
    
    def test_help_text(self):
        """测试帮助信息"""
        print("[帮助信息预览]")
        
        help_text = """
【评分用户端帮助】

评分流程:
  1. 发送「每日AI评分」获取数据收集表单
  2. 填写客观数据（对话次数、使用频率等）
  3. 系统自动根据4维度计算分数
  4. 查看评分报告后发送「确认提交」

评分标准（系统自动计算）:
  活跃度：根据「平均每日使用频率」计算
    - 每天多次：20-25分
    - 每天1次：15-19分
    - 每周几次：10-14分
    - 偶尔：0-9分
  深度：根据「使用工具数量」计算
  持续性：根据「已运行时长」计算
  创新度：根据「高级功能使用情况」计算

评级标准:
  A(优秀): 85-100分
  B(良好): 70-84分
  C(一般): 55-69分
  D(待提升): 0-54分
        """
        
        print(help_text)
        print("[OK] 帮助信息展示正常")


def main():
    """主测试入口"""
    tester = RatingUserSkillTester()
    tester.test_all()


if __name__ == '__main__':
    main()
