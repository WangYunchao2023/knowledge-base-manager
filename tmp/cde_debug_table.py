#!/usr/bin/env python3
import asyncio, sys
sys.path.insert(0, '/home/wangyc/.openclaw/workspace/skills/guidance-web-access/scripts')
from web_access import async_playwright, stealth, get_random_ua, BROWSER_ARGS, log

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=BROWSER_ARGS)
        page = await browser.new_page()
        await page.set_extra_http_headers({'User-Agent': get_random_ua()})
        await stealth.Stealth().apply_stealth_async(page)

        await page.goto('https://www.cde.org.cn/zdyz/fullsearchpage', timeout=90000)
        await asyncio.sleep(5)
        
        # 搜索
        await page.evaluate('''() => {
            const inputs = document.querySelectorAll("input");
            for (const inp of inputs) {
                if (inp.name === "searchTitle" || (inp.placeholder && inp.placeholder.includes("标题"))) {
                    inp.value = "征求意见";
                    inp.dispatchEvent(new Event("input"));
                    inp.dispatchEvent(new Event("change"));
                    break;
                }
            }
        }''')
        await asyncio.sleep(1)
        await page.evaluate('''() => {
            const btns = document.querySelectorAll("button, a");
            for (const btn of btns) {
                if ((btn.innerText||'').trim() === "检索") { btn.click(); break; }
            }
        }''')
        await asyncio.sleep(8)

        # 分析表格
        result = await page.evaluate('''() => {
            const tables = document.querySelectorAll("table");
            let out = "Tables: " + tables.length + "\\n";
            for (let i = 0; i < tables.length; i++) {
                const t = tables[i];
                out += "Table " + i + " class=" + t.className + " rows=" + t.querySelectorAll("tr").length + "\\n";
                const trs = t.querySelectorAll("tr");
                for (let j = 0; j < Math.min(3, trs.length); j++) {
                    const cells = trs[j].querySelectorAll("td, th");
                    const cellTexts = [];
                    for (let c = 0; c < Math.min(cells.length, 5); c++) {
                        cellTexts.push(cells[c].innerText.trim().substring(0, 25));
                    }
                    out += "  row[" + j + "]: " + cellTexts.join(" | ") + "\\n";
                }
            }
            
            // 直接找tr
            const allTrs = document.querySelectorAll("tr");
            out += "\\nTotal TRs: " + allTrs.length + "\\n";
            
            // 找所有链接及其父级tr/td
            const allLinks = document.querySelectorAll("a[href*='zdyz']");
            out += "Detail links: " + allLinks.length + "\\n";
            for (let i = 0; i < Math.min(5, allLinks.length); i++) {
                const a = allLinks[i];
                out += "  link[" + i + "]: " + a.href + " => " + a.innerText.trim().substring(0, 50) + "\\n";
            }
            
            return out;
        }''')
        print(result)
        await browser.close()

asyncio.run(main())
