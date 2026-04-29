#!/usr/bin/env python3
"""
CDE文件下载器 - 简化版
"""
import asyncio
import os
import subprocess
from playwright.async_api import async_playwright

SAVE_DIR = "/home/wangyc/Documents/工作/法规指导原则"

PAGES = [
    ("药物研发与技术审评沟通交流会议申请资料参考", 
     "https://www.cde.org.cn/main/policy/regulatview/df2135f1f1ad1af14318efb3689828a4"),
    ("儿童用药沟通交流中I类会议申请及管理工作细则",
     "https://www.cde.org.cn/main/policy/regulatview/05b555deca24fce53c68d73cc77512c2"),
]

async def main():
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--no-sandbox'])
        context = await browser.new_context()
        page = await context.new_page()
        
        # 获取Cookie
        print("获取Cookie...")
        await page.goto("https://www.cde.org.cn", wait_until='load')
        await asyncio.sleep(10)
        cookies = await context.cookies()
        
        for title, url in PAGES:
            print(f"\n访问: {title}")
            await page.goto(url, wait_until='load')
            await asyncio.sleep(30)
            
            links = await page.query_selector_all('a')
            for link in links:
                href = await link.get_attribute('href')
                text = await link.inner_text()
                
                # 检查是否是下载链接
                if href and ('.pdf' in text.lower() or '.doc' in text.lower()):
                    full_url = f"https://www.cde.org.cn{href}" if not href.startswith('http') else href
                    filename = text.strip()[:60].replace('/', '_')
                    if not filename.endswith(('.pdf', '.doc')):
                        filename += '.pdf'
                    save_path = os.path.join(SAVE_DIR, filename)
                    
                    print(f"  下载: {filename}")
                    
                    # curl下载
                    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                    subprocess.run([
                        'curl', '-L', '-o', save_path,
                        '-H', f'Cookie: {cookie_str}',
                        '-A', 'Mozilla/5.0',
                        full_url
                    ], timeout=60)
                    
                    if os.path.exists(save_path):
                        size = os.path.getsize(save_path)
                        print(f"  完成: {size} bytes")
                    break
            else:
                print("  未找到下载链接")
        
        await browser.close()
    print(f"\n保存目录: {SAVE_DIR}")

if __name__ == "__main__":
    asyncio.run(main())
