#!/usr/bin/env python3
"""
FDA Guidance Documents - Meeting/Communication Related
v1.3.1 - Playwright page.request.get() 下载PDF
"""
import asyncio
import re
from pathlib import Path
from playwright.async_api import async_playwright

VERSION = "1.3.1"

SAVE_DIR = Path.home() / "Documents" / "工作" / "法规指导原则" / "FDA沟通交流"
SAVE_DIR.mkdir(parents=True, exist_ok=True)

MEETING_KEYWORDS = [
    "meeting", "meetings", "advisory committee", "advisory committees",
    "communication", "correspondence", "industry day", "town hall",
    "public meeting", "hearing", "workshop", "conference"
]

def make_filename(title, date=""):
    title = re.sub(r'[\\/:*?"<>|]', '', title)
    title = title[:100].strip()
    # 日期中的 / 替换为 -
    date = date.replace('/', '-') if date else ""
    return (f"{date} - {title}.pdf" if date else f"{title}.pdf")

def log(msg):
    print(f"  {msg}")

async def get_table_data(page):
    rows = await page.query_selector_all('#DataTables_Table_0 tbody tr')
    results = []
    for row in rows:
        cells = await row.query_selector_all('td')
        if len(cells) < 5:
            continue
        title_link = await cells[0].query_selector('a[href]')
        pdf_link = await cells[1].query_selector('a[href]')
        title_text = (await title_link.inner_text()).strip() if title_link else ""
        href = (await title_link.get_attribute('href')) if title_link else ""
        title_url = f"https://www.fda.gov{href}" if href else ""
        pdf_href = (await pdf_link.get_attribute('href')) if pdf_link else ""
        pdf_url = f"https://www.fda.gov{pdf_href}" if pdf_href else ""
        results.append({
            "title": title_text,
            "title_url": title_url,
            "pdf_url": pdf_url,
            "date": (await cells[2].inner_text()).strip(),
            "topic": (await cells[4].inner_text()).strip(),
        })
    return results

async def get_total_count(page):
    text = await page.inner_text('body')
    m = re.search(r'Showing\s+\d+\s+to\s+\d+\s+of\s+([\d,]+)', text)
    return int(m.group(1).replace(',', '')) if m else 0

async def apply_search(page, keyword):
    await page.evaluate(
        f"var t=jQuery('#DataTables_Table_0').DataTable(); t.search('{keyword}').draw();"
    )
    await page.wait_for_timeout(3000)

async def download_pdf(page, url, filepath):
    if filepath.exists():
        return "skipped"
    try:
        resp = await page.request.get(url)
        if resp.ok and resp.status == 200:
            data = await resp.body()
            ct = resp.headers.get('content-type', '')
            if data[:4] == b'%PDF' or 'pdf' in ct.lower():
                filepath.write_bytes(data)
                return "downloaded"
    except Exception as e:
        pass
    return "failed"

async def main():
    print(f"🚀 FDA 沟通交流指导原则下载器 v{VERSION}")
    print(f"📁 保存目录: {SAVE_DIR}")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        page.set_default_timeout(60000)

        print("\n📍 Step 1: 访问FDA指导原则页面...")
        await page.goto(
            "https://www.fda.gov/regulatory-information/search-fda-guidance-documents",
            wait_until="domcontentloaded"
        )
        await page.wait_for_selector('#DataTables_Table_0', timeout=15000)
        await page.wait_for_timeout(3000)
        total = await get_total_count(page)
        print(f"   总记录: {total}")

        print("\n📍 Step 2: DataTables搜索 'meeting'...")
        await apply_search(page, "meeting")
        count = await get_total_count(page)
        print(f"   命中: {count} 条")
        
        meeting_rows = await get_table_data(page)
        filtered = [r for r in meeting_rows
                    if any(k in (r["title"]+" "+r["topic"]+" "+r["title_url"]).lower() 
                           for k in MEETING_KEYWORDS)]
        print(f"   关键词精确匹配: {len(filtered)} 条")

        print("\n   匹配到的指导原则:")
        for row in filtered:
            print(f"   • [{row['date']}] {row['title'][:65]}")
            print(f"     PDF: {row['pdf_url']}")

        print("\n📍 Step 3: 下载PDF...")
        downloaded = 0
        skipped = 0
        failed_urls = []
        
        for i, row in enumerate(filtered, 1):
            if not row["pdf_url"]:
                continue
            fname = make_filename(row["title"], row["date"])
            fpath = SAVE_DIR / fname
            
            print(f"\n  [{i}/{len(filtered)}] {row['title'][:55]}")
            result = await download_pdf(page, row["pdf_url"], fpath)
            
            if result == "downloaded":
                downloaded += 1
                print(f"       ✅ 已下载: {fname} ({fpath.stat().st_size // 1024}KB)")
            elif result == "skipped":
                skipped += 1
                print(f"       ⏭️  已存在")
            else:
                failed_urls.append((row["title"], row["pdf_url"]))
                print(f"       ❌ 下载失败")

        print(f"\n{'='*60}")
        print(f"✅ 完成! 新下载: {downloaded} | 已存在: {skipped} | 失败: {len(failed_urls)}")
        
        files = sorted(SAVE_DIR.glob("*.pdf"))
        print(f"📁 {SAVE_DIR}")
        print(f"   共 {len(files)} 个PDF:")
        for f in files:
            print(f"   • {f.name} ({f.stat().st_size // 1024}KB)")

        if failed_urls:
            print(f"\n⚠️  失败记录:")
            for title, url in failed_urls:
                print(f"   [{title[:50]}] -> {url}")

        await ctx.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
