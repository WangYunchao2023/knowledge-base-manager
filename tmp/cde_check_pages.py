#!/usr/bin/env python3
"""检查CDE征求意见列表是否有分页"""
import asyncio, re
import sys
sys.path.insert(0, '/home/wangyc/.openclaw/workspace/skills/guidance-web-access/scripts')
from web_access import async_playwright, stealth, get_random_ua, BROWSER_ARGS, log

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=BROWSER_ARGS)
        page = await browser.new_page()
        await page.set_extra_http_headers({'User-Agent': get_random_ua()})
        await stealth.Stealth().apply_stealth_async(page)

        await page.goto("https://www.cde.org.cn/zdyz/listpage/3c49fad55caad7a034c263cfc2b6eb9c", timeout=90000)
        
        for _round in range(90):
            await asyncio.sleep(1)
            try:
                metrics = await page.evaluate(r'''
                    () => ({
                        text_len: (document.body.innerText || '').length,
                        node_count: document.querySelectorAll('.news_item, li').length,
                    })
                ''')
                if metrics['text_len'] >= 500 and metrics['node_count'] >= 5 and _round > 5:
                    break
            except:
                pass

        # 检查分页
        page_info = await page.evaluate(r'''
            () => {
                // 查找分页元素
                const pages = document.querySelectorAll('.layui-laypage, .pagination, .page, [class*="page"]');
                const page_text = Array.from(document.querySelectorAll('*[class*="page"]')).map(el => el.className + ':' + el.innerText.trim().substring(0,50)).slice(0, 10);
                return {
                    total_items: document.querySelectorAll('.news_item, li').length,
                    page_elements: page_text,
                    body_text_sample: (document.body.innerText || '').substring(0, 500)
                };
            }
        ''')
        
        log(f"列表项数量: {page_info['total_items']}")
        log(f"分页元素: {page_info['page_elements']}")
        log(f"页面文字片段: {page_info['body_text_sample']}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
