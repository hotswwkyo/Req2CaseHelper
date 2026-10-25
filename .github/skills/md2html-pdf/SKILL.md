---
name: md2html-pdf
description: '将 Markdown 文件转换为美观的 HTML 页面或 PDF 文档，用于测试用例、测试点清单、需求文档、报告等的阅读/评审/分享/汇报/打印。Use when: 需要把 .md 转成 HTML/PDF / 生成美观的 HTML 页面 / 导出 PDF 文档 / 将测试用例或测试点清单导出为网页或 PDF / 文档排版后输出 / 生成可分享、可打印的文档版本。生成测试用例等 MD 文档后，若用户需要可阅读/评审/汇报版本，主动询问是否转换。'
user-invocable: true
---

# MD 转 HTML / PDF 技能

## 目标（这个技能做什么）
将本仓库或用户指定的 Markdown 文件转换为**美观的 HTML 页面**或 **PDF 文档**，便于阅读、评审、分享、汇报与打印输出。典型输入包括：

- 测试用例：`testcases/*.md`
- 测试点清单：`testpoints/*.md`
- 需求 / 背景 / 报告：`docs/*.md` 等

> 实现：HTML 基于 `markdown` 库渲染（内置 GitHub 风格 CSS）；PDF 基于 `markdown-pdf`（底层 PyMuPDF）直接渲染。两者均纯 Python、无系统依赖。
>
> HTML 还内置 **mermaid 流程图渲染**：Markdown 中的 ```mermaid 代码块会被渲染成真正的流程图，且 mermaid.js 直接内联进 HTML，生成物完全自包含、离线可看。

## 何时使用（触发条件）
- 用户要求把 .md 转成 HTML / 生成网页 / 导出 PDF，用于评审、分享、打印等。
- 生成测试用例等 MD 文档后，用户需要"可阅读 / 评审 / 汇报"版本时，主动询问是否转换。与 md2excel 互补：Excel 供禅道导入（机器消费），HTML/PDF 供人读与评审。

## 执行步骤
1. **确认输入与格式**
   - 明确输入 `.md` 文件路径（文件须存在）。
   - 明确输出格式：`html`（美观页面）或 `pdf`（文档），以及输出文件名 / 路径。
2. **运行脚本**（在项目根目录执行）
   ```bash
   python .github/skills/md2html-pdf/scripts/md_convert.py <输入.md> [-o <输出>] [--format html|pdf]
   ```
3. **报告结果**：告知用户生成的文件路径；失败时说明原因。

### 命令示例
```bash
# 默认转 HTML，输出到与输入同目录同名的 .html
python .github/skills/md2html-pdf/scripts/md_convert.py testcases/test_cases_xxx.md

# 转 PDF，指定输出路径
python .github/skills/md2html-pdf/scripts/md_convert.py docs/报告.md -o docs/报告.pdf

# 显式指定格式（即使输出后缀与格式不一致也能强制转换）
python .github/skills/md2html-pdf/scripts/md_convert.py 文档.md --format pdf -o 文档.pdf

# 不渲染流程图（mermaid 代码块按纯文本显示）
python .github/skills/md2html-pdf/scripts/md_convert.py 文档.md --no-mermaid

# 查看完整帮助
python .github/skills/md2html-pdf/scripts/md_convert.py -h
```

## 脚本使用说明

### 参数
| 参数 | 说明 |
|------|------|
| `input` | 输入的 `.md` 文件路径（必填，需存在） |
| `-o` / `--output` | 输出路径（可选；按后缀 `.html`/`.pdf` 自动判断格式；后缀无法识别时警告并追加 `.html`） |
| `--format` | `html` 或 `pdf`（可选；缺省时按输出后缀判断，仍无法判断则默认 `html`） |
| `--no-mermaid` | 不渲染 mermaid 流程图（代码块按纯文本显示）；仅影响 HTML |

### 输出路径推导规则
- 未指定 `-o`：与输入同目录同名——`--format pdf` 得 `.pdf`，否则得 `.html`。
- 指定 `-o` 且未指定 `--format`：按输出后缀判断（`.pdf`→pdf；`.html`/`.htm`→html；其他→警告并追加 `.html`）。
- 指定 `-o` 且指定 `--format`：以 `--format` 为准。

### 依赖安装
```bash
pip install markdown markdown-pdf   # markdown-pdf 会连带安装 PyMuPDF；pygments 可选（HTML 代码高亮）
```

### mermaid 流程图
- 技能目录下的 `assets/mermaid.min.js`（约 3.3MB）是**内置资源**，不要删。转换时会被内联进 HTML，因此生成物离线 / 内网 / 转发给他人都能正常显示流程图。
  - 资源缺失时会自动回退到 CDN（`cdn.jsdelivr.net`）并打印警告——此时打开页面需联网。
  - 因为内联了这个库，含流程图的 HTML 体积约为 3.3MB，属预期行为。
- 渲染在**浏览器端**完成：转换脚本只负责把 ```mermaid 块转成 `<div class="mermaid">`，真正的绘图由页面里的 mermaid.js 执行。
- 语法错误不会被静默忽略——出错时图位置会显示红底错误提示（`Mermaid 渲染失败：...`），便于定位。
- 仅支持 ``` ```mermaid ``` 与 `~~~mermaid` 两种围栏；**闭合围栏长度须与开头一致**，否则会打印“未能识别”警告并按纯文本显示。

### 已知特性与注意事项
- 输入编码须为 UTF-8（脚本自动剥离 BOM）。
- HTML 渲染自动修复"引用块内列表缺空行"问题；开启扩展：`extra`、`toc`、`codehilite`、`nl2br`。
- **不要在 mermaid 块的位置上期待 codehilite：** 脚本会在 markdown 渲染**之前**把 mermaid 块抽成占位符，渲染后再回填，因此 mermaid 源码不会被 `codehilite` 包成代码块（`codehilite` 会吃掉 `language-mermaid` 类名，事后再靠类名补救是识别不出来的）。
- PDF 由 `markdown-pdf` 直接渲染，不经过 HTML 中间步骤；默认 `Section(md_content, toc=False)`（不自动生成目录），可调整脚本中 `MarkdownPdf` / `Section` 用法以启用目录 / 书签 / 自定义 CSS。
- ⚠️ **PDF 不支持 mermaid 流程图**：`markdown-pdf` 不执行 JavaScript，图中的内容只会以代码块形式呈现。脚本检测到 mermaid 时会打印提示。需要“流程图 + PDF”两者兼得时，建议先生成 HTML，再用浏览器“打印 → 另存为 PDF”。
- PDF 中文渲染依赖系统可用字体：若乱码 / 缺字，检查或补充系统字体。
- 文件不存在时报 `❌ 文件不存在` 并以退出码 1 结束；缺少依赖时报对应安装提示。
- 中文文件名 / 路径在 Windows PowerShell 下可用；若终端中文乱码，可先 `chcp 65001`。
- 相对输出路径以调用时的工作目录（CWD）为准，建议统一在项目根目录执行。
- 终端编码：脚本用 ✅/❌/⚠️/ℹ️ 打印结果。当 stdout 不是控制台句柄时（经管道 / 重定向，如 `2>&1 | ...`），Windows 下编码会退化为 GBK，这些符号会被降级显示为 `?`——**仅为显示层降级，脚本已做 `errors='replace'` 加固，不会中断转换**。需要正常显示符号时先 `chcp 65001`，或不经管道运行。
- 转换失败时向用户如实报告原因，勿谎报成功。
- 运行环境：本仓库 `markdown` / `markdown-pdf` 装在**系统 Python 3.11**（`C:\Program Files\Python311\python.exe`），项目 `.venv` 未安装这两个包。用 `.venv` 运行会报“缺少依赖”。
