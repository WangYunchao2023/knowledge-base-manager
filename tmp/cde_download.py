#!/usr/bin/env python3
"""
CDE沟通交流指导原则下载脚本
使用非headless模式，等待30秒让JavaScript加载
"""
import asyncio
import os
from playwright.async_api import async_playwright

SAVE_DIR = "/home/wangyc/Documents/工作/法规指导原则"

# 沟通交流相关指导原则详情页URL
PAGES = [
    ("药物研发与技术审评沟通交流会议申请资料参考", 
     "https://www.cde.org.cn/main/policy/regulatview/df2135f1f1ad1af14318efb3689828a4"),
    ("儿童用药沟通交流中Ⅰ类会议申请及管理工作细则",
     "https://www.cde.org.cn/main/policy/regulatview/05b555deca24fce53c68d73cc77512c2"),
    ("药品研发与技术审评沟通交流办法",
     "https://www.cde.org.cn/main/policy/view/e18ffdbad3bc73381c359eb454790568"),
    ("细胞和基因治疗产品临床相关沟通交流技术指导原则",
     "https://www.cde.org.cn/main/news/viewInfoCommon/3dafaa3e4fe647efab4f80a06d0b7d3e"),
    ("真实世界证据支持药物注册申请的沟通交流指导原则",
     "https://www.cde.org.cn/main/news/viewInfoCommon/f6efe3e4d2ac4fcf8ef4760a4be6b9e0"),
    ("基于三结合注册审评证据体系下的沟通交流指导原则",
     "https://www.cde.org.cn/main/news/viewInfoCommon/7f8df5e4d2ac4fcf8ef4760a4be6b9e1"),
]

async def download_pdf():
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # 必须使用可见浏览器
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        context = await browser.new_context()
        
        for title, url in PAGES:
            print(f"\n{'='*50}")
            print(f"处理: {title}")
            print(f"URL: {url}")
            
            page = await context.new_page()
            
            try:
                await page.goto(url, wait_until='load', timeout=60000)
                print("等待JavaScript加载...")
                await asyncio.sleep(30)  # 关键：等待30秒
                
                # 获取所有链接
                links = await page.query_selector_all('a')
                print(f"找到 {len(links)} 个链接")
                
                # 查找PDF/DOC下载链接
                downloaded = False
                for link in links:
                    try:
                        href = await link.get_attribute('href')
                        text = await link.inner_text()
                        
                        if href and (('pdf' in href.lower()) or ('doc' in href.lower()) or 
                                     ('xlsx' in href.lower()) or ('附件' in text) or ('下载' in text)):
                            full_url = href if href.startswith('http') else f"https://www.cde.org.cn{href}"
                            
                            # 尝试下载
                            if 'pdf' in href.lower() or 'doc' in href.lower():
                                print(f"  发现下载: {text.strip()}")
                                print(f"  URL: {full_url}")
                                
                                # 使用curl下载
                                filename = text.strip()
                                if not filename:
                                    filename = f"{title}.pdf"
                                
                                # 清理文件名
                                filename = filename.replace('/', '_').replace('\\', '_')
                                if not filename.endswith(('.pdf', '.doc', '.docx', '.xlsx')):
                                    filename += '.pdf'
                                
                                save_path = os.path.join(SAVE_DIR, filename)
                                print(f"  下载到: {save_path}")
                                
                                os.system(f'curl -L -o "{save_path}" "{full_url}" 2>/dev/null')
                                
                                if os.path.exists(save_path):
                                    size = os.path.getsize(save_path)
                                    print(f"  下载完成! 大小: {size} bytes")
                                    if size < 10000:  # 文件太小可能是HTML
                                        print(f"  警告: 文件可能不是PDF")
                                        os.remove(save_path)
                                    
                                downloaded = True
                    except Exception as e:
                        print(f"  错误: {e}")
                
                if not downloaded:
                    print("  未找到下载链接")
                    
            except Exception as e:
                print(f"  错误: {e}")
            
            await page.close()
        
        await browser.close()
    
    print(f"\n完成! 文件保存在: {SAVE_DIR}")

if __name__ == "__main__":
    asyncio.run(download_pdf())
