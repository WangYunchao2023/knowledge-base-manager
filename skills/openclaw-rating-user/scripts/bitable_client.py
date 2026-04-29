#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenClaw 评分用户端 - 多维表格客户端
只负责向每日临时表提交评分数据
"""

import json
import os
import sys
from datetime import datetime, date
from typing import Dict, Tuple, Optional
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared_config_loader import SharedConfigLoader


class BitableClient:
    """多维表格客户端（用户端）"""
    
    BASE_URL = "https://open.feishu.cn/open-apis"
    
    def __init__(self, skill_dir=None, access_token=None):
        if skill_dir is None:
            skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self.skill_dir = skill_dir
        self.config_loader = SharedConfigLoader(skill_dir)
        self.access_token = access_token
        
        # 获取缓存目录
        self.cache_dir = os.path.join(skill_dir, 'cache')
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _get_headers(self) -> Dict[str, str]:
        """获取 API 请求头"""
        # 如果没有 access_token，尝试获取
        if not self.access_token:
            self._refresh_token()
        
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    def _refresh_token(self):
        """刷新访问令牌"""
        try:
            config = self.config_loader.load_config()
            app_id = config.get('feishu_app_id', 'cli_a927f72f9cf91cb2')
            app_secret = config.get('feishu_app_secret', 'QBNzZ56uunYhJCV2pL1hcOkGi3EDWjz5')
            
            url = f"{self.BASE_URL}/auth/v3/app_access_token/internal"
            resp = requests.post(url, json={"app_id": app_id, "app_secret": app_secret}, timeout=10)
            result = resp.json()
            
            if result.get('code') == 0:
                self.access_token = result.get('app_access_token')
        except Exception as e:
            print(f"获取 access_token 失败: {e}")
    
    def _api_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Tuple[bool, any]:
        """发送 API 请求"""
        url = f"{self.BASE_URL}{endpoint}"
        headers = self._get_headers()
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            else:
                return False, f"不支持的请求方法: {method}"
            
            response.raise_for_status()
            result = response.json()
            
            if result.get('code') == 0:
                return True, result.get('data', result)
            else:
                return False, result.get('msg', 'API 调用失败')
                
        except requests.exceptions.RequestException as e:
            return False, f"请求失败: {str(e)}"
        except json.JSONDecodeError:
            return False, "响应解析失败"
    
    def _get_daily_table_token(self) -> Optional[str]:
        """获取今日临时表的 App Token（从缓存）"""
        cache_file = os.path.join(self.cache_dir, 'table_token_cache.json')
        
        today_str = date.today().strftime('%Y%m%d')
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                # 检查缓存日期
                if cache.get('date') == today_str:
                    return cache.get('token')
            except:
                pass
        return None
    
    def _save_daily_table_token(self, token: str):
        """保存今日临时表 Token 到缓存"""
        cache_file = os.path.join(self.cache_dir, 'table_token_cache.json')
        
        cache = {
            'date': date.today().strftime('%Y%m%d'),
            'token': token
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    
    def _find_daily_table(self) -> Tuple[bool, str]:
        """
        查找今日临时表的Token
        优先从配置表获取，其次从本地缓存
        """
        today = date.today()
        
        # 1. 尝试从配置表获取（推荐方式）
        config_token = self._get_token_from_config_table()
        if config_token:
            self._save_daily_table_token(config_token)  # 同时更新本地缓存
            return True, config_token
        
        # 2. 尝试从本地缓存获取（备选方式）
        cached_token = self._get_daily_table_token()
        if cached_token:
            return True, cached_token
        
        # 3. 未找到
        return False, "今日评分表尚未创建，请联系管理员"
    
    def _get_token_from_config_table(self) -> Optional[str]:
        """
        从配置表获取今日临时表的Token
        配置表位于云文档/OpenClawRating文件夹中
        """
        try:
            # 从共享配置中获取配置表信息
            config = self.config_loader.load_config()
            config_table = config.get('feishu_bitable', {}).get('config_table', {})
            config_app_token = config_table.get('app_token')
            config_table_id = config_table.get('table_id')
            folder_token = config_table.get('folder_token')
            folder_path = config_table.get('folder_path', '云文档/OpenClawRating')
            
            if not config_app_token or not config_table_id:
                print(f"配置表信息未设置 (应该在: {folder_path})")
                return None
            
            # 查询配置表中 daily_table_token 的配置值
            # 实际应该调用API查询配置表
            # endpoint = f"/bitable/v1/apps/{config_app_token}/tables/{config_table_id}/records"
            # 使用 filter 查询配置项为 daily_table_token 的记录
            
            print(f"正在从配置表获取Token (位置: {folder_path})...")
            return None
            
        except Exception as e:
            print(f"从配置表获取Token失败: {e}")
            return None
    
    def submit_to_master_table(self, data: Dict) -> Tuple[bool, str]:
        """提交评分到汇总表"""
        # 汇总表信息（从配置或硬编码）
        master_app_token = "FrCsbtg5Qavsf7st5xmcLqKlnbc"
        
        # 获取表ID（从API获取第一个表）
        success, result = self._api_request("GET", f"/bitable/v1/apps/{master_app_token}/tables")
        if not success or not result.get('items'):
            return False, "获取汇总表信息失败"
        
        master_table_id = result['items'][0]['table_id']
        
        # 准备记录数据 - 按照汇总表的字段映射
        fields = {
            "open_id": data.get('助手ID', ''),  # 用户唯一标识
            "姓名": data.get('姓名', ''),
            "创建时间": data.get('创建时间', ''),  # 文本格式: '2026-03-26 00:28:10'
            "综合评价": data.get('综合评价', ''),
            "考核日期": data.get('考核日期', 0),  # 毫秒时间戳
            "主要使用场景": data.get('主要使用场景', ''),
            # 附加字段
            "活跃度得分": data.get('活跃度得分', 0),
            "深度得分": data.get('深度得分', 0),
            "持续性得分": data.get('持续性得分', 0),
            "创新度得分": data.get('创新度得分', 0),
            "总分": data.get('总分', 0),
            "评级": data.get('评级', ''),
            "总对话次数": data.get('总对话次数', 0),
            "使用频率": data.get('使用频率', '')
        }
        
        # 创建记录
        record_data = {"fields": fields}
        success, result = self._api_request(
            "POST",
            f"/bitable/v1/apps/{master_app_token}/tables/{master_table_id}/records",
            record_data
        )
        
        if success:
            return True, "✅ 评分已成功写入汇总表"
        else:
            return False, f"❌ 写入汇总表失败: {result}"
    
    def submit_to_daily_table(self, data: Dict) -> Tuple[bool, str]:
        """提交评分到每日评分表"""
        # 每日评分表信息
        daily_app_token = "EA5vb2RbzaF2AVsAqiucf7sznZr"
        
        # 获取表ID
        success, result = self._api_request("GET", f"/bitable/v1/apps/{daily_app_token}/tables")
        if not success or not result.get('items'):
            return False, "获取每日评分表信息失败"
        
        daily_table_id = result['items'][0]['table_id']
        
        # 准备记录数据 - 按照每日评分表的字段映射
        from datetime import datetime
        now = datetime.now()
        
        # 生成文本综合评价（50字以内）
        eval_text = data.get('综合评价', '')
        if not eval_text:
            # 如果没有提供，生成默认评价
            parts = []
            if data.get('活跃度得分', 0) >= 20:
                parts.append("使用活跃")
            if data.get('深度得分', 0) >= 20:
                parts.append("工具多样")
            if data.get('创新度得分', 0) >= 20:
                parts.append("善于创新")
            eval_text = "，".join(parts) if parts else "使用正常"
        
        # 确保50字以内
        if len(eval_text) > 50:
            eval_text = eval_text[:47] + "..."
        
        fields = {
            "open_id": data.get('助手ID', ''),
            "姓名": data.get('姓名', ''),
            "评分日期": data.get('考核日期', 0),
            "提交时间": data.get('创建时间', ''),
            "活跃度得分": data.get('活跃度得分', 0),
            "深度得分": data.get('深度得分', 0),
            "持续性得分": data.get('持续性得分', 0),
            "创新度得分": data.get('创新度得分', 0),
            "总分": data.get('总分', 0),
            "评级": data.get('评级', ''),
            "综合评价": eval_text,  # 文本格式，50字以内
            "主要使用场景": data.get('主要使用场景', ''),
            "总对话次数": data.get('总对话次数', 0),
            "使用频率": data.get('使用频率', ''),
            "最常用工具TOP3": data.get('最常用工具TOP3', ''),
            "使用高峰时段": data.get('使用高峰时段', ''),
            "成功任务数": data.get('成功任务数', 0),
            "失败任务数": data.get('失败任务数', 0),
            "长期任务": data.get('长期任务', '无'),
            "定期任务执行率": data.get('定期任务执行率', 0)
        }
        
        # 创建记录
        record_data = {"fields": fields}
        success, result = self._api_request(
            "POST",
            f"/bitable/v1/apps/{daily_app_token}/tables/{daily_table_id}/records",
            record_data
        )
        
        if success:
            return True, "评分已成功写入每日评分表"
        else:
            return False, f"写入每日评分表失败: {result}"
    
    def get_user_history(self, user_id: str) -> Tuple[bool, any]:
        """获取用户历史评分记录"""
        master_app_token = "FrCsbtg5Qavsf7st5xmcLqKlnbc"
        
        # 获取表ID
        success, result = self._api_request("GET", f"/bitable/v1/apps/{master_app_token}/tables")
        if not success or not result.get('items'):
            return False, "获取汇总表信息失败"
        
        master_table_id = result['items'][0]['table_id']
        
        # 构建查询条件 - 按open_id过滤
        filter_obj = {
            "conjunction": "and",
            "conditions": [
                {
                    "field_name": "open_id",
                    "operator": "is",
                    "value": [user_id]
                }
            ]
        }
        
        params = {
            "filter": json.dumps(filter_obj),
            "sort": json.dumps([{"field_name": "考核日期", "desc": True}]),
            "page_size": 50
        }
        
        success, result = self._api_request(
            "GET",
            f"/bitable/v1/apps/{master_app_token}/tables/{master_table_id}/records",
            params=params
        )
        
        if success:
            items = result.get('items', [])
            return True, items
        else:
            return False, result
    
    def submit_rating(self, user_id: str, rating_data: Dict) -> Tuple[bool, str]:
        """提交评分到每日临时表"""
        # 获取临时表 Token
        success, result = self._find_daily_table()
        if not success:
            return False, result
        
        app_token = result
        
        # 获取表 ID
        success, result = self._api_request("GET", f"/bitable/v1/apps/{app_token}/tables")
        if not success:
            return False, f"获取数据表失败: {result}"
        
        tables = result.get('items', [])
        if not tables:
            return False, "未找到数据表"
        
        table_id = tables[0].get('table_id')
        
        # 准备记录数据
        fields = {
            "提交时间": datetime.now().isoformat(),
            "评分人ID": user_id,  # open_id
            "评分人": rating_data.get('name', ''),
            "评分日期": rating_data.get('eval_date', date.today().isoformat()),
            "评级": rating_data.get('rating', ''),
            "总分": rating_data.get('total_score', 0),
            "活跃度得分": rating_data.get('activity_score', 0),
            "深度得分": rating_data.get('depth_score', 0),
            "持续性得分": rating_data.get('continuity_score', 0),
            "创新度得分": rating_data.get('innovation_score', 0),
            "综合评价": rating_data.get('overall_eval', ''),
            "主要使用场景": rating_data.get('main_scenario', ''),
            "助手名称": rating_data.get('assistant_name', ''),
            "助手创建日期": rating_data.get('assistant_create_date', ''),
            "已运行时长": rating_data.get('run_duration', ''),
            "总对话次数": rating_data.get('total_dialogues', 0),
            "平均每日频率": rating_data.get('avg_daily_frequency', ''),
            "最常用工具TOP3": rating_data.get('top3_tools', ''),
            "使用高峰时段": rating_data.get('peak_hours', ''),
            "成功完成任务数": rating_data.get('success_tasks', 0),
            "失败/中断任务数": rating_data.get('failed_tasks', 0),
            "正在进行的长期任务": rating_data.get('ongoing_tasks', ''),
            "定期任务执行率": rating_data.get('cron_task_rate', ''),
            "提交来源": rating_data.get('source', '未知')
        }
        
        # 创建记录
        record_data = {"fields": fields}
        success, result = self._api_request(
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            record_data
        )
        
        if success:
            return True, "✅ 评分提交成功"
        else:
            return False, f"❌ 提交失败: {result}"


if __name__ == '__main__':
    # 测试
    print("多维表格客户端已加载")
