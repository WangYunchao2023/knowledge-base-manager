#!/usr/bin/env python3
"""详细检查CDE页面"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        page = await browser.new_page()
        await page.set_extra_http_headers({'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'})

        resp = await page.goto("https://www.cde.org.cn/zdyz/listpage/3c49fad55caad7a034c263cfc2b6eb9c", timeout=60000)
        print(f"状态码: {resp.status}")

        # 等待更长时间
        await asyncio.sleep(15)

        content = await page.content()
        print(f"HTML长度: {len(content)}")
        print(f"HTML前500字符: {content[:500]}")

        # 检查是否有frame
        frames = page.frames
        print(f"\nFrames数量: {len(frames)}")
        for i, frame in enumerate(frames):
            print(f"  Frame {i}: {frame.url[:80]}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
