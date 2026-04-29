#!/usr/bin/env python3
"""
CDE征求意见稿下载脚本 - 完整流程
在单个浏览器会话中完成：列表页 -> 详情页 -> 下载附件
"""
import asyncio, os, sys, re, json
from pathlib import Path
from datetime import datetime

# CDE搜索页URL
LIST_URL = "https://www.cde.org.cn/zdyz/listpage/3c49fad55caad7a034c263cfc2b6eb9c"
SAVE_DIR = Path("/home/wangyc/Documents/法规指导原则-征求意见")
SAVE_DIR.mkdir(parents=True, exist_ok=True)

# 已有的文件（增量跳过）
existing = set()
for f in SAVE_DIR.iterdir():
    if f.is_file():
        existing.add(f.name)

print(f"📁 已存在文件: {len(existing)} 个")

def sanitize_filename(name):
    """清理文件名中的非法字符"""
    return re.sub(r'[\\/:*?"<>|]', '', name)

async def download_from_detail_page(page, detail_url, pub_date, title):
    """访问详情页，下载附件"""
    try:
        await page.goto(detail_url, timeout=60000)
        await asyncio.sleep(6)  # 等待动态内容加载

        # 查找附件下载链接
        links = await page.query_selector_all('a[href*="downloadAtt"]')
        if not links:
            # 尝试其他下载链接格式
            links = await page.query_selector_all('a[href*="download"]')

        downloaded = []
        for i, link in enumerate(links):
            href = await link.get_attribute('href')
            if not href:
                continue

            # 获取链接文本作为文件名的一部分
            link_text = await link.inner_text()
            link_text = sanitize_filename(link_text.strip())[:30]

            # 完整URL
            if href.startswith('/'):
                href = f"https://www.cde.org.cn{href}"

            # 生成文件名
            short_title = sanitize_filename(title)[:40]
            if i > 0:
                fname = f"{pub_date} - {short_title} - {link_text}.pdf"
            else:
                fname = f"{pub_date} - {short_title}.pdf"

            fpath = SAVE_DIR / fname

            # 增量跳过
            if fname in existing or fpath.exists():
                print(f"  ⏭️ 跳过(已存在): {fname[:60]}")
                continue

            # 下载文件
            try:
                async with page.expect_download(timeout=30000) as dl_info:
                    await link.click()
                    await asyncio.sleep(2)

                dl = await dl_info.value
                await dl.save_as(fpath)

                size = fpath.stat().st_size // 1024
                print(f"  ✅ 下载: {fname[:60]} ({size}KB)")
                downloaded.append(fname)
                existing.add(fname)
            except Exception as e:
                print(f"  ❌ 下载失败: {fname[:60]} - {e}")

        return downloaded
    except Exception as e:
        print(f"  ❌ 详情页访问失败: {detail_url} - {e}")
        return []

async def main():
    print("=" * 60)
    print("🚀 CDE征求意见稿下载 - 完整流程")
    print("=" * 60)

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
            ]
        )
        page = await browser.new_page()

        # 设置User-Agent
        await page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        print(f"\n🌐 访问列表页: {LIST_URL}")
        await page.goto(LIST_URL, timeout=60000)
        await asyncio.sleep(8)  # 等待动态内容加载

        # 滚动加载更多内容
        print("📜 滚动加载更多内容...")
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(3)

        # 提取所有新闻条目
        items = await page.query_selector_all('.news_item')
        print(f"📋 发现 {len(items)} 条征求意见稿\n")

        all_downloads = []

        for idx, item in enumerate(items):
            try:
                # 提取日期和标题
                date_el = await item.query_selector('.news_date')
                title_el = await item.query_selector('.news_content_title')

                if not date_el or not title_el:
                    continue

                date_text = await date_el.inner_text()
                title_text = await title_el.inner_text()

                # 格式化日期
                date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', date_text)
                if date_match:
                    pub_date = f"{date_match.group(1)}{date_match.group(2).zfill(2)}{date_match.group(3).zfill(2)}"
                else:
                    pub_date = date_text.replace('.', '').replace(' ', '')

                # 查找详情链接
                detail_link = await item.query_selector('a[href*="listpage/detail"]')
                if not detail_link:
                    # 尝试其他链接格式
                    detail_link = await item.query_selector('a[href*="zdyz"]')

                if detail_link:
                    detail_href = await detail_link.get_attribute('href')
                    if detail_href:
                        if detail_href.startswith('/'):
                            detail_url = f"https://www.cde.org.cn{detail_href}"
                        else:
                            detail_url = detail_href

                        print(f"[{idx+1}/{len(items)}] 📄 {pub_date} - {title_text[:50]}")
                        dls = await download_from_detail_page(page, detail_url, pub_date, title_text)
                        all_downloads.extend(dls)
                    else:
                        print(f"[{idx+1}/{len(items)}] ⏭️ 无详情链接: {title_text[:50]}")
                else:
                    print(f"[{idx+1}/{len(items)}] ⏭️ 跳过: {title_text[:50]}")
            except Exception as e:
                print(f"[{idx+1}/{len(items)}] ❌ 处理失败: {e}")
                continue

        print(f"\n{'='*60}")
        print(f"✅ 下载完成！共下载 {len(all_downloads)} 个新文件")
        print(f"📁 保存目录: {SAVE_DIR}")
        print(f"📊 目录总计: {len(list(SAVE_DIR.iterdir()))} 个文件")
        print(f"{'='*60}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
