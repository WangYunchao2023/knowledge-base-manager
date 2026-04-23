"""
FDA - 获取所有筛选器选项（Select2组件）
"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

REPORT = Path.home() / "Documents" / "工作" / "法规指导原则" / "FDA筛选器完整感知.json"
REPORT_MD = Path.home() / "Documents" / "工作" / "法规指导原则" / "FDA筛选器完整感知.md"

async def main():
    print("🔍 FDA Guidance - 获取筛选器选项")
    print("=" * 60)
    
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
        
        filters = {}
        
        # 使用正确的Select2选择器
        filter_map = {
            'Product': '#lcds-datatable-filter--product',
            'FDA Organization': '#lcds-datatable-filter--org',
            'Topic': '#lcds-datatable-filter--topic',
            'Issue Date': '#lcds-datatable-filter--date',
            'Draft or Final': '#lcds-datatable-filter--draft',
            'Open for Comment': '#lcds-datatable-filter--comment',
            'Document Type': '#lcds-datatable-filter--type',
            'Comment Closing': '#lcds-datatable-filter--closing'
        }
        
        for name, selector in filter_map.items():
            el = await page.query_selector(selector)
            if el:
                opts = await el.query_selector_all('option')
                options = []
                for opt in opts:
                    text = (await opt.inner_text()).strip()
                    val = await opt.get_attribute('value')
                    if text:  # 排除空选项
                        options.append({"text": text, "value": val})
                filters[name] = options
                print(f"\n📋 {name} ({len(options)}项):")
                for o in options[:20]:
                    print(f"   • {o['text']}")
                if len(options) > 20:
                    print(f"   ... 还有 {len(options)-20} 项")
        
        REPORT.write_text(json.dumps(filters, ensure_ascii=False, indent=2))
        
        # 生成Markdown
        md = "# FDA Guidance - 筛选器完整感知报告\n\n"
        for name, options in filters.items():
            md += f"\n## {name} ({len(options)}项)\n"
            for o in options:
                md += f"- {o['text']}\n"
        
        REPORT_MD.write_text(md)
        
        print(f"\n✅ 已保存: {REPORT}")
        
        await browser.close()

asyncio.run(main())
