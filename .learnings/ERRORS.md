
## 2026-04-03 CDE网站访问失败

**问题**: 无法访问CDE官网（https://www.cde.org.cn）检查指导原则更新

**原因**: CDE网站使用高度混淆的JavaScript反爬虫保护，常规HTTP请求无法获取有效内容。即使使用curl、wget或Chrome headless模式也无法解析其动态内容。

**尝试的方法**:
1. 直接curl访问 - 返回混淆的HTML和JavaScript代码
2. 使用不同User-Agent - 无效
3. 尝试特定列表页URL - 同样被反爬保护
4. Chrome headless模式 - 未能执行JS并获取DOM

**影响**: 
- 无法检查指定时间段内（2026-04-02 8:30 至 2026-04-03 8:30）新发布的指导原则
- 无法自动下载PDF文件
- 无法更新指导原则摘录Word文档

**建议**:
1. 使用RPA工具（如UiPath、影刀等）配合真实浏览器访问
2. 手动登录CDE网站检查
3. 考虑使用第三方CDE数据订阅服务
2026-04-13 - PDF解析失败 - 文件实际为HTML（非PDF） - 可能为CDE指导原则文档下载时的错误文件或占位符 - 位置：某个自动文档处理任务
2026-04-13 - PDF解析失败 - 文件实际为HTML（非PDF） - 可能为CDE指导原则文档下载时的错误文件或占位符

## 2026-04-14 (2) PDF解析失败 - faint-co 任务 SIGKILL

**Session**: faint-co (async exec, SIGKILL)

**Errors**:
```
invalid pdf header: b'\x1f\x8b\x08\x00\x00'  → gzip压缩文件被当作PDF处理
invalid pdf header: b'<!DOC'               → HTML被当作PDF处理
incorrect startxref pointer(3)             → PDF结构损坏/不完整
EOF marker not found                       → 文件不完整
```

**原因**: 下载的「PDF」文件实际上是gzip/HTML/损坏的PDF。CDE反爬机制返回非PDF内容，或文件下载不完整。

**解决方案**:
1. 下载后校验magic bytes：`%PDF` (0x25 50 44 46) 才是真正的PDF
2. gzip压缩文件 (`\x1f\x8b`) 需先解压再检测格式
3. 如content-type为text/html，直接标记下载失败并跳过解析
4. 下载失败的文件不应进入PDF解析流程

---

## 2026-04-14 PDF parsing error - HTML response instead of PDF

**Session**: briny-cr (async exec)

**Error**: 
```
parsing for Object Streams invalid pdf header: b'<!DOC' EOF marker not found incorrect startxref pointer(3)
```

**Cause**: When downloading PDFs from CDE website, the server returned HTML (likely an anti-scraping page or error page) instead of the actual PDF file. The `b'<!DOC'` suggests `<!DOCTYPE html>` was returned.

**Context**: This happened during the graphify pipeline for CDE guidance documents. The guidance-web-access skill was likely trying to download PDF files.

**Resolution needed**: 
- PDF download validation (check if response is actually a PDF before treating it as such)
- The CDE website appears to have anti-scraping measures that return HTML instead of files
- When downloading, check Content-Type header or file magic bytes (%PDF signature)
- If HTML is returned, the download should be retried or flagged as failed

## 2026-04-15 graphify SIGTERM

**问题**：graphify 进程收到 SIGTERM 信号被终止  
**触发**：后台 graphify 任务  
**可能原因**：内存不足 / 超时 / 被手动 kill  
**后续**：下次跑 graphify 前确认内存和超时配置

## 2026-04-15 19:20 - graphifyy 模块不存在

**错误**: `ModuleNotFoundError: No module named 'graphifyy'` (swift-ke, signal SIGKILL)

**原因**: 调用 graphify 技能时拼写错误，多了一个 'y'。正确模块名为 `graphify`。

**正确导入**: `from graphify import ...` 或 `graphify` skill 路径为 `~/.openclaw/skills/graphify/SKILL.md`

**改进**: 调用 skill 前确认名称拼写正确。
