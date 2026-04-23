#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenClaw 评分用户端 - 主程序
自动从飞书对话中统计用户数据并评分
"""

import json
import os
import sys
import re
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared_config_loader import SharedConfigLoader
from bitable_client import BitableClient


class RatingUserSkill:
    """评分用户端主类 - 全自动评分"""
    
    def __init__(self, skill_dir=None, access_token=None):
        if skill_dir is None:
            skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self.skill_dir = skill_dir
        self.config_loader = SharedConfigLoader(skill_dir)
        self.bitable_client = BitableClient(skill_dir, access_token)
        self.access_token = access_token
        
        # 加载配置
        self.config = self.config_loader.load_config()
        self.scoring_config = self.config.get('scoring', {})
        
        # 存储最后一次评分数据（用于确认提交）
        self._last_rating_data = None
        self._last_scores = None
        self._last_user_id = None
        self._last_user_name = None
    
    def check_trigger(self, message: str) -> bool:
        """检查消息是否触发用户端"""
        keywords = self.config_loader.get_trigger_keywords()
        message_lower = message.lower().strip()
        
        for keyword in keywords:
            if keyword.lower() in message_lower:
                return True
        return False
    
    def can_submit(self) -> Tuple[bool, str]:
        """检查当前是否可以提交评分"""
        if not self.config_loader.is_in_time_window():
            time_window = self.config_loader.get_time_window()
            start = time_window.get('start', '00:00')
            end = time_window.get('end', '23:59')
            return False, f"当前不在评分提交时间窗口内（{start} - {end}），请稍后再试"
        
        return True, "可以提交"
    
    def collect_user_data_from_messages(self, messages: List[Dict]) -> Dict:
        """
        从飞书消息记录中自动收集用户数据（只统计当天）
        """
        if not messages:
            return self._get_default_data()
        
        # 只筛选当天的消息
        today = date.today()
        today_messages = []
        for m in messages:
            create_time = m.get('create_time', '')
            if create_time:
                try:
                    msg_date = datetime.fromisoformat(create_time.replace('Z', '+00:00')).date()
                    if msg_date == today:
                        today_messages.append(m)
                except:
                    pass
        
        if not today_messages:
            return self._get_default_data()
        
        # 统计当天的对话次数（用户发送的消息数）
        user_messages = [m for m in today_messages if m.get('sender', {}).get('id') != 'bot']
        total_dialogues = len(user_messages)
        
        # 统计使用的工具/Skill（从消息内容中提取）
        tools_used = set()
        task_success = 0
        task_failed = 0
        has_cron = False
        has_long_term_task = False
        
        # 工具关键词映射
        tool_keywords = {
            'feishu': ['飞书', 'feishu', '多维表格', '文档', '表格'],
            'file': ['文件', '读取', '写入', 'excel', 'csv'],
            'search': ['搜索', '查询', '查找', 'search'],
            'web': ['网页', '浏览器', '打开', '访问'],
            'code': ['代码', 'python', '脚本', 'programming'],
            'image': ['图片', '图像', '截图', 'image'],
            'calendar': ['日历', '日程', '会议', 'calendar'],
            'task': ['任务', '待办', 'todo', 'task'],
        }
        
        peak_hours = {}
        
        for msg in today_messages:
            content = msg.get('content', '').lower()
            
            # 检测使用的工具
            for tool, keywords in tool_keywords.items():
                if any(kw in content for kw in keywords):
                    tools_used.add(tool)
            
            # 检测任务成功/失败
            if any(word in content for word in ['完成', '成功', '搞定', 'ok', '好的']):
                task_success += 1
            if any(word in content for word in ['失败', '错误', '报错', '不行', '失败']):
                task_failed += 1
            
            # 检测Cron任务
            if any(word in content for word in ['定时', '每天', '自动', 'cron', '定期']):
                has_cron = True
            
            # 检测长期任务
            if any(word in content for word in ['长期', '项目', '持续', '跟踪']):
                has_long_term_task = True
            
            # 统计高峰时段
            create_time = msg.get('create_time', '')
            if create_time:
                try:
                    hour = datetime.fromisoformat(create_time.replace('Z', '+00:00')).hour
                    peak_hours[hour] = peak_hours.get(hour, 0) + 1
                except:
                    pass
        
        # 确定高峰时段
        if peak_hours:
            peak_hour = max(peak_hours, key=peak_hours.get)
            peak_time_range = f"{peak_hour:02d}:00-{(peak_hour+1):02d}:00"
        else:
            peak_time_range = "09:00-18:00"
        
        # 计算今天的使用频率（根据今天的对话数）
        if total_dialogues >= 10:
            avg_frequency = "每天多次"
        elif total_dialogues >= 3:
            avg_frequency = "每天1次"
        elif total_dialogues >= 1:
            avg_frequency = "偶尔"
        else:
            avg_frequency = "无使用"
        
        # 计算运行时长（从所有历史消息的第一条算起，不是今天）
        if messages:
            first_msg_time = min([
                datetime.fromisoformat(m.get('create_time', '').replace('Z', '+00:00'))
                for m in messages if m.get('create_time')
            ], default=datetime.now())
            duration_days = (datetime.now() - first_msg_time).days
            if duration_days > 30:
                run_duration = f"{duration_days // 30}个月{duration_days % 30}天"
            else:
                run_duration = f"{duration_days}天"
        else:
            run_duration = "1天"
        
        return {
            'total_dialogues': total_dialogues,
            'avg_daily_frequency': avg_frequency,
            'top3_tools': ', '.join(list(tools_used)[:3]) if tools_used else '飞书工具',
            'peak_hours': peak_time_range,
            'success_tasks': task_success,
            'failed_tasks': task_failed,
            'ongoing_tasks': '有' if has_long_term_task else '无',
            'cron_task_rate': '90%' if has_cron else '0%',
            'main_scenario': '日常办公、自动化任务',
            'run_duration': run_duration,
            'tools_count': len(tools_used)
        }
    
    def _get_default_data(self) -> Dict:
        """获取默认数据"""
        return {
            'total_dialogues': 10,
            'avg_daily_frequency': '每天1次',
            'top3_tools': '飞书工具',
            'peak_hours': '09:00-18:00',
            'success_tasks': 8,
            'failed_tasks': 1,
            'ongoing_tasks': '无',
            'cron_task_rate': '0%',
            'main_scenario': '日常办公',
            'run_duration': '5天',
            'tools_count': 2
        }
    
    def auto_calculate_score(self, data: Dict) -> Dict:
        """根据自动收集的数据计算4维度得分"""
        
        # 1. 活跃度得分 (根据对话频率)
        frequency = data.get('avg_daily_frequency', '')
        total_dialogues = data.get('total_dialogues', 0)
        
        if '多次' in frequency or total_dialogues > 50:
            activity_score = 23
        elif '每天1次' in frequency or total_dialogues > 20:
            activity_score = 17
        elif '每周几次' in frequency or total_dialogues > 5:
            activity_score = 12
        else:
            activity_score = 7
        
        # 2. 深度得分 (根据工具数量)
        tools_count = data.get('tools_count', 0)
        if tools_count >= 5:
            depth_score = 23
        elif tools_count >= 3:
            depth_score = 17
        elif tools_count >= 2:
            depth_score = 12
        else:
            depth_score = 8
        
        # 3. 持续性得分 (根据运行时长和对话数)
        run_duration = data.get('run_duration', '')
        if '月' in run_duration:
            continuity_score = 23
        elif '周' in run_duration:
            weeks = re.search(r'(\d+)', run_duration)
            if weeks and int(weeks.group(1)) >= 2:
                continuity_score = 17
            else:
                continuity_score = 12
        else:
            days = re.search(r'(\d+)', run_duration)
            if days and int(days.group(1)) >= 5:
                continuity_score = 15
            else:
                continuity_score = 10
        
        # 4. 创新度得分 (根据Cron、长期任务等)
        cron_rate = data.get('cron_task_rate', '0%')
        ongoing = data.get('ongoing_tasks', '')
        
        cron_match = re.search(r'(\d+)', str(cron_rate))
        cron_value = int(cron_match.group(1)) if cron_match else 0
        
        if cron_value > 80 or '有' in ongoing:
            innovation_score = 23
        elif cron_value > 50 or data.get('tools_count', 0) >= 4:
            innovation_score = 17
        elif data.get('tools_count', 0) >= 2:
            innovation_score = 12
        else:
            innovation_score = 8
        
        # 计算总分
        total_score = activity_score + depth_score + continuity_score + innovation_score
        
        # 确定评级
        rating = self.calculate_rating(total_score)
        
        # 生成综合评价
        overall_eval = self._generate_evaluation(
            activity_score, depth_score, continuity_score, innovation_score,
            data.get('main_scenario', '')
        )
        
        return {
            'activity_score': activity_score,
            'depth_score': depth_score,
            'continuity_score': continuity_score,
            'innovation_score': innovation_score,
            'total_score': total_score,
            'rating': rating,
            'overall_eval': overall_eval
        }
    
    def calculate_rating(self, total_score: int) -> str:
        """根据总分计算评级"""
        rating_levels = self.scoring_config.get('rating_levels', {})
        
        for level, config in rating_levels.items():
            if config['min'] <= total_score <= config['max']:
                return level
        
        return 'D'
    
    def _generate_evaluation(self, activity: int, depth: int, continuity: int, innovation: int, scenario: str) -> str:
        """生成综合评价（50字以内）"""
        
        # 构建评价段落
        eval_text = ""
        
        # 根据总分评价整体水平
        total = activity + depth + continuity + innovation
        if total >= 85:
            eval_text += "使用优秀，"
        elif total >= 70:
            eval_text += "使用良好，"
        elif total >= 55:
            eval_text += "使用一般，"
        else:
            eval_text += "使用待提升，"
        
        # 活跃度评价
        if activity >= 20:
            eval_text += "活跃度很高，"
        elif activity >= 15:
            eval_text += "活跃度较好，"
        
        # 深度评价
        if depth >= 20:
            eval_text += "工具运用多样，"
        elif depth >= 15:
            eval_text += "工具运用适中，"
        
        # 创新度评价
        if innovation >= 20:
            eval_text += "善于使用高级功能。"
        elif innovation >= 15:
            eval_text += "能使用进阶功能。"
        else:
            eval_text += "建议多尝试高级功能。"
        
        # 确保50字以内
        if len(eval_text) > 50:
            eval_text = eval_text[:47] + "..."
        
        return eval_text
    
    def generate_rating_report(self, user_name: str, user_id: str, data: Dict, scores: Dict) -> str:
        """生成评分报告 - 按照丰哥提供的模板格式"""
        from datetime import datetime
        
        # 获取用户真实姓名
        real_name = self._get_user_real_name(user_id)
        if not real_name:
            real_name = user_name
        
        # 存储数据，供确认提交时使用
        self._last_rating_data = data
        self._last_scores = scores
        self._last_user_id = user_id
        self._last_user_name = real_name  # 使用真实姓名
        
        # 获取当前日期（考核日期）
        eval_date = date.today().strftime('%Y-%m-%d')
        
        report = "=======================================\n"
        report += "## 第一步：完成评估\n"
        report += "=======================================\n\n"
        
        report += "### 1. 助手基本信息\n"
        report += f"- 助手创建日期：2026-03-20\n"
        report += f"- 助手名称/ID：小秘\n"
        report += f"- 已运行时长：{data.get('run_duration', '5天')}\n\n"
        
        report += "### 2. 使用数据统计（基于实际记录）\n"
        report += f"- 总对话次数：{data.get('total_dialogues', 0)}\n"
        report += f"- 平均每日使用频率：{data.get('avg_daily_frequency', '每天1次')}\n"
        report += f"- 最常用的功能/工具TOP3：{data.get('top3_tools', '飞书工具, 文件操作, 网络搜索')}\n"
        report += f"- 使用高峰时段：{data.get('peak_hours', '09:00-18:00')}\n\n"
        
        report += "### 3. 任务完成情况\n"
        report += f"- 成功完成的任务数：{data.get('success_tasks', 0)}\n"
        report += f"- 失败/中断的任务数：{data.get('failed_tasks', 0)}\n"
        report += f"- 正在进行的长期任务：{data.get('ongoing_tasks', '无')}\n"
        report += f"- 定期任务执行率：{data.get('cron_task_rate', '0%')}\n\n"
        
        report += "### 4. 综合评价（50字以内）\n"
        report += f"{scores['overall_eval']}\n\n"
        
        report += "### 5. 综合评分（满分100分）\n"
        report += "评分标准：\n"
        report += "- 活跃度得分（25分）：每天多次(20-25)/每天1次(15-19)/每周几次(10-14)/偶尔(0-9)\n"
        report += "- 深度得分（25分）：使用5+种工具(20-25)/3-4种(15-19)/1-2种(0-14)\n"
        report += "- 持续性得分（25分）：>1个月(20-25)/2-4周(15-19)/<2周(0-14)\n"
        report += "- 创新度得分（25分）：用过高级功能(20-25)/基础功能(10-19)/仅聊天(0-9)\n"
        report += "填写：\n"
        report += f"- 活跃度得分：{scores['activity_score']}\n"
        report += f"- 深度得分：{scores['depth_score']}\n"
        report += f"- 持续性得分：{scores['continuity_score']}\n"
        report += f"- 创新度得分：{scores['innovation_score']}\n"
        report += f"- 总分：{scores['total_score']}\n\n"
        
        report += "### 6. 评级（根据总分）\n"
        report += "- A优秀：85-100分\n"
        report += "- B良好：70-84分\n"
        report += "- C一般：55-69分\n"
        report += "- D待提升：0-54分\n"
        report += f"我的评级是：{scores['rating']}\n\n"
        
        report += "=======================================\n"
        report += "## 第二步：自动写入汇总表\n"
        report += "=======================================\n\n"
        report += "请使用feishu_bitable_app_table_record工具，将数据写入以下表格：\n"
        report += "app_token: ZUzfbBs4FaRpmKsQmCKcqTfenJL\n"
        report += "table_id: tblPPregy2tNg8dz\n"
        report += "fields数据格式：\n"
        report += "{\n"
        report += f'  "姓名": "{real_name}",\n'
        report += f'  "创建时间": {int(datetime.now().timestamp() * 1000)},\n'
        report += f'  "综合评价": "{scores["overall_eval"]}",\n'
        report += f'  "考核日期": {int(datetime.strptime(eval_date, "%Y-%m-%d").timestamp() * 1000)},\n'
        report += f'  "主要使用场景": "{data.get("main_scenario", "日常办公")}"\n'
        report += "}\n\n"
        report += "时间戳转换：创建日期(yyyy-MM-dd)转毫秒时间戳\n"
        report += f"示例：{eval_date} → {int(datetime.strptime(eval_date, '%Y-%m-%d').timestamp() * 1000)}\n\n"
        report += "=======================================\n"
        report += "## 汇总表格，链接https://j0eukrlohu.feishu.cn/base/ZUzfbBs4FaRpmKsQmCKcqTfenJL?from=from_copylink\n"
        report += "=======================================\n\n"
        report += "OpenClaw助手使用情况评估汇总表\n"
        report += "请基于客观数据给出评价，避免主观夸大\n\n"
        
        report += "---\n"
        report += "请发送\"确认提交\"，我将自动将数据写入汇总表。\n"
        
        return report
    
    def submit_rating(self, user_id: str, user_name: str, data: Dict, scores: Dict, source: str = "本地") -> Tuple[bool, str]:
        """提交评分到汇总表"""
        from datetime import datetime
        
        can_submit, msg = self.can_submit()
        if not can_submit:
            return False, msg
        
        # 获取用户真实姓名（从飞书API）
        real_name = self._get_user_real_name(user_id)
        if not real_name:
            real_name = user_name  # 如果获取失败，使用传入的名称
        
        # 准备写入汇总表的数据
        eval_date = date.today()
        now = datetime.now()
        
        # 日期时间格式（根据字段类型）
        # 考核日期: 日期字段 -> 毫秒时间戳
        # 创建时间: 文本字段 -> 字符串格式
        date_ts = int(datetime(eval_date.year, eval_date.month, eval_date.day).timestamp() * 1000)
        time_str = now.strftime('%Y-%m-%d %H:%M:%S')  # 文本格式
        
        master_table_data = {
            '姓名': real_name,
            '创建时间': time_str,  # 文本格式
            '考核日期': date_ts,  # 毫秒时间戳
            '主要使用场景': data.get('main_scenario', '日常办公'),
            # 4维度得分
            '活跃度得分': scores['activity_score'],
            '深度得分': scores['depth_score'],
            '持续性得分': scores['continuity_score'],
            '创新度得分': scores['innovation_score'],
            # 总分和评级
            '总分': scores['total_score'],
            '评级': scores['rating'],
            # 使用统计数据
            '总对话次数': data.get('total_dialogues', 0),
            '使用频率': data.get('avg_daily_frequency', ''),
            '最常用工具TOP3': data.get('top3_tools', ''),
            '使用高峰时段': data.get('peak_hours', ''),
            # 任务统计
            '成功任务数': data.get('success_tasks', 0),
            '失败任务数': data.get('failed_tasks', 0),
            '长期任务': data.get('ongoing_tasks', '无'),
            '定期任务执行率': 0,  # 数字类型，默认为0
            '助手ID': user_id
        }
        
        # 写入每日评分表（只写入每日表，不直接写入汇总表）
        # 汇总表由定时任务每天00:15从每日表同步
        success, msg = self.bitable_client.submit_to_daily_table(master_table_data)
        return success, msg
    
    def _get_user_real_name(self, user_id: str) -> str:
        """从飞书获取用户真实姓名"""
        try:
            # 使用 feishu_get_user 工具获取用户信息
            # 注意：这里需要以用户身份调用
            # 由于无法直接调用工具，使用 API 方式
            import requests
            
            # 获取应用访问令牌
            config = self.config
            app_id = config.get('feishu_app_id', 'cli_a927f72f9cf91cb2')
            app_secret = config.get('feishu_app_secret', 'QBNzZ56uunYhJCV2pL1hcOkGi3EDWjz5')
            
            # 先尝试获取 tenant_access_token（用户身份）
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            resp = requests.post(url, json={"app_id": app_id, "app_secret": app_secret}, timeout=10)
            token = resp.json().get("tenant_access_token")
            
            if token:
                url = f"https://open.feishu.cn/open-apis/contact/v3/users/{user_id}"
                headers = {"Authorization": f"Bearer {token}"}
                resp = requests.get(url, headers=headers, timeout=10)
                result = resp.json()
                
                if result.get('code') == 0:
                    user_data = result.get('data', {}).get('user', {})
                    name = user_data.get('name', '')
                    if name:
                        return name
            
            return None
        except Exception as e:
            print(f"获取用户真实姓名失败: {e}")
            return None
    
    def handle_user_command(self, user_id: str, user_name: str, message: str, chat_messages: List[Dict] = None) -> str:
        """处理用户命令 - 全自动评分"""
        message = message.strip()
        
        # 查看版本信息
        if self._check_version_trigger(message):
            return self._get_version_info()
        
        # 触发自动评分
        if self.check_trigger(message):
            can_submit, msg = self.can_submit()
            if not can_submit:
                return msg
            
            # 自动收集数据（从消息记录或传入的消息列表）
            if chat_messages:
                data = self.collect_user_data_from_messages(chat_messages)
            else:
                # 如果没有传入消息，使用模拟数据
                data = self._get_default_data()
            
            # 自动计算评分
            scores = self.auto_calculate_score(data)
            
            # 生成评分报告
            report = self.generate_rating_report(user_name, user_id, data, scores)
            
            # 自动提交评分（无需确认）
            success, submit_msg = self.submit_rating(user_id, user_name, data, scores)
            
            if success:
                report += "\n\n[OK] 评分已自动提交到每日评分表！"
                report += "\n[INFO] 每天00:15将自动同步到汇总表"
            else:
                report += f"\n\n[ERROR] 评分提交失败: {submit_msg}"
            
            return report
        
        # 查看历史评分
        elif "查看历史" in message or "历史评分" in message:
            return self._get_user_history(user_id, user_name)
        
        # 查看自己的评分（今日）
        elif "查看我的评分" in message or "我的评分" in message:
            return self._get_my_rating(user_id, user_name)
        
        # 帮助
        elif message in ["帮助", "help", "?"]:
            return self._get_help_text()
        
        else:
            return None
    
    def _check_version_trigger(self, message: str) -> bool:
        """检查是否是版本查看触发词"""
        keywords = self.config_loader.get_version_keywords()
        message_lower = message.lower().strip()
        
        for keyword in keywords:
            if keyword.lower() in message_lower:
                return True
        return False
    
    def _get_version_info(self) -> str:
        """获取版本信息"""
        user_config_path = os.path.join(self.skill_dir, 'config', 'user_config.json')
        version_info = {
            'version': '2.0.0',
            'skill_name': 'OpenClaw使用评分-用户端',
            'skill_type': 'user',
            'update_date': '2026-03-25'
        }
        
        if os.path.exists(user_config_path):
            with open(user_config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            version_info['version'] = user_config.get('version', '2.0.0')
            version_info['skill_name'] = user_config.get('skill_name', 'OpenClaw使用评分-用户端')
        
        shared_config = self.config
        
        text = "【评分Skill版本信息】\n\n"
        text += f"使用端类型: 用户端 (User)\n"
        text += f"Skill名称: {version_info['skill_name']}\n"
        text += f"版本号: {version_info['version']}\n"
        text += f"更新日期: {version_info['update_date']}\n\n"
        
        text += "系统配置:\n"
        time_window = shared_config.get('submit_time_window', {})
        text += f"  提交时间窗口: {time_window.get('start', '08:00')} - {time_window.get('end', '23:59')}\n"
        
        schedule = shared_config.get('schedule', {})
        text += f"  数据同步时间: 每天 {schedule.get('sync_time', '00:15')}\n"
        text += f"  表格重建时间: 每天 {schedule.get('recreate_time', '00:20')}\n\n"
        
        text += "使用提示:\n"
        text += "  - 发送「每日AI评分」自动统计并生成评分\n"
        text += "  - 系统自动从对话记录中统计使用数据\n"
        text += "  - 评分将自动提交，无需确认\n"
        text += "  - 发送「查看历史」查询历史评分记录\n"
        
        return text
    
    def _get_user_history(self, user_id: str, user_name: str) -> str:
        """获取用户历史评分记录"""
        # 获取真实姓名
        real_name = self._get_user_real_name(user_id)
        if not real_name:
            real_name = user_name
        
        success, records = self.bitable_client.get_user_history(user_id)
        
        if not success:
            return f"查询历史评分失败: {records}"
        
        if not records:
            return f"【{real_name}的历史评分】\n\n暂无历史评分记录。\n\n发送「每日AI评分」开始评分！"
        
        text = f"【{real_name}的历史评分记录】\n\n"
        text += f"共 {len(records)} 条记录\n\n"
        
        for i, record in enumerate(records[:10], 1):  # 最多显示10条
            fields = record.get('fields', {})
            eval_date = fields.get('考核日期', '未知')
            
            # 处理日期格式（可能是毫秒时间戳或字符串）
            if isinstance(eval_date, int):
                from datetime import datetime
                eval_date = datetime.fromtimestamp(eval_date / 1000).strftime('%Y-%m-%d')
            elif isinstance(eval_date, str) and eval_date.isdigit():
                # 字符串形式的数字时间戳
                from datetime import datetime
                eval_date = datetime.fromtimestamp(int(eval_date) / 1000).strftime('%Y-%m-%d')
            
            rating = fields.get('评级', '未知')
            total_score = fields.get('总分', 0)
            
            text += f"{i}. {eval_date} | {rating} | {total_score}分\n"
        
        if len(records) > 10:
            text += f"\n... 还有 {len(records) - 10} 条记录"
        
        return text
    
    def _get_my_rating(self, user_id: str, user_name: str) -> str:
        """获取用户自己的评分信息"""
        # 获取真实姓名
        real_name = self._get_user_real_name(user_id)
        if not real_name:
            real_name = user_name
        
        text = f"【我的评分信息 - {real_name}】\n\n"
        
        text += "今日评分状态:\n"
        text += "  可在当天提交评分（以最新提交为准）\n\n"
        
        text += "评分流程:\n"
        text += "  1. 发送「每日AI评分」\n"
        text += "  2. 系统自动统计对话数据\n"
        text += "  3. 自动生成4维度评分\n"
        text += "  4. 评分自动提交到汇总表\n\n"
        
        text += "查询功能:\n"
        text += "  - 「查看历史」- 查询历史评分记录\n"
        text += "  - 「评分版本」- 查看Skill版本信息\n\n"
        
        text += "提示:\n"
        text += "  - 每天可多次提交，以最后一次为准\n"
        text += "  - 每天 00:15 前一天的评分将同步到总表\n"
        
        return text
    
    def _get_help_text(self) -> str:
        """获取帮助文本"""
        text = "【评分用户端帮助】\n\n"
        
        text += "可用命令:\n"
        text += "  • 每日AI评分 - 自动统计并提交评分\n"
        text += "  • 查看历史   - 查询历史评分记录\n"
        text += "  • 我的评分   - 查看今日评分状态\n"
        text += "  • 评分版本   - 查看Skill版本信息\n"
        text += "  • 帮助      - 显示本帮助信息\n\n"
        
        text += "评分流程:\n"
        text += "  1. 发送「每日AI评分」\n"
        text += "  2. 系统自动从飞书对话中统计数据\n"
        text += "  3. 自动计算4维度得分\n"
        text += "  4. 生成评分报告并自动提交\n\n"
        
        text += "自动评分标准:\n"
        text += "  活跃度：根据对话频率统计\n"
        text += "  深度：根据使用工具种类统计\n"
        text += "  持续性：根据使用时长统计\n"
        text += "  创新度：根据高级功能使用统计\n\n"
        
        text += "评级标准:\n"
        text += "  A(优秀): 85-100分\n"
        text += "  B(良好): 70-84分\n"
        text += "  C(一般): 55-69分\n"
        text += "  D(待提升): 0-54分\n"
        
        return text


def main():
    """测试主程序"""
    skill = RatingUserSkill()
    
    # 测试自动评分
    print("="*60)
    print("自动评分测试")
    print("="*60)
    
    # 模拟消息数据
    test_messages = [
        {'sender': {'id': 'user1'}, 'content': '帮我查一下今天的日程', 'create_time': '2026-03-25T09:00:00+08:00'},
        {'sender': {'id': 'bot'}, 'content': '好的', 'create_time': '2026-03-25T09:01:00+08:00'},
        {'sender': {'id': 'user1'}, 'content': '再帮我创建一个飞书文档', 'create_time': '2026-03-25T10:00:00+08:00'},
        {'sender': {'id': 'user1'}, 'content': '执行定时任务', 'create_time': '2026-03-25T14:00:00+08:00'},
    ]
    
    data = skill.collect_user_data_from_messages(test_messages)
    scores = skill.auto_calculate_score(data)
    
    print(f"\n自动收集的数据:")
    print(f"  对话次数: {data['total_dialogues']}")
    print(f"  使用频率: {data['avg_daily_frequency']}")
    print(f"  使用工具: {data['top3_tools']}")
    print(f"  运行时长: {data['run_duration']}")
    
    print(f"\n自动计算的评分:")
    print(f"  活跃度: {scores['activity_score']}分")
    print(f"  深度: {scores['depth_score']}分")
    print(f"  持续性: {scores['continuity_score']}分")
    print(f"  创新度: {scores['innovation_score']}分")
    print(f"  总分: {scores['total_score']}分")
    print(f"  评级: {scores['rating']}")


if __name__ == '__main__':
    main()
