"""
FDA - 调试筛选器选择器
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        page.set_default_timeout(30000)
        
        await page.goto(
            "https://www.fda.gov/regulatory-information/search-fda-guidance-documents",
            wait_until="domcontentloaded"
        )
        await page.wait_for_selector('#DataTables_Table_0', timeout=20000)
        await page.wait_for_timeout(3000)
        
        # 查找所有select元素
        print("📍 所有select元素:")
        selects = await page.query_selector_all('select')
        for sel in selects:
            sid = await sel.get_attribute('id')
            sclass = await sel.get_attribute('class')
            sname = await sel.get_attribute('name')
            opts_count = len(await sel.query_selector_all('option'))
            print(f"   id={sid}, class={sclass}, name={sname}, options={opts_count}")
        
        # 打印页面中包含"product"的元素
        print("\n📍 包含'product'的元素:")
        product_els = await page.query_selector_all('[id*="product" i], [class*="product" i]')
        for el in product_els[:10]:
            tag = await el.evaluate('el => el.tagName')
            sid = await el.get_attribute('id')
            sclass = await el.get_attribute('class')
            print(f"   <{tag}> id={sid}, class={sclass}")
        
        await browser.close()

asyncio.run(main())
