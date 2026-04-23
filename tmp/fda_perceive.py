"""
FDA Guidance Page - 感知阶段
 Purpose: 访问页面，感知结构，不下载任何内容
"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

SAVE_DIR = Path.home() / "Documents" / "工作" / "法规指导原则"
REPORT = SAVE_DIR / "FDA感知报告.json"
REPORT_MD = SAVE_DIR / "FDA感知报告.md"

async def main():
    print("🔍 FDA指导原则页面感知阶段")
    print("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await ctx.new_page()
        page.set_default_timeout(30000)
        
        print("\n📍 访问页面...")
        await page.goto(
            "https://www.fda.gov/regulatory-information/search-fda-guidance-documents",
            wait_until="domcontentloaded"
        )
        
        print("📍 等待DataTables表格加载...")
        await page.wait_for_selector('#DataTables_Table_0', timeout=20000)
        await page.wait_for_timeout(3000)  # 等待JS渲染
        
        # 1. 感知表格结构
        print("\n📍 感知表格结构...")
        headers = await page.query_selector_all('#DataTables_Table_0 thead th')
        header_names = []
        for h in headers:
            text = (await h.inner_text()).strip()
            header_names.append(text)
        
        # 2. 感知总记录数
        body_text = await page.inner_text('body')
        import re
        count_match = re.search(r'Showing\s+\d+\s+to\s+\d+\s+of\s+([\d,]+)', body_text)
        total_count = count_match.group(1).replace(',', '') if count_match else "未知"
        
        # 3. 感知前10行数据
        print("\n📍 感知样本数据（前10行）...")
        rows = await page.query_selector_all('#DataTables_Table_0 tbody tr')
        sample_rows = []
        for row in rows[:10]:
            cells = await row.query_selector_all('td')
            if len(cells) >= 5:
                row_data = {
                    "序号": (await cells[0].inner_text()).strip(),
                    "标题链接": await cells[0].query_selector('a[href]'),
                    "PDF链接": await cells[1].query_selector('a[href]'),
                    "日期": (await cells[2].inner_text()).strip(),
                    "类型": (await cells[3].inner_text()).strip(),
                    "分类": (await cells[4].inner_text()).strip(),
                }
                # 获取链接
                if row_data["标题链接"]:
                    href = await row_data["标题链接"].get_attribute('href')
                    row_data["标题URL"] = f"https://www.fda.gov{href}" if href else ""
                if row_data["PDF链接"]:
                    pdf_href = await row_data["PDF链接"].get_attribute('href')
                    row_data["PDF_URL"] = f"https://www.fda.gov{pdf_href}" if pdf_href else ""
                row_data.pop("标题链接")
                row_data.pop("PDF链接")
                sample_rows.append(row_data)
        
        # 4. 感知筛选器选项
        print("\n📍 感知筛选器...")
        filters = {}
        
        # Product filter
        product_options = await page.query_selector_all('#product_category option')
        filters["Product"] = [o.inner_text().strip() for o in product_options[:20]]
        
        # FDA Organization
        org_options = await page.query_selector_all('#fdorg_options option')
        filters["FDA Organization"] = [o.inner_text().strip() for o in org_options[:20]]
        
        # Document Type
        doc_options = await page.query_selector_all('#doc_type option')
        filters["Document Type"] = [o.inner_text().strip() for o in doc_options[:20]]
        
        # Draft or Final
        status_options = await page.query_selector_all('#daf_status option')
        filters["Draft or Final"] = [o.inner_text().strip() for o in status_options]
        
        # 5. 感知搜索功能
        print("\n📍 感知搜索功能...")
        search_input = await page.query_selector('#DataTables_Table_0_filter input')
        search_placeholder = await search_input.get_attribute('placeholder') if search_input else "未知"
        
        # 6. 感知分页
        pagination = await page.query_selector_all('#DataTables_Table_0_paginate span a')
        page_info = {
            "是否有分页": len(pagination) > 0,
            "分页按钮数": len(pagination)
        }
        
        report = {
            "感知时间": "2026-04-03T00:38:00+08:00",
            "页面URL": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents",
            "表格结构": {
                "列数": len(header_names),
                "列名": header_names,
                "总记录数": total_count
            },
            "样本数据": sample_rows,
            "筛选器": filters,
            "搜索功能": {
                "输入框placeholder": search_placeholder,
                "支持关键词搜索": True
            },
            "分页": page_info,
            "技术说明": {
                "渲染方式": "JavaScript动态加载（DataTables）",
                "需要Playwright": True,
                "下载方式": "page.request.get()"
            }
        }
        
        # 保存JSON报告
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        
        # 生成Markdown报告
        md = f"""# FDA指导原则页面 - 感知报告

## 基本信息
- **感知时间**: 2026-04-03 08:38 (GMT+8)
- **页面URL**: https://www.fda.gov/regulatory-information/search-fda-guidance-documents
- **渲染方式**: JavaScript动态加载（DataTables）

## 表格结构
- **总记录数**: {total_count}
- **列数**: {len(header_names)}
- **列名**: {', '.join(header_names)}

## 样本数据（前10行）

| 序号 | 日期 | 类型 | 分类 |
|------|------|------|------|
"""
        for r in sample_rows:
            md += f"| {r.get('序号','')} | {r.get('日期','')} | {r.get('类型','')} | {r.get('分类','')[:30]} |\n"
            md += f"|   | **标题**: {r.get('标题URL','')[:80]} |\n"
            md += f"|   | **PDF**: {r.get('PDF_URL','')[:80]} |\n"
        
        md += f"""
## 筛选器选项

### Product（前20项）
{', '.join(filters.get('Product', [])[:20])} ...

### FDA Organization（前20项）
{', '.join(filters.get('FDA Organization', [])[:20])} ...

### Document Type
{', '.join(filters.get('Document Type', [])[:10])}

### Draft or Final
{', '.join(filters.get('Draft or Final', []))}

## 搜索功能
- **输入框**: {search_placeholder}
- **支持关键词搜索**: ✅

## 分页
- **是否有分页**: {'是' if page_info['是否有分页'] else '否'}
- **分页按钮数**: {page_info['分页按钮数']}

## 技术说明
1. 页面使用 **DataTables** jQuery插件
2. 数据通过JavaScript动态加载
3. 需要使用 **Playwright** 才能正确渲染和抓取
4. PDF下载推荐使用 `page.request.get()` 绕过浏览器直接请求

## 关键发现
1. 表格列包含：标题、PDF、日期、类型、分类等
2. 支持多维度筛选：Product、FDA Organization、Topic、Date、Draft/Final等
3. 支持关键词搜索
4. 数据量较大（{total_count}条记录），需要考虑分页或搜索策略
"""
        
        REPORT_MD.write_text(md)
        
        print("\n" + "=" * 60)
        print("✅ 感知完成!")
        print(f"📄 JSON报告: {REPORT}")
        print(f"📄 Markdown报告: {REPORT_MD}")
        print(f"\n📊 总记录数: {total_count}")
        print(f"📊 表格列数: {len(header_names)}")
        print(f"   列名: {header_names}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
