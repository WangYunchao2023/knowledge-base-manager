const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ 
    headless: false,
    args: [
      '--no-sandbox',
      '--disable-dev-shm-usage',
      '--user-data-dir=' + process.env.HOME + '/.config/google-chrome',
      '--profile-directory=Default'
    ]
  });
  
  const context = await browser.newContext({
    acceptDownloads: true
  });
  
  const page = await context.newPage();
  
  try {
    console.log('使用用户Chrome profile...');
    await page.goto('https://www.kdocs.cn/l/chwmDt90OaFU', { 
      waitUntil: 'networkidle',
      timeout: 30000 
    });
    
    await page.waitForTimeout(5000);
    
    const title = await page.title();
    console.log('页面标题:', title);
    
    // 点击"文件"菜单
    console.log('点击文件菜单...');
    const fileMenu = await page.$('text=文件');
    if (fileMenu) {
      await fileMenu.click();
      await page.waitForTimeout(2000);
      console.log('文件菜单已点击');
    }
    
    // 查找下载/导出选项
    const downloadOption = await page.$('text=下载, text=导出, text=另存为');
    if (downloadOption) {
      console.log('找到导出选项:', await downloadOption.textContent());
      await downloadOption.click();
      await page.waitForTimeout(3000);
    }
    
    // 尝试快捷键 Ctrl+S
    console.log('尝试 Ctrl+S...');
    await page.keyboard.press('Control+s');
    await page.waitForTimeout(3000);
    
    // 检查是否有下载对话框
    const dialogs = await page.$$('dialog');
    if (dialogs.length > 0) {
      console.log('发现对话框');
    }
    
    // 尝试截图确认
    await page.screenshot({ path: '/tmp/kdocs_after.png' });
    console.log('截图已保存到 /tmp/kdocs_after.png');
    
    // 尝试点击WPS特有的下载按钮
    const downloadBtn = await page.$('[aria-label*="下载"], [title*="下载"], [aria-label*="导出"], [title*="导出"]');
    if (downloadBtn) {
      console.log('找到下载按钮!');
      const label = await downloadBtn.getAttribute('aria-label') || await downloadBtn.getAttribute('title');
      console.log('按钮标签:', label);
      await downloadBtn.click();
      await page.waitForTimeout(5000);
    }
    
    // 检查网络请求获取下载URL
    let capturedUrl = null;
    page.on('request', request => {
      const url = request.url();
      if (url.includes('export') || url.includes('download') || url.includes('.et') || url.includes('.xlsx')) {
        console.log('下载请求:', url);
        capturedUrl = url;
      }
    });
    
    // 等待一段时间
    await page.waitForTimeout(5000);
    
    if (capturedUrl) {
      console.log('\n捕获到下载URL:', capturedUrl);
    }
    
    // 最终截图
    await page.screenshot({ path: '/tmp/kdocs_final.png' });
    console.log('最终截图已保存');
    
    console.log('\n请手动操作浏览器完成下载，或告诉我页面上的选项');
    
  } catch (err) {
    console.error('错误:', err.message);
  } finally {
    await browser.close();
  }
}

main();
