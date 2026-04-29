#!/usr/bin/env python3
"""
CDE征求意见稿 - 搜索+翻页+下载
1. 在搜索页以"征求意见"为关键词搜索
2. 翻页遍历所有结果
3. 每页下载所有相关附件
"""
import asyncio, os, sys, re
from pathlib import Path

SAVE_DIR = Path("/home/wangyc/Documents/法规指导原则-征求意见1")
SAVE_DIR.mkdir(parents=True, exist_ok=True)

# 已存在的文件（用于增量跳过）
existing = {f.name for f in SAVE_DIR.iterdir() if f.is_file()}
print(f"📁 已存在文件: {len(existing)} 个")

sys.path.insert(0, '/home/wangyc/.openclaw/workspace/skills/guidance-web-access/scripts')
from web_access import async_playwright, stealth, get_random_ua, BROWSER_ARGS, log

def sanitize(name):
    return re.sub(r'[\\/:*?"<>|]', '', name)

async def do_search(page, keyword):
    """在搜索页执行搜索"""
    # 点击标题输入框并输入
    await page.evaluate("""
        () => {
            // 找到搜索框并填值
            const inputs = document.querySelectorAll('input');
            for (const inp of inputs) {
                if (inp.placeholder && (inp.placeholder.includes('标题') || inp.name === 'searchTitle')) {
                    inp.value = '';
                    inp.dispatchEvent(new Event('input'));
                }
            }
        }
    """)
    await asyncio.sleep(0.5)

    # 使用JavaScript直接设置输入框值
    await page.evaluate(f"""
        () => {{
            const inputs = document.querySelectorAll('input');
            for (const inp of inputs) {{
                if (inp.placeholder && (inp.placeholder.includes('标题') || inp.name === 'searchTitle')) {{
                    inp.value = '{keyword}';
                    inp.dispatchEvent(new Event('input'));
                    inp.dispatchEvent(new Event('change'));
                    break;
                }}
            }}
        }}
    """)
    await asyncio.sleep(1)

    # 点击搜索按钮
    await page.evaluate("""
        () => {
            const buttons = document.querySelectorAll('button, a, input[type="button"], input[type="submit"]');
            for (const btn of buttons) {
                const text = btn.innerText || btn.value || '';
                if (text.includes('检索') || text.includes('搜索') || text.includes('查询')) {
                    btn.click();
                    break;
                }
            }
        }
    """)
    await asyncio.sleep(3)

async def get_total_pages(page):
    """获取总页数"""
    try:
        info = await page.evaluate(r'''
            () => {
                const text = document.body.innerText;
                // 匹配"共 X 条"或"共 X 页"
                const match = text.match(/共\s*(\d+)\s*(条|页)/);
                const total = match ? parseInt(match[1]) : 0;

                // 查找当前页码
                const pageMatch = text.match(/第\s*(\d+)\s*页/);
                const currentPage = pageMatch ? parseInt(pageMatch[1]) : 1;

                // 查找总页数
                const totalPageMatch = text.match(/共\s*\d+\s*页.*?第\s*(\d+)\s*页/);
                const totalPages = totalPageMatch ? parseInt(totalPageMatch[1]) : 1;

                return { total, currentPage, totalPages };
            }
        ''')
        return info
    except:
        return {'total': 0, 'currentPage': 1, 'totalPages': 1}

async def get_page_items(page):
    """提取当前页所有条目"""
    await asyncio.sleep(2)

    items = await page.query_selector_all('.news_item')
    log(f"    当前页发现 {len(items)} 条")

    entries = []
    for item in items:
        try:
            # 提取日期
            date_text = await item.inner_text()
            date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', date_text)
            pub_date = f"{date_match.group(1)}{date_match.group(2).zfill(2)}{date_match.group(3).zfill(2)}" if date_match else ""

            # 提取标题
            title_match = re.search(r'《([^》]+)》', date_text)
            title = title_match.group(1) if title_match else date_text[:60]

            # 提取详情URL
            links = await item.query_selector_all('a[href]')
            detail_url = None
            for link in links:
                href = await link.get_attribute('href')
                if href and ('detail' in href or 'zdyz' in href) and 'listpage' not in href:
                    detail_url = href if href.startswith('http') else f"https://www.cde.org.cn{href}"
                    break

            if detail_url:
                entries.append({
                    'pub_date': pub_date,
                    'title': title,
                    'detail_url': detail_url,
                    'source_text': date_text
                })
        except Exception as e:
            continue

    return entries

async def download_from_detail(browser, entry):
    """从详情页下载附件"""
    page = await browser.new_page()
    await page.set_extra_http_headers({'User-Agent': get_random_ua()})
    await stealth.Stealth().apply_stealth_async(page)

    downloaded = []
    try:
        await page.goto(entry['detail_url'], timeout=60000)
        await asyncio.sleep(6)

        # 查找所有下载链接
        links = await page.query_selector_all('a[href*="downloadAtt"]')
        if not links:
            links = await page.query_selector_all('a[href*="download"]')

        log(f"      发现 {len(links)} 个下载链接")

        for i, link in enumerate(links):
            href = await link.get_attribute('href')
            if not href:
                continue

            link_text = (await link.inner_text()).strip()[:25]
            href = href if href.startswith('http') else f"https://www.cde.org.cn{href}"

            title_clean = sanitize(entry['title'])[:40]
            fname = f"{entry['pub_date']} - {title_clean} - {sanitize(link_text)}.pdf" if i > 0 else f"{entry['pub_date']} - {title_clean}.pdf"
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

async def go_to_page(page, page_num):
    """跳转到指定页码"""
    try:
        # 尝试使用页码跳转
        await page.evaluate(f"""
            () => {{
                // 尝试找到页码输入框
                const inputs = document.querySelectorAll('input');
                for (const inp of inputs) {{
                    if (inp.className && inp.className.includes('layui-input')) {{
                        inp.value = '{page_num}';
                        inp.dispatchEvent(new Event('input'));
                        inp.dispatchEvent(new Event('change'));

                        // 查找确定按钮
                        const btn = inp.nextElementSibling;
                        if (btn && btn.innerText.includes('确定')) {{
                            btn.click();
                        }}
                        break;
                    }}
                }}

                // 备用方案：直接触发layui分页
                const laypage = document.querySelector('.layui-laypage');
                if (laypage) {{
                    const event = new CustomEvent('laypage', {{detail: {{curr: {page_num}}}}});
                    laypage.dispatchEvent(event);
                }}
            }}
        """)
        await asyncio.sleep(3)
        return True
    except Exception as e:
        log(f"      ⚠️ 跳转页码失败: {e}")
        return False

async def click_next_page(page):
    """点击下一页"""
    try:
        await page.evaluate("""
            () => {
                const links = document.querySelectorAll('a');
                for (const link of links) {
                    if (link.innerText === '下一页' && !link.classList.contains('disabled')) {
                        link.click();
                        break;
                    }
                }
            }
        """)
        await asyncio.sleep(3)
        return True
    except:
        return False

async def main():
    log("=" * 60)
    log("🚀 CDE征求意见稿 - 搜索+翻页+下载")
    log("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=BROWSER_ARGS)
        page = await browser.new_page()
        await page.set_extra_http_headers({'User-Agent': get_random_ua()})
        await stealth.Stealth().apply_stealth_async(page)

        # 访问搜索页
        log("\n🌐 访问搜索页...")
        await page.goto("https://www.cde.org.cn/zdyz/fullsearchpage", timeout=90000)
        await asyncio.sleep(5)

        # 执行搜索
        log("🔍 搜索关键词: 征求意见")
        await do_search(page, "征求意见")

        # 等待搜索结果
        for _round in range(60):
            await asyncio.sleep(1)
            try:
                metrics = await page.evaluate(r'''
                    () => ({
                        text_len: (document.body.innerText || '').length,
                        node_count: document.querySelectorAll('.news_item').length,
                    })
                ''')
                if metrics['node_count'] > 0 and _round > 3:
                    break
            except:
                pass

        # 获取总页数
        page_info = await get_total_pages(page)
        total = page_info['total']
        current = page_info['currentPage']
        log(f"\n📊 搜索结果: 共 {total} 条，当前第 {current} 页")

        total_downloads = 0
        page_num = 1

        while True:
            # 提取当前页条目
            entries = await get_page_items(page)
            log(f"\n--- 第 {page_num} 页: 发现 {len(entries)} 条 ---")

            for idx, entry in enumerate(entries):
                log(f"[{idx+1}/{len(entries)}] 📄 {entry['pub_date']} - {entry['title'][:40]}")
                dls = await download_from_detail(browser, entry)
                total_downloads += len(dls)

            # 检查是否有下一页
            page_info = await get_total_pages(page)
            current = page_info['currentPage']

            # 尝试点击下一页
            has_next = await page.evaluate("""
                () => {
                    const links = document.querySelectorAll('a');
                    for (const link of links) {
                        if (link.innerText === '下一页' && !link.classList.contains('disabled') && !link.classList.contains('layui-disabled')) {
                            return true;
                        }
                    }
                    return false;
                }
            """)

            if not has_next:
                log(f"\n✅ 已到最后一页，停止翻页")
                break

            log(f"    → 翻到第 {page_num + 1} 页...")
            await click_next_page(page)
            await asyncio.sleep(3)
            page_num += 1

            # 防呆：如果页码没变但还有内容，继续尝试
            new_info = await get_total_pages(page)
            if new_info['currentPage'] == current and page_num > 1:
                log(f"    页码未变，假设已到底")
                break

        log(f"\n{'='*60}")
        log(f"✅ 任务完成！新增 {total_downloads} 个文件")
        log(f"📁 目录: {SAVE_DIR}")
        log(f"📊 目录总计: {len(list(SAVE_DIR.iterdir()))} 个文件")
        log(f"{'='*60}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
