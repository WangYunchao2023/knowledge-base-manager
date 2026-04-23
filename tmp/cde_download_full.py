#!/usr/bin/env python3
"""
CDE文件下载器 - 完整版
需要先访问首页获取Cookie，然后用会话下载
"""
import asyncio
import os
import subprocess
from playwright.async_api import async_playwright

SAVE_DIR = "/home/wangyc/Documents/工作/法规指导原则"

# CDE指导原则详情页URL列表
PAGES = [
    ("药物研发与技术审评沟通交流会议申请资料参考", 
     "https://www.cde.org.cn/main/policy/regulatview/df2135f1f1ad1af14318efb3689828a4"),
    ("儿童用药沟通交流中I类会议申请及管理工作细则",
     "https://www.cde.org.cn/main/policy/regulatview/05b555deca24fce53c68d73cc77512c2"),
    ("细胞和基因治疗产品临床相关沟通交流技术指导原则",
     "https://www.cde.org.cn/main/news/viewInfoCommon/3dafaa3e4fe647efab4f80a06d0b7d3e"),
    ("真实世界证据支持药物注册申请的沟通交流指导原则",
     "https://www.cde.org.cn/main/news/viewInfoCommon/f6efe3e4d2ac4fcf8ef4760a4be6b9e0"),
    ("基于三结合注册审评证据体系下的沟通交流指导原则",
     "https://www.cde.org.cn/main/news/viewInfoCommon/7f8df5e4d2ac4fcf8ef4760a4be6b9e1"),
]

async def download_with_session():
    """使用会话来下载文件"""
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        context = await browser.new_context()
        page = await context.new_page()
        
        # 1. 先访问首页获取Cookie
        print("步骤1: 访问首页获取Cookie...")
        await page.goto("https://www.cde.org.cn", wait_until='load', timeout=60000)
        await asyncio.sleep(10)
        cookies = await context.cookies()
        print(f"  获取到 {len(cookies)} 个Cookie")
        
        # 2. 访问每个详情页并下载
        for title, url in PAGES:
            print(f"\n步骤2: 访问 {title}...")
            
            try:
                await page.goto(url, wait_until='load', timeout=60000)
                await asyncio.sleep(30)  # 等待JavaScript加载
                
                # 获取所有链接
                links = await page.query_selector_all('a')
                
                # 查找PDF/DOC下载链接
                for link in links:
                    try:
                        href = await link.get_attribute('href')
                        text = await link.inner_text()
                        
                        # 检查href或text中是否包含下载关键词
                        if href and ('pdf' in href.lower() or 'doc' in href.lower() or 
                                     'pdf' in text.lower() or 'doc' in text.lower() or
                                     '.pdf' in text or '.doc' in text):
                            full_url = href if href.startswith('http') else f"https://www.cde.org.cn{href}"
                            
                            # 提取文件名
                            filename = text.strip() if text.strip() else f"{title}.pdf"
                            filename = filename.replace('/', '_').replace('\\', '')[:80]
                            if not filename.endswith(('.pdf', '.doc', '.docx')):
                                filename += '.pdf'
                            
                            save_path = os.path.join(SAVE_DIR, filename)
                            print(f"  找到下载: {text.strip()[:30]}")
                            print(f"  URL: {full_url}")
                            print(f"  保存到: {save_path}")
                        
                        # 使用curl下载（带Cookie）
                        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                        
                        result = subprocess.run(
                            ['curl', '-L', '-o', save_path, 
                             '-H', f'Cookie: {cookie_str}',
                             '-A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                             full_url],
                            capture_output=True, timeout=60
                        )
                        
                        if os.path.exists(save_path):
                            size = os.path.getsize(save_path)
                            # 检查是否是有效文件
                            if size < 10000:
                                # 可能是HTML错误页
                                with open(save_path, 'r') as f:
                                    content = f.read(100)
                                    if '<!DOCTYPE' in content or '<html' in content:
                                        print(f"  ✗ 下载失败，得到的是HTML页面")
                                        os.remove(save_path)
                                        continue
                            print(f"  ✓ 下载完成! 大小: {size} bytes")
                        break
                else:
                    print(f"  未找到PDF下载链接")
                    
            except Exception as e:
                print(f"  错误: {str(e)[:50]}")
        
        await browser.close()
    
    print(f"\n完成! 文件保存在: {SAVE_DIR}")

if __name__ == "__main__":
    asyncio.run(download_with_session())
