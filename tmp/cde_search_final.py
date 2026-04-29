#!/usr/bin/env python3
"""
CDE征求意见稿 - 搜索+翻页+下载 最终版
搜索页结构：Table5 = 征求意见数据表
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

async def do_search(page, keyword):
    await page.evaluate(f'''
        () => {{
            const inputs = document.querySelectorAll("input");
            for (const inp of inputs) {{
                if (inp.name === "searchTitle" || (inp.placeholder && inp.placeholder.includes("标题"))) {{
                    inp.value = "{keyword}";
                    inp.dispatchEvent(new Event("input"));
                    inp.dispatchEvent(new Event("change"));
                    break;
                }}
            }}
        }}
    ''')
    await asyncio.sleep(1)
    await page.evaluate('''() => {
        const btns = document.querySelectorAll("button, a");
        for (const btn of btns) {
            if ((btn.innerText||'').trim() === "检索") { btn.click(); break; }
        }
    }''')
    await asyncio.sleep(8)

async def extract_tables(page):
    """提取所有layui-table中的数据行"""
    result = await page.evaluate('''() => {
        const tables = document.querySelectorAll("table.layui-table");
        const results = [];
        
        for (let ti = 0; ti < tables.length; ti++) {
            const table = tables[ti];
            const rows = table.querySelectorAll("tr");
            
            for (let ri = 1; ri < rows.length; ri++) {  // 跳过表头(ri=0)
                const cells = rows[ri].querySelectorAll("td");
                if (cells.length < 3) continue;
                
                const num = cells[0].innerText.trim();
                const date = cells[1].innerText.trim().replace('关于公开征求', '').trim();
                const titleCell = cells[2];
                const title = titleCell.innerText.trim();
                
                // 提取详情链接
                const link = titleCell.querySelector("a[href]");
                const url = link ? link.href : "";
                
                // 判断是否含"征求意见稿"
                const isConsult = title.includes("征求意见稿");
                
                results.push({
                    table_index: ti,
                    num: num,
                    date: date,
                    title: title,
                    url: url,
                    isConsult: isConsult
                });
            }
        }
        return results;
    }''')
    return result

async def get_pagination_info(page):
    info = await page.evaluate('''() => {
        const text = document.body.innerText;
        const totalMatch = text.match(/共\s*(\d+)\s*条/);
        const total = totalMatch ? parseInt(totalMatch[1]) : 0;
        
        // 找页码信息
        const pageInfo = {
            total: total,
            current: 1,
            hasNext: false,
            pageText: ""
        };
        
        // 查找所有包含"下一页"的链接
        const nextLinks = [];
        document.querySelectorAll("a").forEach(a => {
            if ((a.innerText||'').trim() === "下一页") {
                nextLinks.push({
                    text: a.innerText,
                    href: a.href,
                    className: a.className,
                    disabled: a.classList.contains("layui-disabled")
                });
            }
        });
        
        pageInfo.hasNext = nextLinks.some(l => !l.disabled);
        pageInfo.nextLinks = nextLinks;
        
        return pageInfo;
    }''')
    return info

async def download_from_detail(browser, pub_date, title, detail_url):
    page = await browser.new_page()
    await page.set_extra_http_headers({'User-Agent': get_random_ua()})
    await stealth.Stealth().apply_stealth_async(page)

    downloaded = []
    try:
        await page.goto(detail_url, timeout=60000, wait_until="domcontentloaded")
        
        # 等待页面稳定
        for _ in range(20):
            await asyncio.sleep(1)
            try:
                count = await page.evaluate("document.querySelectorAll('a[href*=\"downloadAtt\"]').length")
                if count > 0:
                    break
            except:
                pass
        
        await asyncio.sleep(3)
        
        try:
            links = await page.query_selector_all('a[href*="downloadAtt"]')
        except Exception as e:
            log(f"      ⚠️ 下载链接提取失败: {e}")
            links = []
        
        if not links:
            try:
                links = await page.query_selector_all('a[href*="download"]')
            except:
                links = []

        log(f"      发现 {len(links)} 个附件")

        for i, link in enumerate(links):
            href = await link.get_attribute('href')
            if not href:
                continue
            link_text = (await link.inner_text()).strip()[:25]
            href = href if href.startswith('http') else f"https://www.cde.org.cn{href}"

            # 解析日期 YYYY-MM-DD -> YYYYMMDD
            date_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', pub_date)
            if date_match:
                date_str = f"{date_match.group(1)}{date_match.group(2).zfill(2)}{date_match.group(3).zfill(2)}"
            else:
                date_str = pub_date.replace('-', '').replace('.', '')

            title_clean = sanitize(title)[:40]
            fname = f"{date_str} - {title_clean} - {sanitize(link_text)}.pdf" if i > 0 else f"{date_str} - {title_clean}.pdf"
            fpath = SAVE_DIR / fname

            if fname in existing or fpath.exists():
                log(f"      ⏭️ 跳过: {fname[:55]}")
                continue

            try:
                async with page.expect_download(timeout=30000) as dl_info:
                    await link.click()
                    await asyncio.sleep(2)
                dl = await dl_info.value
                await dl.save_as(fpath)
                size = fpath.stat().st_size // 1024
                log(f"      ✅ {fname[:55]} ({size}KB)")
                downloaded.append(fname)
                existing.add(fname)
            except Exception as e:
                log(f"      ❌ 下载失败: {e}")
    finally:
        await page.close()
    return downloaded

async def click_next(page):
    await page.evaluate('''() => {
        const links = document.querySelectorAll("a");
        for (const link of links) {
            const t = (link.innerText||'').trim();
            if (t === "下一页" && !link.classList.contains("layui-disabled") && !link.classList.contains("disabled")) {
                link.click();
                break;
            }
        }
    }''')
    await asyncio.sleep(4)

async def main():
    log("=" * 60)
    log("🚀 CDE征求意见稿 - 搜索+翻页+下载 最终版")
    log("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=BROWSER_ARGS)
        page = await browser.new_page()
        await page.set_extra_http_headers({'User-Agent': get_random_ua()})
        await stealth.Stealth().apply_stealth_async(page)

        log("\n🌐 访问搜索页...")
        await page.goto("https://www.cde.org.cn/zdyz/fullsearchpage", timeout=90000)
        await asyncio.sleep(5)

        log("🔍 搜索: 征求意见")
        await do_search(page, "征求意见")

        page_info = await get_pagination_info(page)
        log(f"\n📊 搜索结果: 共 {page_info['total']} 条")

        total_downloads = 0
        page_num = 1
        visited_urls = set()

        while True:
            await asyncio.sleep(3)
            all_rows = await extract_tables(page)

            # 过滤：Table5(征求意见表) + 标题含"征求意见稿"
            consult_rows = [r for r in all_rows if '征求意见稿' in r['title'] and r['url'] and r['url'] not in visited_urls]
            
            log(f"\n=== 第 {page_num} 页: 总条目={len(all_rows)}, 征求意见稿={len(consult_rows)} ===")

            for r in consult_rows:
                visited_urls.add(r['url'])
                log(f"[{page_num}] 📄 {r['date']} - {r['title'][:45]}")
                dls = await download_from_detail(browser, r['date'], r['title'], r['url'])
                total_downloads += len(dls)

            # 检查是否有下一页
            page_info = await get_pagination_info(page)
            if not page_info['hasNext']:
                log(f"\n✅ 已到最后一页，停止")
                break

            log(f"    → 翻到第 {page_num + 1} 页...")
            await click_next(page)
            page_num += 1

        log(f"\n{'='*60}")
        log(f"✅ 完成！新增 {total_downloads} 个文件")
        log(f"📁 目录: {SAVE_DIR}")
        log(f"📊 目录总计: {len(list(SAVE_DIR.iterdir()))} 个")
        log(f"{'='*60}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
