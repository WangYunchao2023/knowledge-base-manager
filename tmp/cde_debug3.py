#!/usr/bin/env python3
"""深入调试CDE页面加载"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        page = await browser.new_page()

        # 拦截API请求
        api_calls = []
        async def handle_response(resp):
            if 'api' in resp.url or 'json' in resp.url or 'listpage' in resp.url:
                api_calls.append({'url': resp.url, 'status': resp.status})

        page.on("response", handle_response)

        await page.goto("https://www.cde.org.cn/zdyz/listpage/3c49fad55caad7a034c263cfc2b6eb9c", timeout=60000)

        # 等待网络空闲
        try:
            await page.wait_for_load_state("networkidle", timeout=30000)
        except:
            print("网络未空闲，继续...")

        await asyncio.sleep(5)

        print(f"API调用数量: {len(api_calls)}")
        for call in api_calls[:10]:
            print(f"  [{call['status']}] {call['url'][:100]}")

        # 再次检查页面内容
        body_text = await page.evaluate("document.body.innerText")
        print(f"\n页面文字长度: {len(body_text)}")
        if body_text.strip():
            print(f"前200字符: {body_text[:200]}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
