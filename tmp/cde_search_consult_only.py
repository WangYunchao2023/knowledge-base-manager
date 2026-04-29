#!/usr/bin/env python3
"""
CDE征求意见稿 - 精确版
策略：搜索"征求意见"，在所有结果中只下载标题含"征求意见稿"的条目
但由于搜索结果混入了发布通告，改用列表页逐页遍历
"""
import asyncio, os, sys, re
from pathlib import Path

SAVE_DIR = Path("/home/wangyc/Documents/法规指导原则-征求意见1")
SAVE_DIR.mkdir(parents=True, exist_ok=True)
existing = {f.name for f in SAVE_DIR.iterdir() if f.is_file()}
print(f"📁 已存在: {len(existing)} 个")

sys.path.insert(0, '/home/wangyc/.openclaw/workspace/skills/guidance-web-access/scripts')
from web_access import async_playwright, stealth, get_random_ua, BROWSER_ARGS, log

def sanitize(name):
    return re.sub(r'[\\/:*?"<>|]', '', name)

async def extract_consult_items(page):
    """提取当前页所有含'征求意见稿'的条目"""
    result = await page.evaluate('''() => {
        const tables = document.querySelectorAll("table.layui-table");
        const items = [];
        
        for (let ti = 0; ti < tables.length; ti++) {
            const rows = tables[ti].querySelectorAll("tr");
            for (let ri = 1; ri < rows.length; ri++) {
                const cells = rows[ri].querySelectorAll("td");
                if (cells.length < 3) continue;
                
                const titleCell = cells[2];
                const title = titleCell.innerText.trim();
                
                if (!title.includes("征求意见稿")) continue;
                
                const date = cells[1].innerText.trim();
                const link = titleCell.querySelector("a[href]");
                const url = link ? link.href : "";
                
                items.push({ date, title, url });
            }
        }
        return items;
    }''')
    return result

async def get_page_info(page):
    info = await page.evaluate('''() => {
        // 找所有 layui-laypage 的分页信息
        const laypages = document.querySelectorAll(".layui-laypage");
        let totalPages = 0;
        let currentPage = 1;
        let hasNext = false;
        
        for (const lp of laypages) {
            const lastEl = lp.querySelector(".layui-laypage-last");
            const currEl = lp.querySelector(".layui-laypage-curr em");
            const nextEl = lp.querySelector(".layui-laypage-next");
            
            if (lastEl) {
                const m = lastEl.innerText.match(/(\\d+)/);
                if (m) totalPages = parseInt(m[1]);
            }
            if (currEl) {
                const m = currEl.innerText.match(/(\\d+)/);
                if (m) currentPage = parseInt(m[1]);
            }
            if (nextEl && !nextEl.classList.contains("layui-disabled")) {
                hasNext = true;
            }
        }
        
        return { totalPages, currentPage, hasNext };
    }''')
    return info

async def go_to_page(page, num):
    await page.evaluate(f'''
        () => {{
            const links = document.querySelectorAll("a");
            for (const link of links) {{
                if (link.innerText.trim() === String({num}) && link.className !== "layui-laypage-em") {{
                    link.click();
                    return;
                }}
            }}
        }}
    ''')
    await asyncio.sleep(5)

def quick_check(entry):
    """快速检查：条目是否需要下载（通过文件名判断）"""
    dm = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', entry['date'])
    date_str = f"{dm.group(1)}{dm.group(2).zfill(2)}{dm.group(3).zfill(2)}" if dm else entry['date'].replace('-','').replace('.','')
    tc = sanitize(entry['title'])[:40]
    # 检查主文件是否存在
    main_name = f"{date_str} - {tc}.pdf"
    if main_name in existing:
        return False  # 已存在，跳过
    return True  # 需要下载

async def download_one(browser, entry):
    page = await browser.new_page()
    await page.set_extra_http_headers({'User-Agent': get_random_ua()})
    await stealth.Stealth().apply_stealth_async(page)
    
    downloaded = []
    try:
        await page.goto(entry['url'], timeout=60000, wait_until="domcontentloaded")
        
        for _ in range(20):
            await asyncio.sleep(1)
            try:
                n = await page.evaluate("document.querySelectorAll('a[href*=\"downloadAtt\"]').length")
                if n > 0: break
            except: pass
        
        await asyncio.sleep(3)
        
        try:
            links = await page.query_selector_all('a[href*="downloadAtt"]')
        except: links = []
        if not links:
            try:
                links = await page.query_selector_all('a[href*="download"]')
            except: links = []
        
        log(f"      附件 {len(links)} 个")
        
        for i, link in enumerate(links):
            href = await link.get_attribute('href')
            if not href: continue
            link_text = (await link.inner_text()).strip()[:25]
            href = href if href.startswith('http') else f"https://www.cde.org.cn{href}"
            
            dm = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', entry['date'])
            date_str = f"{dm.group(1)}{dm.group(2).zfill(2)}{dm.group(3).zfill(2)}" if dm else entry['date'].replace('-','').replace('.','')
            
            tc = sanitize(entry['title'])[:40]
            fname = f"{date_str} - {tc} - {sanitize(link_text)}.pdf" if i > 0 else f"{date_str} - {tc}.pdf"
            fp = SAVE_DIR / fname
            
            if fname in existing or fp.exists():
                log(f"      ⏭️ {fname[:50]}")
                continue
            
            try:
                async with page.expect_download(timeout=30000) as di:
                    await link.click()
                    await asyncio.sleep(2)
                dl = await di.value
                await dl.save_as(fp)
                sz = fp.stat().st_size // 1024
                log(f"      ✅ {fname[:50]} ({sz}KB)")
                downloaded.append(fname)
                existing.add(fname)
            except Exception as e:
                log(f"      ❌ {e}")
    finally:
        await page.close()
    return downloaded

async def main():
    log("=" * 60)
    log("🚀 CDE征求意见稿下载 - 精确版")
    log("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=BROWSER_ARGS)
        page = await browser.new_page()
        await page.set_extra_http_headers({'User-Agent': get_random_ua()})
        await stealth.Stealth().apply_stealth_async(page)
        
        # 方法：直接访问列表页（征求意见Tab）
        # 该Tab的URL包含所有征求意见条目
        log("\n🌐 访问征求意见列表页...")
        
        # 尝试列表页
        await page.goto("https://www.cde.org.cn/zdyz/listpage/3c49fad55caad7a034c263cfc2b6eb9c", timeout=90000)
        await asyncio.sleep(10)
        
        # 获取总页数
        page_info = await get_page_info(page)
        log(f"📊 列表页分页: 第 {page_info['currentPage']} 页")
        
        # 如果列表页只有少量条目，切换到搜索页策略
        # 先在搜索页搜索"征求意见稿"（精确标题匹配）
        total_downloads = 0
        visited = set()
        
        # 策略1：搜索页搜索"征求意见稿"
        log("\n🔍 策略1: 搜索页搜索'征求意见稿'")
        await page.goto("https://www.cde.org.cn/zdyz/fullsearchpage", timeout=90000)
        await asyncio.sleep(5)
        
        await page.evaluate('''() => {
            const inputs = document.querySelectorAll("input");
            for (const inp of inputs) {
                if (inp.name === "searchTitle" || (inp.placeholder && inp.placeholder.includes("标题"))) {
                    inp.value = "征求意见稿";
                    inp.dispatchEvent(new Event("input"));
                    inp.dispatchEvent(new Event("change"));
                    break;
                }
            }
        }''')
        await asyncio.sleep(1)
        await page.evaluate('''() => {
            const btns = document.querySelectorAll("button, a");
            for (const btn of btns) {
                if ((btn.innerText||'').trim() === "检索") { btn.click(); break; }
            }
        }''')
        await asyncio.sleep(8)
        
        pi = await get_page_info(page)
        total_p = pi.get('totalPages', 0) or 0
        log(f"  搜索'征求意见稿': 共 {total_p} 页")
        
        for pnum in range(1, total_p + 1):
            if pnum > 1:
                await go_to_page(page, str(pnum))
            
            items = await extract_consult_items(page)
            if not items:
                break
            
            log(f"\n  第 {pnum}/{total_p} 页: {len(items)} 条征求意见稿")
            
            for item in items:
                if item['url'] in visited or not item['url']:
                    continue
                
                # 快速跳过已存在的条目
                if not quick_check(item):
                    log(f"  ⏭️ {item['date']} - {item['title'][:40]} (已存在)")
                    visited.add(item['url'])
                    continue
                
                visited.add(item['url'])
                log(f"  📄 {item['date']} - {item['title'][:40]}")
                try:
                    dls = await download_one(browser, item)
                    total_downloads += len(dls)
                except Exception as e:
                    log(f"  ⚠️ 下载出错: {e}")
        
        log(f"\n{'='*60}")
        log(f"✅ 完成！新增 {total_downloads} 个文件")
        log(f"📁 目录: {SAVE_DIR}")
        log(f"📊 目录总计: {len(list(SAVE_DIR.iterdir()))} 个")
        log(f"{'='*60}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
