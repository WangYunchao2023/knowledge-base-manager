#!/usr/bin/env python3
"""
CDE征求意见稿 - 搜索+翻页+下载 v2
使用JavaScript直接提取搜索结果
"""
import asyncio, os, sys, re
from pathlib import Path

SAVE_DIR = Path("/home/wangyc/Documents/法规指导原则-征求意见1")
SAVE_DIR.mkdir(parents=True, exist_ok=True)
existing = {f.name for f in SAVE_DIR.iterdir() if f.is_file()}
print(f"📁 已存在文件: {len(existing)} 个")

sys.path.insert(0, '/home/wangyc/.openclaw/workspace/skills/guidance-web-access/scripts')
from web_access import async_playwright, stealth, get_random_ua, BROWSER_ARGS, log

def sanitize(name):
    return re.sub(r'[\\/:*?"<>|]', '', name)

async def main():
    log("=" * 60)
    log("🚀 CDE征求意见稿 - 搜索+翻页+下载 v2")
    log("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=BROWSER_ARGS)
        page = await browser.new_page()
        await page.set_extra_http_headers({'User-Agent': get_random_ua()})
        await stealth.Stealth().apply_stealth_async(page)

        log("\n🌐 访问搜索页...")
        await page.goto("https://www.cde.org.cn/zdyz/fullsearchpage", timeout=90000)
        await asyncio.sleep(5)

        # 检查iframe
        frames = page.frames
        log(f" Frames数量: {len(frames)}")
        for i, f in enumerate(frames):
            log(f"   Frame {i}: {f.url[:80]}")

        # 注入搜索关键词
        log("\n🔍 搜索: 征求意见")
        await page.evaluate("""
            () => {
                // 填入搜索关键词
                const inputs = document.querySelectorAll('input');
                for (const inp of inputs) {
                    if (inp.name === 'searchTitle' || (inp.placeholder && inp.placeholder.includes('标题'))) {
                        inp.value = '征求意见';
                        inp.dispatchEvent(new Event('input'));
                        inp.dispatchEvent(new Event('change'));
                        break;
                    }
                }
            }
        """)
        await asyncio.sleep(1)

        # 点击搜索
        await page.evaluate("""
            () => {
                const btns = document.querySelectorAll('button, a, input[type='button']');
                for (const btn of btns) {
                    const t = (btn.innerText || '').trim();
                    if (t === '检索' || t === '搜索' || t === '查询') {
                        btn.click();
                        break;
                    }
                }
            }
        """)
        await asyncio.sleep(8)

        # 直接用JS提取结果
        log("\n📋 提取搜索结果...")
        for attempt in range(3):
            await asyncio.sleep(3)
            result = await page.evaluate(r'''
                () => {
                    // 查找所有新闻条目
                    const items = document.querySelectorAll('.news_item');
                    if (items.length > 0) {
                        return { format: 'news_item', count: items.length };
                    }

                    // 尝试其他格式
                    const allLinks = document.querySelectorAll('a[href*="detail"]');
                    if (allLinks.length > 0) {
                        return { format: 'detail_links', count: allLinks.length };
                    }

                    // 返回页面文字样本
                    return {
                        format: 'text',
                        text: (document.body.innerText || '').substring(0, 1000),
                        link_count: document.querySelectorAll('a[href]').length
                    };
                }
            ''')
            log(f"   提取结果: {result}")
            if result.get('count', 0) > 0:
                break

        await browser.close()
        log(f"\n搜索页结构不同于列表页，需要换策略")
        log(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())
