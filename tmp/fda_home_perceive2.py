"""
FDA Search Guidance - 感知Product/Organization/Topic筛选器
"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

REPORT = Path.home() / "Documents" / "工作" / "法规指导原则" / "FDA筛选器感知报告.json"
REPORT_MD = Path.home() / "Documents" / "工作" / "法规指导原则" / "FDA筛选器感知报告.md"

async def main():
    print("🔍 FDA Guidance - 感知筛选器")
    print("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        page.set_default_timeout(30000)
        
        print("\n📍 访问Search Guidance Documents页面...")
        await page.goto(
            "https://www.fda.gov/regulatory-information/search-fda-guidance-documents",
            wait_until="domcontentloaded"
        )
        await page.wait_for_selector('#DataTables_Table_0', timeout=20000)
        await page.wait_for_timeout(3000)
        
        # 获取所有筛选器选项
        filters = {}
        
        # Product
        product_el = await page.query_selector('#product_category')
        if product_el:
            opts = await product_el.query_selector_all('option')
            filters['Product'] = [(await o.inner_text()).strip() for o in opts if (await o.inner_text()).strip() and (await o.inner_text()).strip() != 'All']
        
        # FDA Organization
        org_el = await page.query_selector('#fdorg_options')
        if org_el:
            opts = await org_el.query_selector_all('option')
            filters['FDA Organization'] = [(await o.inner_text()).strip() for o in opts if (await o.inner_text()).strip() and (await o.inner_text()).strip() != 'All']
        
        # Topic
        topic_el = await page.query_selector('#topic_options')
        if topic_el:
            opts = await topic_el.query_selector_all('option')
            filters['Topic'] = [(await o.inner_text()).strip() for o in opts if (await o.inner_text()).strip() and (await o.inner_text()).strip() != 'All']
        
        # Document Type
        doc_el = await page.query_selector('#doc_type')
        if doc_el:
            opts = await doc_el.query_selector_all('option')
            filters['Document Type'] = [(await o.inner_text()).strip() for o in opts if (await o.inner_text()).strip() and (await o.inner_text()).strip() != 'All']
        
        # Draft or Final
        status_el = await page.query_selector('#daf_status')
        if status_el:
            opts = await status_el.query_selector_all('option')
            filters['Draft or Final'] = [(await o.inner_text()).strip() for o in opts if (await o.inner_text()).strip() and (await o.inner_text()).strip() != 'All']
        
        # 保存报告
        REPORT.write_text(json.dumps(filters, ensure_ascii=False, indent=2))
        
        md = """# FDA Guidance - 筛选器选项感知报告

## Product (产品分类)
"""
        for p in filters.get('Product', []):
            md += f"- {p}\n"
        
        md += "\n## FDA Organization (FDA组织)\n"
        for o in filters.get('FDA Organization', []):
            md += f"- {o}\n"
        
        md += "\n## Topic (主题分类)\n"
        for t in filters.get('Topic', []):
            md += f"- {t}\n"
        
        md += "\n## Document Type (文档类型)\n"
        for d in filters.get('Document Type', []):
            md += f"- {d}\n"
        
        md += "\n## Draft or Final (状态)\n"
        for s in filters.get('Draft or Final', []):
            md += f"- {s}\n"
        
        REPORT_MD.write_text(md)
        
        print("\n✅ 感知完成!")
        print(f"📊 Product: {len(filters.get('Product', []))}项")
        print(f"📊 FDA Organization: {len(filters.get('FDA Organization', []))}项")
        print(f"📊 Topic: {len(filters.get('Topic', []))}项")
        print(f"📄 {REPORT}")
        
        # 打印Product列表
        print("\n📋 Product分类:")
        for p in filters.get('Product', []):
            print(f"   • {p}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
