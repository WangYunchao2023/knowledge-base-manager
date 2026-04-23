# LEARNINGS.md

## 2026-04-15

### PDF下载验证重要性
**问题**: 异步PDF处理命令返回 "invalid pdf header: b'<!DOC'" 错误

**原因**: 下载的文件是HTML错误页面（反爬虫机制），而非真实PDF

**教训**: 
- 下载PDF后必须验证文件头为 `%PDF`
- 发现无效文件应删除并重试（最多3次）
- 这与3月份CDE下载遇到的问题一致：网站对爬虫返回HTML

**预防**:
- 已在 guidance-web-access skill 中有自动验证机制
- 发现 `<!DOC` 头应立即删除文件并重新下载
## 2026-04-19
- PDF detection/processing: some files returned HTML (b'<!DOC') instead of valid PDF. Check if source URLs are broken or if there's a redirect issue.
- Graphify large corpus processing completed: 7186 files / 28M words, needs_graph=true
