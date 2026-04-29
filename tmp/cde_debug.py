#!/usr/bin/env python3
"""检查CDE页面结构"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        page = await browser.new_page()
        await page.set_extra_http_headers({'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'})

        await page.goto("https://www.cde.org.cn/zdyz/listpage/3c49fad55caad7a034c263cfc2b6eb9c", timeout=60000)
        await asyncio.sleep(10)

        # 获取页面HTML片段
        content = await page.content()
        print(f"HTML长度: {len(content)}")

        # 尝试多种选择器
        selectors = ['.news_item', '.news_content', '.news_list', 'div[class*="news"]', 'ul li', '.list_item']
        for sel in selectors:
            els = await page.query_selector_all(sel)
            print(f"  {sel}: {len(els)} 个")

        # 尝试获取包含"征求意见稿"文字的元素
        all_text = await page.inner_text('body')
        if '征求意见稿' in all_text:
            print("\n✅ 页面包含'征求意见稿'文字")
            # 找到该文字位置
            lines = all_text.split('\n')
            for i, line in enumerate(lines):
                if '征求意见稿' in line:
                    print(f"  行{i}: {line.strip()[:80]}")
        else:
            print("\n❌ 页面不包含'征求意见稿'文字")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
