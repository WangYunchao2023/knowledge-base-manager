#!/usr/bin/env python3
"""CDE征求意见稿下载 - 修复版：先提取URL列表，再逐个下载"""
import asyncio, os, sys, re, json
from pathlib import Path

SAVE_DIR = Path("/home/wangyc/Documents/法规指导原则-征求意见1")
SAVE_DIR.mkdir(parents=True, exist_ok=True)

existing = {f.name for f in SAVE_DIR.iterdir() if f.is_file()}
print(f"📁 已存在文件: {len(existing)} 个")

sys.path.insert(0, '/home/wangyc/.openclaw/workspace/skills/guidance-web-access/scripts')
from web_access import async_playwright, stealth, get_random_ua, BROWSER_ARGS, log

async def extract_list(page):
    """从列表页提取所有条目URL和元数据"""
    await page.goto("https://www.cde.org.cn/zdyz/listpage/3c49fad55caad7a034c263cfc2b6eb9c", timeout=90000)
    
    # 等待页面稳定
    for _round in range(90):
        await asyncio.sleep(1)
        try:
            metrics = await page.evaluate(r'''
                () => ({
                    text_len: (document.body.innerText || '').length,
                    node_count: document.querySelectorAll('.news_item, li').length,
                })
            ''')
            if metrics['text_len'] >= 500 and metrics['node_count'] >= 5 and _round > 5:
                break
        except:
            pass

    # 滚动加载
    for _ in range(3):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)

    # 提取数据
    items = await page.query_selector_all('.news_item')
    entries = []
    for item in items:
        try:
            date_text = await item.inner_text()
            links = await item.query_selector_all('a[href]')
            href = await links[0].get_attribute('href') if links else None
            
            if not href:
                continue
            
            # 提取日期
            date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', date_text)
            if date_match:
                pub_date = f"{date_match.group(1)}{date_match.group(2).zfill(2)}{date_match.group(3).zfill(2)}"
            else:
                pub_date = re.sub(r'\D', '', date_text[:10])
            
            # 提取标题
            title_match = re.search(r'《([^》]+)》', date_text)
            title = title_match.group(1) if title_match else date_text[:50]
            
            detail_url = href if href.startswith('http') else f"https://www.cde.org.cn{href}"
            entries.append({'pub_date': pub_date, 'title': title, 'detail_url': detail_url})
        except:
            continue
    
    return entries

async def download_from_detail(browser, entry):
    """访问详情页下载附件"""
    page = await browser.new_page()
    page.set_extra_http_headers({'User-Agent': get_random_ua()})
    await stealth.Stealth().apply_stealth_async(page)
    
    try:
        await page.goto(entry['detail_url'], timeout=60000)
        await asyncio.sleep(6)
        
        links = await page.query_selector_all('a[href*="downloadAtt"]')
        if not links:
            links = await page.query_selector_all('a[href*="download"]')
        
        downloaded = 0
        for i, link in enumerate(links):
            href = await link.get_attribute('href')
            if not href:
                continue
            
            link_text = (await link.inner_text()).strip()[:20]
            href = href if href.startswith('http') else f"https://www.cde.org.cn{href}"
            
            title_clean = re.sub(r'[\\/:*?"<>|]', '', entry['title'])[:40]
            fname = f"{entry['pub_date']} - {title_clean} - {link_text}.pdf" if i > 0 else f"{entry['pub_date']} - {title_clean}.pdf"
            fpath = SAVE_DIR / fname
            
            if fname in existing or fpath.exists():
                log(f"  ⏭️ 跳过: {fname[:50]}")
                continue
            
            try:
                async with page.expect_download(timeout=30000) as dl_info:
                    await link.click()
                    await asyncio.sleep(2)
                dl = await dl_info.value
                await dl.save_as(fpath)
                size = fpath.stat().st_size // 1024
                log(f"  ✅ {fname[:55]} ({size}KB)")
                downloaded += 1
                existing.add(fname)
            except Exception as e:
                log(f"  ❌ 下载失败: {e}")
        
        return downloaded
    finally:
        await page.close()

async def main():
    log("=" * 60)
    log("🚀 CDE征求意见稿下载")
    log("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=BROWSER_ARGS)
        
        # 第一步：提取列表
        page = await browser.new_page()
        await page.set_extra_http_headers({'User-Agent': get_random_ua()})
        await stealth.Stealth().apply_stealth_async(page)
        
        log("📋 步骤1: 提取征求意见稿列表...")
        entries = await extract_list(page)
        await page.close()
        log(f"✅ 共找到 {len(entries)} 条征求意见稿\n")
        
        # 第二步：逐个下载
        log("📥 步骤2: 逐个下载附件...")
        total_dl = 0
        for idx, entry in enumerate(entries):
            log(f"[{idx+1}/{len(entries)}] 📄 {entry['pub_date']} - {entry['title'][:45]}")
            n = await download_from_detail(browser, entry)
            total_dl += n
        
        log(f"\n{'='*60}")
        log(f"✅ 完成！新增 {total_dl} 个文件")
        log(f"📁 目录总计: {len(list(SAVE_DIR.iterdir()))} 个")
        log(f"{'='*60}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
