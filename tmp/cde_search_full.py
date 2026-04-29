#!/usr/bin/env python3
"""
CDE征求意见稿 - 搜索+翻页+下载 v3（完整版）
1. 搜索页输入"征求意见"关键词
2. 翻页遍历所有结果
3. 每页过滤出标题含"征求意见稿"的条目
4. 访问详情页下载附件
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

async def extract_current_page(page):
    """提取当前页所有条目，返回(日期, 标题, URL, 是否含征求意见稿)"""
    await asyncio.sleep(3)

    result = await page.evaluate('''() => {
        const rows = [];
        // 找所有表格行
        const trs = document.querySelectorAll("table tr");
        for (const tr of trs) {
            const tds = tr.querySelectorAll("td");
            if (tds.length < 3) continue;

            // 取每列
            const dateTd = tds[1]; // 发布日期
            const titleTd = tds[2]; // 标题

            const dateText = (dateTd ? dateTd.innerText : "").trim();
            const titleText = (titleTd ? titleTd.innerText : "").trim();

            // 取链接
            const link = titleTd ? titleTd.querySelector("a[href*='zdyz']") : null;
            if (!link) continue;

            const href = link.href;
            rows.push({
                date: dateText,
                title: titleText,
                url: href
            });
        }
        return rows;
    }''')

    return result

async def get_page_count(page):
    await asyncio.sleep(1)
    info = await page.evaluate('''() => {
        const text = document.body.innerText;
        const match = text.match(/共\s*(\d+)\s*条/);
        const total = match ? parseInt(match[1]) : 0;

        // 查找当前页
        const currMatch = text.match(/第\s*(\d+)\s*页/);
        const current = currMatch ? parseInt(currMatch[1]) : 1;

        return { total, current };
    }''')
    return info

async def download_from_detail(browser, pub_date, title, detail_url):
    """访问详情页下载附件"""
    page = await browser.new_page()
    await page.set_extra_http_headers({'User-Agent': get_random_ua()})
    await stealth.Stealth().apply_stealth_async(page)

    downloaded = []
    try:
        await page.goto(detail_url, timeout=60000)
        await asyncio.sleep(6)

        links = await page.query_selector_all('a[href*="downloadAtt"]')
        if not links:
            links = await page.query_selector_all('a[href*="download"]')

        log(f"      发现 {len(links)} 个附件")

        for i, link in enumerate(links):
            href = await link.get_attribute('href')
            if not href:
                continue
            link_text = (await link.inner_text()).strip()[:25]
            href = href if href.startswith('http') else f"https://www.cde.org.cn{href}"

            # 格式化日期
            date_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', pub_date)
            if date_match:
                date_str = f"{date_match.group(1)}{date_match.group(2).zfill(2)}{date_match.group(3).zfill(2)}"
            else:
                date_str = pub_date.replace('-', '')

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
            if ((link.innerText||'').trim() === "下一页") {
                link.click();
                break;
            }
        }
    }''')
    await asyncio.sleep(3)

async def main():
    log("=" * 60)
    log("🚀 CDE征求意见稿 - 搜索+翻页+下载 v3")
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

        page_info = await get_page_count(page)
        log(f"\n📊 搜索结果: 共 {page_info['total']} 条")

        total_downloads = 0
        page_num = 1
        all_seen = set()  # 去重

        while True:
            entries = await extract_current_page(page)
            log(f"\n=== 第 {page_num} 页: 提取到 {len(entries)} 条 ===")

            # 过滤：只保留标题含"征求意见稿"的
            filtered = [e for e in entries if '征求意见稿' in e['title'] and e['url'] not in all_seen]
            log(f"    含'征求意见稿': {len(filtered)} 条")

            for e in filtered:
                all_seen.add(e['url'])
                log(f"[{page_num}-{len(filtered)}] 📄 {e['date']} - {e['title'][:40]}")
                dls = await download_from_detail(browser, e['date'], e['title'], e['url'])
                total_downloads += len(dls)

            # 检查是否还有下一页
            page_info = await get_page_count(page)
            current = page_info['current']

            # 尝试翻页
            has_next = await page.evaluate('''() => {
                const links = document.querySelectorAll("a");
                for (const link of links) {
                    if ((link.innerText||'').trim() === "下一页" && !link.classList.contains("layui-disabled")) {
                        return true;
                    }
                }
                return false;
            }''')

            if not has_next:
                log(f"\n✅ 已到最后一页，停止")
                break

            log(f"    → 翻到第 {page_num + 1} 页...")
            await click_next(page)
            await asyncio.sleep(3)
            page_num += 1

        log(f"\n{'='*60}")
        log(f"✅ 完成！新增 {total_downloads} 个文件")
        log(f"📁 目录: {SAVE_DIR}")
        log(f"📊 目录总计: {len(list(SAVE_DIR.iterdir()))} 个")
        log(f"{'='*60}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
