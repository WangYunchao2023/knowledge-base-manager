"""
FDA首页 - 感知分类导航结构
Purpose: 访问首页，感知所有Guidance分类链接
"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

REPORT = Path.home() / "Documents" / "工作" / "法规指导原则" / "FDA首页感知报告.json"
REPORT_MD = Path.home() / "Documents" / "工作" / "法规指导原则" / "FDA首页感知报告.md"

async def main():
    print("🔍 FDA首页 - 感知分类导航")
    print("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await ctx.new_page()
        page.set_default_timeout(30000)
        
        # 1. 访问FDA首页
        print("\n📍 访问FDA首页...")
        await page.goto("https://www.fda.gov", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        
        # 2. 感知Regulatory Information下拉菜单
        print("\n📍 查找Regulatory Information链接...")
        reg_link = await page.query_selector('a[href*="regulatory-information"]')
        if reg_link:
            reg_href = await reg_link.get_attribute('href')
            print(f"   找到: {reg_href}")
        
        # 3. 点击Regulatory Information展开子菜单
        print("\n📍 展开Regulatory Information子菜单...")
        await page.hover('a[href*="regulatory-information"]')
        await page.wait_for_timeout(1000)
        
        # 4. 查找所有Guidance相关链接
        print("\n📍 查找Guidance分类链接...")
        guidance_links = []
        
        # 方法1: 查找子菜单中的链接
        menu_links = await page.query_selector_all('.dropdown-menu a, .nav-dropdown a, [role="menu"] a')
        for link in menu_links:
            href = await link.get_attribute('href')
            text = (await link.inner_text()).strip()
            if href and ('guidance' in href.lower() or 'guidance' in text.lower()):
                guidance_links.append({"text": text, "href": href})
        
        # 方法2: 直接访问Regulatory Information页面找Guidance分类
        print("\n📍 访问Regulatory Information页面...")
        if reg_href:
            reg_url = f"https://www.fda.gov{reg_href}" if not reg_href.startswith('http') else reg_href
            await page.goto(reg_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
        
        # 查找页面上的Guidance相关链接
        all_links = await page.query_selector_all('a[href]')
        guidance_categories = []
        for link in all_links:
            href = await link.get_attribute('href')
            text = (await link.inner_text()).strip()
            if href and 'guidance' in href.lower():
                full_url = f"https://www.fda.gov{href}" if href.startswith('/') else href
                if full_url not in [c['url'] for c in guidance_categories]:
                    guidance_categories.append({
                        "text": text[:100],
                        "url": full_url
                    })
        
        # 5. 访问Search Guidance Documents页面，获取Product分类
        print("\n📍 访问Search Guidance Documents页面...")
        await page.goto(
            "https://www.fda.gov/regulatory-information/search-fda-guidance-documents",
            wait_until="domcontentloaded"
        )
        await page.wait_for_selector('#DataTables_Table_0', timeout=20000)
        await page.wait_for_timeout(3000)
        
        # 获取Product筛选器的所有选项
        product_filter = await page.query_selector('#product_category')
        product_options = []
        if product_filter:
            options = await product_filter.query_selector_all('option')
            for opt in options:
                text = (await opt.inner_text()).strip()
                val = await opt.get_attribute('value')
                if text and text != "All":
                    product_options.append({"text": text, "value": val})
        
        # 获取FDA Organization筛选器选项
        org_filter = await page.query_selector('#fdorg_options')
        org_options = []
        if org_filter:
            options = await org_filter.query_selector_all('option')
            for opt in options:
                text = (await opt.inner_text()).strip()
                val = await opt.get_attribute('value')
                if text and text != "All":
                    org_options.append({"text": text[:80], "value": val})
        
        # 获取Topic筛选器选项
        topic_filter = await page.query_selector('#topic_options')
        topic_options = []
        if topic_filter:
            options = await topic_filter.query_selector_all('option')
            for opt in options:
                text = (await opt.inner_text()).strip()
                val = await opt.get_attribute('value')
                if text and text != "All":
                    topic_options.append({"text": text[:80], "value": val})
        
        report = {
            "感知时间": "2026-04-03T00:45:00+08:00",
            "guidance分类链接": guidance_categories[:30],
            "Product筛选器": product_options,
            "FDA_Organization筛选器": org_options[:30],
            "Topic筛选器": topic_options[:50]
        }
        
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        
        # 生成Markdown
        md = f"""# FDA首页 + Guidance分类 - 感知报告

## 感知时间
2026-04-03 08:45 (GMT+8)

## FDA Guidance分类链接
"""
        for c in guidance_categories[:30]:
            md += f"- [{c['text']}]({c['url']})\n"
        
        md += f"""
## Search Guidance Documents - 筛选器选项

### Product ({len(product_options)}项)
"""
        for p in product_options:
            md += f"- {p['text']} (value={p['value']})\n"
        
        md += f"""
### FDA Organization ({len(org_options)}项)
"""
        for o in org_options[:30]:
            md += f"- {o['text']}\n"
        
        md += f"""
### Topic ({len(topic_options)}项)
"""
        for t in topic_options[:50]:
            md += f"- {t['text']}\n"
        
        REPORT_MD.write_text(md)
        
        print("\n" + "=" * 60)
        print("✅ 感知完成!")
        print(f"📄 JSON: {REPORT}")
        print(f"📄 Markdown: {REPORT_MD}")
        print(f"\n📊 Product筛选器: {len(product_options)}项")
        print(f"📊 FDA Organization: {len(org_options)}项")
        print(f"📊 Topic筛选器: {len(topic_options)}项")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
