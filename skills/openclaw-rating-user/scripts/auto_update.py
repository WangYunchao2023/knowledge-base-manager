#!/usr/bin/env python3
"""
OpenClaw评分Skill - 自动更新脚本
功能：检查版本 → 下载最新ZIP → 备份 → 解压安装 → 配置合并 → 验证
"""

import json
import os
import re
import sys
import zipfile
import shutil
import tempfile
import requests
from datetime import datetime

# ========== 配置 ==========
OPENCLAW_CONFIG = os.path.expanduser("~/.openclaw/openclaw.json")
FEISHU_API_BASE = "https://open.feishu.cn/open-apis"

VERSION_TABLE = {
    "app_token": "FEyJbVnADaC1TZshvUqc791In7b",
    "table_id": "tbl4YgNTSPBaLPuR"
}

SKILL_TYPES = {
    "user": {
        "dir": os.path.expanduser("~/.openclaw/workspace/skills/openclaw-rating-user"),
        "zip_field": "user_zip",
        "config_file": "user_config.json"
    },
    "admin": {
        "dir": os.path.expanduser("~/.openclaw/workspace/skills/openclaw-rating-admin"),
        "zip_field": "admin_zip",
        "config_file": "shared_config.json"
    }
}

# 配置合并时保留的个性化字段（不被新版本覆盖）
PRESERVE_KEYS = [
    "trigger_keywords",
    "version_keywords",
    "history_keywords",
    "submit_time_window",
    "skill_managers"
]


def load_feishu_credentials():
    """从openclaw.json读取飞书凭证"""
    with open(OPENCLAW_CONFIG, 'r', encoding='utf-8') as f:
        config = json.load(f)
    feishu = config.get("channels", {}).get("feishu", {})
    app_id = feishu.get("appId")
    app_secret = feishu.get("appSecret")
    if not app_id or not app_secret:
        raise Exception("openclaw.json中未找到飞书appId或appSecret")
    return app_id, app_secret


def get_tenant_access_token(app_id, app_secret):
    """获取tenant_access_token"""
    url = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": app_id, "app_secret": app_secret})
    data = resp.json()
    if data.get("code") == 0:
        return data["tenant_access_token"]
    raise Exception(f"获取token失败: {data.get('msg', data)}")


def get_local_version(skill_dir):
    """获取本地版本号（优先从config读取，备选从SKILL.md读取）"""
    # 方式1: 从config文件读取
    config_dir = os.path.join(skill_dir, "config")
    for name in ["user_config.json", "shared_config.json"]:
        p = os.path.join(config_dir, name)
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            if "version" in cfg:
                return cfg["version"]

    # 方式2: 从SKILL.md读取
    skill_md = os.path.join(skill_dir, "SKILL.md")
    if os.path.exists(skill_md):
        with open(skill_md, 'r', encoding='utf-8') as f:
            for line in f:
                match = re.search(r'v(\d+\.\d+\.\d+)', line)
                if match:
                    return match.group(1)
    return None


def get_latest_version(token):
    """从版本管理表获取最新版本信息"""
    url = f"{FEISHU_API_BASE}/bitable/v1/apps/{VERSION_TABLE['app_token']}/tables/{VERSION_TABLE['table_id']}/records/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "filter": {
            "conjunction": "and",
            "conditions": [
                {"field_name": "状态", "operator": "is", "value": ["最新版"]}
            ]
        }
    }
    resp = requests.post(url, headers=headers, json=payload)
    data = resp.json()
    if data.get("code") == 0:
        items = data.get("data", {}).get("items", [])
        if items:
            record = items[0]
            fields = record["fields"]
            # 解析版本号（可能是富文本数组或纯文本）
            version_raw = fields.get("版本号", "")
            if isinstance(version_raw, list):
                version = version_raw[0].get("text", "") if version_raw else ""
            else:
                version = str(version_raw)
            version = version.lstrip("v")
            return {
                "version": version,
                "record_id": record["record_id"],
                "user_zip": fields.get("用户端ZIP", []),
                "admin_zip": fields.get("管理端ZIP", [])
            }
    return None


def compare_versions(local, remote):
    """
    语义化版本号比较
    返回: -1(本地较旧), 0(相同), 1(本地较新)
    """
    def parse(v):
        return tuple(int(x) for x in v.split('.'))
    try:
        l, r = parse(local), parse(remote)
        if l < r:
            return -1
        elif l == r:
            return 0
        else:
            return 1
    except (ValueError, AttributeError):
        return -1  # 解析失败视为需要更新


def download_zip(token, file_token, output_path):
    """从飞书下载附件"""
    url = f"{FEISHU_API_BASE}/drive/v1/medias/{file_token}/download"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, stream=True)
    if resp.status_code == 200:
        with open(output_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        size = os.path.getsize(output_path)
        print(f"   [OK] 下载完成: {os.path.basename(output_path)} ({size:,} bytes)")
        return True
    raise Exception(f"下载失败: HTTP {resp.status_code}")


def backup_skill(skill_dir, version):
    """备份当前skill目录"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"{skill_dir}.bak_v{version}_{timestamp}"
    shutil.copytree(skill_dir, backup_dir)
    return backup_dir


def install_zip(zip_path, skill_dir):
    """解压ZIP安装到skill目录"""
    with zipfile.ZipFile(zip_path, 'r') as zf:
        names = zf.namelist()
        if not names:
            raise Exception("ZIP文件为空")

        # 找到ZIP中的根目录名（如 openclaw-rating-user/）
        root_dir = names[0].split('/')[0] + '/'

        installed_count = 0
        for name in names:
            # 去掉ZIP中的根目录前缀
            if name.startswith(root_dir):
                rel_path = name[len(root_dir):]
            else:
                rel_path = name

            if not rel_path:
                continue

            target_path = os.path.join(skill_dir, rel_path)

            if name.endswith('/'):
                os.makedirs(target_path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with zf.open(name) as src, open(target_path, 'wb') as dst:
                    dst.write(src.read())
                installed_count += 1

    print(f"   [OK] 安装完成: {installed_count} 个文件")
    return installed_count


def merge_config(skill_dir, backup_dir, skill_type):
    """
    配置合并策略：
    - 新版本的config作为基础（包含新增字段、更新的版本号）
    - 从旧版本保留个性化设置（PRESERVE_KEYS中的字段）
    """
    config_name = SKILL_TYPES[skill_type]["config_file"]
    new_config_path = os.path.join(skill_dir, "config", config_name)
    old_config_path = os.path.join(backup_dir, "config", config_name)

    if not os.path.exists(old_config_path) or not os.path.exists(new_config_path):
        print(f"   [SKIP] 配置文件不存在，跳过合并")
        return

    with open(new_config_path, 'r', encoding='utf-8') as f:
        new_config = json.load(f)
    with open(old_config_path, 'r', encoding='utf-8') as f:
        old_config = json.load(f)

    # 保留个性化字段
    merged_count = 0
    for key in PRESERVE_KEYS:
        if key in old_config:
            new_config[key] = old_config[key]
            merged_count += 1

    with open(new_config_path, 'w', encoding='utf-8') as f:
        json.dump(new_config, f, indent=2, ensure_ascii=False)

    print(f"   [OK] 配置合并完成: 保留了 {merged_count} 个个性化字段")


def rollback(skill_dir, backup_dir):
    """从备份恢复"""
    if os.path.exists(skill_dir):
        shutil.rmtree(skill_dir)
    shutil.copytree(backup_dir, skill_dir)
    print(f"   [OK] 已从备份恢复")


def check_only(skill_type="user"):
    """
    仅检查版本，不执行更新
    返回: {"needs_update": bool, "local": str, "remote": str}
    """
    skill_dir = SKILL_TYPES[skill_type]["dir"]
    local_version = get_local_version(skill_dir)
    if not local_version:
        return {"needs_update": False, "error": "无法读取本地版本号"}

    app_id, app_secret = load_feishu_credentials()
    token = get_tenant_access_token(app_id, app_secret)
    latest = get_latest_version(token)
    if not latest:
        return {"needs_update": False, "error": "版本管理表中无最新版记录"}

    needs_update = compare_versions(local_version, latest["version"]) < 0
    return {
        "needs_update": needs_update,
        "local": local_version,
        "remote": latest["version"]
    }


def auto_update(skill_type="user"):
    """
    主更新流程
    :param skill_type: "user" 或 "admin"
    :return: 更新结果字典
    """
    print("=" * 50)
    print(f"[UPDATE] OpenClaw评分Skill 自动更新 ({skill_type}端)")
    print("=" * 50)

    skill_info = SKILL_TYPES[skill_type]
    skill_dir = skill_info["dir"]
    backup_dir = None

    # Step 1: 读取本地版本号
    print("\n>> Step 1: 读取本地版本号...")
    local_version = get_local_version(skill_dir)
    if not local_version:
        raise Exception("无法读取本地版本号")
    print(f"   本地版本: v{local_version}")

    # Step 2: 获取最新版本
    print("\n>> Step 2: 获取最新版本信息...")
    app_id, app_secret = load_feishu_credentials()
    token = get_tenant_access_token(app_id, app_secret)
    latest = get_latest_version(token)
    if not latest:
        return {"status": "error", "message": "版本管理表中无最新版记录"}
    print(f"   最新版本: v{latest['version']}")

    # Step 3: 比较版本号
    print("\n>> Step 3: 比较版本号...")
    cmp = compare_versions(local_version, latest["version"])
    if cmp >= 0:
        print(f"   [OK] 本地已是最新版本，无需更新")
        return {"status": "up_to_date", "local": local_version, "remote": latest["version"]}
    print(f"   [>>] 需要更新: v{local_version} -> v{latest['version']}")

    # Step 4: 下载ZIP
    print("\n>> Step 4: 下载最新版ZIP...")
    zip_key = skill_info["zip_field"]
    zip_list = latest.get(zip_key, [])
    if not zip_list:
        raise Exception(f"最新版记录中无{zip_key}附件")
    file_token = zip_list[0]["file_token"]
    zip_name = zip_list[0].get("name", f"update_v{latest['version']}.zip")
    zip_path = os.path.join(tempfile.gettempdir(), zip_name)
    download_zip(token, file_token, zip_path)

    # Step 5: 备份
    print("\n>> Step 5: 备份当前版本...")
    backup_dir = backup_skill(skill_dir, local_version)
    print(f"   [OK] 备份完成: {os.path.basename(backup_dir)}")

    # Step 6: 安装
    print("\n>> Step 6: 安装新版本...")
    try:
        install_zip(zip_path, skill_dir)
    except Exception as e:
        print(f"   [FAIL] 安装失败: {e}")
        print(f"   [>>] 正在从备份恢复...")
        rollback(skill_dir, backup_dir)
        raise Exception(f"安装失败已回滚: {e}")

    # Step 7: 配置合并
    print("\n>> Step 7: 合并配置...")
    merge_config(skill_dir, backup_dir, skill_type)

    # Step 8: 验证
    print("\n>> Step 8: 验证安装...")
    new_version = get_local_version(skill_dir)
    if new_version == latest["version"]:
        print(f"   [OK] 验证通过: v{new_version}")
    else:
        print(f"   [WARN] 版本号不匹配: 期望v{latest['version']}, 实际v{new_version}")

    # 清理临时文件
    if os.path.exists(zip_path):
        os.remove(zip_path)

    print("\n" + "=" * 50)
    print(f"[DONE] 更新完成！v{local_version} -> v{new_version}")
    print(f"   备份位置: {os.path.basename(backup_dir)}")
    print("=" * 50)

    return {
        "status": "updated",
        "old_version": local_version,
        "new_version": new_version,
        "backup_dir": backup_dir
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="OpenClaw评分Skill 自动更新")
    parser.add_argument("action", nargs="?", default="update",
                       choices=["update", "check"],
                       help="update=执行更新, check=仅检查版本")
    parser.add_argument("--type", default="user", choices=["user", "admin"],
                       help="skill类型: user(用户端) 或 admin(管理端)")
    args = parser.parse_args()

    try:
        if args.action == "check":
            result = check_only(args.type)
        else:
            result = auto_update(args.type)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
