#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenClaw 评分用户端 - 独立配置加载器 v3.0.0
完全独立运行，不再依赖管理端的配置文件
"""

import json
import os
from datetime import datetime


class SharedConfigLoader:
    """独立配置加载器 - 从用户端自身配置或飞书配置表读取"""
    
    def __init__(self, skill_dir=None, bitable_client=None):
        if skill_dir is None:
            skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self.skill_dir = skill_dir
        self.bitable_client = bitable_client
        
        # 直接读取用户端自身的配置文件
        self.config_path = os.path.join(skill_dir, 'config', 'user_config.json')
        self._config = None
    
    def load_config(self):
        """加载用户端自身配置"""
        if self._config is None:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            else:
                raise FileNotFoundError(f"用户端配置文件不存在: {self.config_path}")
        return self._config
    
    def reload_config(self):
        """强制重新加载配置"""
        self._config = None
        return self.load_config()
    
    def get_trigger_keywords(self):
        """获取触发关键词列表"""
        config = self.load_config()
        return config.get('trigger_keywords', ['每日AI评分', 'AI评分'])
    
    def get_version_keywords(self):
        """获取版本查看关键词列表"""
        config = self.load_config()
        return config.get('version_keywords', ['评分版本', '评分Skill版本'])
    
    def get_history_keywords(self):
        """获取历史查询关键词列表"""
        config = self.load_config()
        return config.get('history_keywords', ['查看历史评分', '历史评分'])
    
    def get_time_window(self):
        """获取提交时间窗口配置（优先从飞书配置表读取）"""
        # 尝试从飞书配置表读取
        try:
            config = self.load_config()
            config_table = config.get('feishu_bitable', {}).get('config_table', {})
            app_token = config_table.get('app_token')
            table_id = config_table.get('table_id')
            
            if app_token and table_id:
                import requests
                # 获取 app access token
                url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
                app_id = "cli_a927f72f9cf91cb2"
                app_secret = "QBNzZ56uunYhJCV2pL1hcOkGi3EDWjz5"
                resp = requests.post(url, json={"app_id": app_id, "app_secret": app_secret}, timeout=10)
                token = resp.json().get("app_access_token")
                
                if token:
                    url2 = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
                    headers = {"Authorization": f"Bearer {token}"}
                    resp2 = requests.get(url2, headers=headers, timeout=10)
                    result = resp2.json()
                    
                    if result.get('code') == 0:
                        items = result.get('data', {}).get('items', [])
                        time_config = {'enabled': True, 'start': '00:00', 'end': '23:59'}
                        
                        for item in items:
                            fields = item.get('fields', {})
                            key_raw = fields.get('配置项', '')
                            # 处理文本字段格式
                            if isinstance(key_raw, list):
                                key = key_raw[0].get('text', '') if key_raw else ''
                            else:
                                key = str(key_raw)
                            
                            val_raw = fields.get('配置值', '')
                            if isinstance(val_raw, list):
                                val = val_raw[0].get('text', '') if val_raw else ''
                            else:
                                val = str(val_raw)
                            
                            if key == 'time_window_start':
                                time_config['start'] = val.split(':')[0] + ':' + val.split(':')[1] if ':' in val else val
                            elif key == 'time_window_end':
                                time_config['end'] = val.split(':')[0] + ':' + val.split(':')[1] if ':' in val else val
                            elif key == 'time_window_enabled':
                                time_config['enabled'] = val.lower() == 'true'
                        
                        return time_config
        except Exception as e:
            print(f"从配置表读取时间窗口失败: {e}")
        
        # 回退到本地配置
        config = self.load_config()
        return config.get('submit_time_window', {'enabled': True, 'start': '00:00', 'end': '23:59'})
    
    def is_in_time_window(self):
        """检查当前是否在提交时间窗口内"""
        time_window = self.get_time_window()
        if not time_window.get('enabled', True):
            return True
        
        now = datetime.now()
        start_str = time_window.get('start', '00:00')
        end_str = time_window.get('end', '23:59')
        
        start_time = datetime.strptime(start_str, '%H:%M').time()
        end_time = datetime.strptime(end_str, '%H:%M').time()
        
        return start_time <= now.time() <= end_time
    
    def get_bitable_config(self):
        """获取多维表格配置"""
        config = self.load_config()
        return config.get('feishu_bitable', {})
    
    def get_master_table_token(self):
        """获取汇总表 app_token"""
        bitable = self.get_bitable_config()
        return bitable.get('master_table', {}).get('app_token', '')
    
    def get_daily_table_token(self):
        """获取每日评分表 app_token"""
        bitable = self.get_bitable_config()
        return bitable.get('daily_table', {}).get('app_token', '')
    
    def get_scoring_config(self):
        """获取评分标准配置"""
        config = self.load_config()
        return config.get('scoring', {})


if __name__ == '__main__':
    # 测试
    loader = SharedConfigLoader()
    print("✅ 独立配置加载器初始化成功")
    print(f"配置路径: {loader.config_path}")
    
    try:
        config = loader.load_config()
        print(f"技能名称: {config.get('skill_name')}")
        print(f"版本: {config.get('version')}")
        print(f"触发关键词: {loader.get_trigger_keywords()}")
        print(f"汇总表Token: {loader.get_master_table_token()}")
        print(f"每日表Token: {loader.get_daily_table_token()}")
        print(f"当前在提交时间窗口内: {loader.is_in_time_window()}")
    except FileNotFoundError as e:
        print(f"错误: {e}")
