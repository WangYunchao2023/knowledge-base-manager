#!/usr/bin/env python3
"""CDE征求意见稿下载 - 使用guidance-web-access的核心函数"""
import asyncio, os, sys, re, json
from pathlib import Path

SAVE_DIR = Path("/home/wangyc/Documents/法规指导原则-征求意见")
SAVE_DIR.mkdir(parents=True, exist_ok=True)

# 已有的文件
existing = {f.name for f in SAVE_DIR.iterdir() if f.is_file()}
print(f"📁 已存在文件: {len(existing)} 个")

sys.path.insert(0, '/home/wangyc/.openclaw/workspace/skills/guidance-web-access/scripts')
from web_access import async_playwright, stealth, get_random_ua, BROWSER_ARGS, log

async def main():
    print("=" * 60)
    print("🚀 CDE征求意见稿下载 - guidance-web-access核心")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=BROWSER_ARGS)
        page = await browser.new_page()
        ua = get_random_ua()
        await page.set_extra_http_headers({'User-Agent': ua})
        await stealth.Stealth().apply_stealth_async(page)

        log("🌐 导航到征求意见列表页...")
        await page.goto("https://www.cde.org.cn/zdyz/listpage/3c49fad55caad7a034c263cfc2b6eb9c", timeout=90000)

        # 使用稳定性检测等待页面加载
        log("⏳ 等待页面内容加载...")
        prev_text_len = 0
        prev_node_count = 0
        for _round in range(90):  # 最多90秒
            await asyncio.sleep(1)
            try:
                metrics = await page.evaluate(r'''
                    () => {
                        const nodeCount = document.querySelectorAll(
                            '.news_item, li, tr, .article-item, .list-item, .item, .result-item, div[class*="news"]'
                        ).length;
                        const linkCount = document.querySelectorAll('a[href]').length;
                        return {
                            text_len: (document.body.innerText || '').length,
                            node_count: nodeCount,
                            link_count: linkCount
                        };
                    }
                ''')
                text_delta = abs(metrics['text_len'] - prev_text_len)
                node_delta = abs(metrics['node_count'] - prev_node_count)
                has_content = metrics['text_len'] >= 500 or metrics['node_count'] >= 5

                if text_delta < 100 and node_delta < 3 and has_content and _round > 5:
                    log(f"    ✅ 页面已稳定 (文本约{metrics['text_len']}字, 节点约{metrics['node_count']}个)")
                    break

                prev_text_len = metrics['text_len']
                prev_node_count = metrics['node_count']

                if _round % 10 == 0:
                    log(f"    ⏳ 等待中... (文本约{metrics['text_len']}字, 节点约{metrics['node_count']}个)")
            except Exception as e:
                log(f"    ⚠️ 检测异常: {e}")

        # 滚动加载
        log("📜 滚动加载...")
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)

        # 提取内容
        items = await page.query_selector_all('.news_item')
        log(f"📋 发现 {len(items)} 条")

        all_downloads = []
        for idx, item in enumerate(items):
            try:
                date_el = await item.query_selector('.news_date')
                title_el = await item.query_selector('.news_content_title')
                if not date_el or not title_el:
                    continue

                date_text = (await date_el.inner_text()).strip()
                title_text = (await title_el.inner_text()).strip()

                date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', date_text)
                pub_date = f"{date_match.group(1)}{date_match.group(2).zfill(2)}{date_match.group(3).zfill(2)}" if date_match else date_text.replace('.', '')

                # 查找详情链接
                detail_link = await item.query_selector('a[href]')
                detail_href = await detail_link.get_attribute('href') if detail_link else None

                log(f"[{idx+1}/{len(items)}] 📄 {pub_date} - {title_text[:50]}")

                if detail_href:
                    detail_url = detail_href if detail_href.startswith('http') else f"https://www.cde.org.cn{detail_href}"

                    # 访问详情页下载
                    await page.goto(detail_url, timeout=60000)
                    await asyncio.sleep(6)

                    links = await page.query_selector_all('a[href*="downloadAtt"]')
                    for i, link in enumerate(links):
                        href = await link.get_attribute('href')
                        link_text = (await link.inner_text()).strip()[:20]
                        if not href:
                            continue
                        href = href if href.startswith('http') else f"https://www.cde.org.cn{href}"

                        short_title = title_text[:40].replace('/', '')
                        fname = f"{pub_date} - {short_title} - {link_text}.pdf" if i > 0 else f"{pub_date} - {short_title}.pdf"
                        fpath = SAVE_DIR / fname

                        if fname in existing or fpath.exists():
                            log(f"  ⏭️ 跳过(已存在)")
                            continue

                        try:
                            async with page.expect_download(timeout=30000) as dl_info:
                                await link.click()
                                await asyncio.sleep(2)
                            dl = await dl_info.value
                            await dl.save_as(fpath)
                            size = fpath.stat().st_size // 1024
                            log(f"  ✅ {fname[:50]} ({size}KB)")
                            all_downloads.append(fname)
                            existing.add(fname)
                        except Exception as e:
                            log(f"  ❌ 下载失败: {e}")
            except Exception as e:
                log(f"[{idx+1}] ❌ 处理失败: {e}")

        log(f"\n{'='*60}")
        log(f"✅ 下载完成！新增 {len(all_downloads)} 个文件")
        log(f"📁 目录总计: {len(list(SAVE_DIR.iterdir()))} 个")
        log(f"{'='*60}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
