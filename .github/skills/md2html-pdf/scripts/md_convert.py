#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Markdown 转 HTML / PDF 转换工具

本脚本提供命令行接口，支持将 Markdown 文件转换为美观的 HTML 页面
或 PDF 文档。

- HTML 转换基于 `markdown` 库（开启 extra 扩展），并自动修复
  引用块内列表缺少空行的问题，确保列表正确渲染。
- PDF 转换基于 `markdown-pdf` 库（底层使用 PyMuPDF），
  纯 Python 实现，无外部系统依赖，在 Windows / macOS / Linux
  上均可直接运行。

用法:
    python md_convert.py <input.md> [-o <output>] [--format {html,pdf}]

示例:
    # 将 README.md 转换为 README.html（默认格式）
    python md_convert.py README.md

    # 将 报告.md 转换为 PDF 文件，指定输出路径
    python md_convert.py 报告.md -o 最终报告.pdf

    # 强制转换为 PDF，即使输出后缀为 .html（不推荐，但可行）
    python md_convert.py 文档.md --format pdf -o 文档.html

    # 查看完整帮助
    python md_convert.py -h
"""

import re
import os
import sys
import argparse
from html import escape as _escape_html


# ===== Mermaid 流程图支持 =====

# mermaid 围栏代码块：```mermaid ... ``` 或 ~~~mermaid ... ~~~
_MERMAID_FENCE_RE = re.compile(
    r'^[ \t]*(?P<fence>`{3,}|~{3,})[ \t]*mermaid[ \t]*\r?\n'
    r'(?P<code>.*?)'
    r'^[ \t]*(?P=fence)[ \t]*\r?$',
    re.MULTILINE | re.DOTALL,
)

# 遗留围栏检测（闭合围栏长度与开头不一致时提取会失败）
_MERMAID_LEFTOVER_RE = re.compile(
    r'^[ \t]*(?:`{3,}|~{3,})[ \t]*mermaid', re.MULTILINE
)

# 渲染期占位符：独占一行，避免被其它 markdown 扩展改写
_MERMAID_PLACEHOLDER = '@@MERMAID_BLOCK_{}@@'

# 本地 mermaid 资源（默认内联进 HTML，保证离线 / 内网 / 转发场景可用）
_MERMAID_LOCAL_JS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'assets', 'mermaid.min.js',
)
# 本地资源缺失时的兜底 CDN
_MERMAID_CDN_JS = 'https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js'

# 内联后追加的初始化脚本（含渲染失败兜底，避免"空白无提示"的静默失败）
_MERMAID_INIT_SCRIPT = """<script>
(function () {
  function showError(message) {
    document.querySelectorAll('.mermaid').forEach(function (el) {
      if (el.querySelector('svg')) { return; }
      el.classList.add('mermaid-error');
      var tip = document.createElement('div');
      tip.className = 'mermaid-error-msg';
      tip.textContent = 'Mermaid 渲染失败：' + message;
      el.appendChild(tip);
    });
  }
  function render() {
    if (typeof mermaid === 'undefined') {
      showError('mermaid.js 未加载成功（本地资源缺失且无法访问 CDN）');
      return;
    }
    try {
      mermaid.initialize({
        startOnLoad: false,
        theme: 'neutral',
        securityLevel: 'strict',
        fontFamily: '"Microsoft YaHei", system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif',
        flowchart: { useMaxWidth: true, htmlLabels: true, curve: 'basis' }
      });
      mermaid.run({ querySelector: '.mermaid' }).catch(function (err) {
        showError((err && err.message) || String(err));
      });
    } catch (err) {
      showError((err && err.message) || String(err));
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', render);
  } else {
    render();
  }
})();
</script>"""


def _extract_mermaid_blocks(md_content: str):
    """
    抽出 Markdown 中的 ```mermaid 代码块，替换为独占一行的占位符。

    必须在 markdown 渲染**之前**执行：`fenced_code` / `codehilite` 会把
    围栏块渲染成带语法高亮的 `<code>`，并吃掉 `language-mermaid` 类名，
    导致渲染后无法再靠类名识别。

    Args:
        md_content (str): 原始 Markdown 文本。

    Returns:
        tuple[list[str], str]: (处理后的 Markdown 文本, mermaid 源码列表)
    """
    blocks = []

    def _replace(match):
        blocks.append(match.group('code').rstrip('\n'))
        return _MERMAID_PLACEHOLDER.format(len(blocks) - 1)

    return _MERMAID_FENCE_RE.sub(_replace, md_content), blocks


def _restore_mermaid_blocks(html_body: str, blocks) -> str:
    """
    将占位符回填为 `<div class="mermaid">`，交由浏览器端 mermaid.js 渲染。

    Args:
        html_body (str): markdown 渲染后的 HTML 正文。
        blocks (list[str]): mermaid 源码列表（与占位符下标一一对应）。

    Returns:
        str: 回填后的 HTML 正文。
    """
    for index, code in enumerate(blocks):
        placeholder = _MERMAID_PLACEHOLDER.format(index)
        div = f'<div class="mermaid">\n{code}\n</div>'
        # 占位符单独成段时会被包成 <p>...</p>，两种形态都替换
        html_body = html_body.replace(f'<p>{placeholder}</p>', div)
        html_body = html_body.replace(placeholder, div)
    return html_body


def _build_mermaid_script() -> str:
    """
    生成注入 HTML 末尾的 mermaid 加载 + 初始化脚本。

    优先内联技能目录下的 `assets/mermaid.min.js`（生成物自包含、离线可用）；
    本地资源缺失时回退到 CDN，并打印警告。

    Returns:
        str: 可直接嵌入 `<body>` 末尾的 script 标签片段。
    """
    if os.path.exists(_MERMAID_LOCAL_JS):
        with open(_MERMAID_LOCAL_JS, 'r', encoding='utf-8') as f:
            library = f.read().replace('</script>', r'<\/script>')
        loader = f'<script>\n{library}\n</script>'
    else:
        print(f"⚠️ 警告: 未找到本地 mermaid 资源 {_MERMAID_LOCAL_JS}，"
              f"已回退到 CDN（打开页面需联网）")
        loader = f'<script src="{_MERMAID_CDN_JS}"></script>'
    return loader + '\n' + _MERMAID_INIT_SCRIPT


# ===== 文首 YAML frontmatter 支持 =====

# 文首 frontmatter：起始 --- 独占一行，至下一个 --- 结束
_FRONTMATTER_RE = re.compile(
    r'\A---[ \t]*\r?\n(?P<body>.*?)\r?\n---[ \t]*(?:\r?\n|\Z)',
    re.DOTALL,
)


def _split_frontmatter(md_content: str):
    """
    剥离文首的 YAML frontmatter。

    Args:
        md_content (str): 文件全文。

    Returns:
        tuple: (frontmatter 文本或 None, 去掉 frontmatter 后的正文)。
    """
    match = _FRONTMATTER_RE.match(md_content)
    if not match:
        return None, md_content
    return match.group('body'), md_content[match.end():]


def _parse_frontmatter(frontmatter_text: str):
    """
    解析 `key: value` 形式的 YAML frontmatter（覆盖常见写法）。

    处理规则：跳过空行与 `#` 注释行；引号包裹的值去除引号；
    `[a, b]` 行内数组去掉外层方括号；无冒号的行视为上一项的续行。

    Args:
        frontmatter_text (str): frontmatter 区块文本。

    Returns:
        list: [(key, value), ...]，保持原文顺序。
    """
    rows = []
    for raw_line in frontmatter_text.splitlines():
        line = raw_line.lstrip()
        if not line.strip() or line.startswith('#'):
            continue
        if ':' not in line:
            if rows:
                rows[-1][1] = f"{rows[-1][1]} {line.strip()}".strip()
            continue
        key, _, value = line.partition(':')
        key = key.strip().strip('"\'')
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
            value = value[1:-1]
        if value.startswith('[') and value.endswith(']'):
            value = value[1:-1].strip()
        rows.append([key, value])
    return rows


def _render_frontmatter_table(frontmatter_text: str) -> str:
    """
    把 YAML frontmatter 渲染成 HTML 表格（对齐 VS Code Markdown 预览）。

    Args:
        frontmatter_text (str): frontmatter 区块文本。

    Returns:
        str: `<table class="front-matter">` 片段；无有效键值对时返回空串。
    """
    rows = _parse_frontmatter(frontmatter_text)
    if not rows:
        return ''
    cells = ''.join(
        f'<tr><th>{_escape_html(key)}</th><td>{_escape_html(value)}</td></tr>'
        for key, value in rows
    )
    return f'<table class="front-matter">\n{cells}\n</table>'


def convert_to_html(input_path: str, output_path: str, render_mermaid: bool = True) -> None:
    """
    将 Markdown 文件转换为带样式的 HTML 文件。

    使用 `markdown` 库将 Markdown 文本渲染为 HTML，并嵌入基础的 CSS 样式，
    生成一个完整的、可直接在浏览器中打开的 HTML 页面。

    Markdown 中的 ```mermaid 代码块会被抽出并转为 `<div class="mermaid">`，
    同时把 mermaid.js 内联进页面，由浏览器端渲染成流程图。

    Args:
        input_path (str): 输入的 Markdown 文件路径（必须为 .md 文件）。
        output_path (str): 输出的 HTML 文件路径（应包含 .html 后缀）。
        render_mermaid (bool): 是否渲染 mermaid 流程图，默认 True；
            置为 False 时 mermaid 代码块按普通代码块显示。

    Returns:
        None

    Raises:
        ImportError: 如果未安装 `markdown` 库。
        FileNotFoundError: 如果输入文件不存在（由调用方捕获处理）。
        UnicodeDecodeError: 如果文件编码不是 UTF-8。

    Example:
        >>> convert_to_html("README.md", "docs/index.html")
        ✅ HTML 转换成功: docs/index.html
    """
    try:
        import markdown
    except ImportError:
        print("❌ 缺少依赖，请执行: pip install markdown")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # 移除可能的 BOM 头
    if md_content.startswith('\ufeff'):
        md_content = md_content[1:]

    # ===== 剥离文首 YAML frontmatter，单独渲染为表格（对齐 VS Code 预览效果）=====
    frontmatter_html = ''
    frontmatter_text, md_content = _split_frontmatter(md_content)
    if frontmatter_text:
        frontmatter_html = _render_frontmatter_table(frontmatter_text)
        if frontmatter_html:
            print(f"ℹ️ 已识别文首 YAML frontmatter，已渲染为表格"
                  f"（{len(_parse_frontmatter(frontmatter_text))} 项）")

    # ===== 预处理：抽出 mermaid 代码块（必须在渲染前，否则类名会被 codehilite 吃掉）=====
    mermaid_blocks = []
    if render_mermaid:
        md_content, mermaid_blocks = _extract_mermaid_blocks(md_content)
        if _MERMAID_LEFTOVER_RE.search(md_content):
            print("⚠️ 警告: 存在未能识别的 mermaid 代码块"
                  "（可能是闭合围栏长度与开头不一致），将按纯文本显示")
    elif _MERMAID_LEFTOVER_RE.search(md_content):
        print("ℹ️ 提示: 已按 --no-mermaid 跳过流程图渲染，代码块按纯文本显示")

    # ===== 自动修复：引用块内列表缺少空行 =====

    # 匹配 "> 文本行" 后面紧跟 "> - 列表项" 的情况，在中间插入一个空行
    # 即把 ">\n> -" 替换为 ">\n>\n> -"
    md_content = re.sub(r'(> .+)\n(> - )', r'\1\n>\n\2', md_content)

    # 渲染正文，开启 extra 扩展（包含表格、围栏代码、脚注、属性列表等）
    # 同时开启 toc 和 codehilite 以获得更好效果
    body = markdown.markdown(
        md_content,
        extensions=[
            'extra',          # 表格、围栏代码、脚注、属性列表、定义列表等
            'toc',            # 生成目录（可选）
            'codehilite',     # 代码高亮（需要 Pygments）
            'nl2br',
        ]
    )

    # ===== 回填 frontmatter 表格 =====
    if frontmatter_html:
        body = frontmatter_html + '\n' + body

    # ===== 回填 mermaid 占位符 =====
    mermaid_script = ""
    if mermaid_blocks:
        body = _restore_mermaid_blocks(body, mermaid_blocks)
        mermaid_script = _build_mermaid_script()

    # 构建完整的 HTML 页面，包含丰富的 CSS 样式
    html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{os.path.basename(input_path)}</title>
    <style>
        body {{
            margin: 40px auto;
            padding: 20px;
            line-height: 1.6;
            font-family: "Microsoft YaHei", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            color: #1e1e1e;
            background: #fafafa;
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 1.5em;
            margin-bottom: 0.5em;
            border-bottom: 1px solid #eaecef;
            padding-bottom: 0.3em;
        }}
        h1 {{ font-size: 2.2em; }}
        h2 {{ font-size: 1.8em; }}
        h3 {{ font-size: 1.4em; }}
        blockquote {{
            border-left: 4px solid #dfe2e5;
            padding-left: 1.2em;
            margin-left: 0;
            color: #6a737d;
            background: #f6f8fa;
            padding: 0.5em 1em;
            border-radius: 0 4px 4px 0;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
            font-family: "Microsoft YaHei", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }}
        pre {{
            background: #f6f8fa;
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            border: 1px solid #e1e4e8;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 1.2em 0;
        }}
        table tr {{
            border-width: 1px;
            border-bottom-color: #e6e6e6;
            border-top-style: none;
            border-left-style: none;
            border-right-style: none;
            border-bottom-style: solid;
        }}
        table tr:hover {{
            background-color: #f2f6f6;
        }}
        table thead tr:first-child {{
            border-bottom-color: #666;
        }}
        table tbody tr:last-child {{
            border-bottom-style: none;
        }}
        th, td {{
            /* border: 1px solid #dfe2e5; */
            padding: 8px 12px;
            text-align: left;
        }}
        th {{
            background: #f6f8fa;
            font-weight: 600;
            min-width: 80px;
        }}
        table.front-matter {{
            margin: 0 0 2em 0;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
        }}
        table.front-matter th {{
            width: 130px;
            white-space: nowrap;
            background: #f6f8fa;
            color: #57606a;
        }}
        table.front-matter tr:hover {{
            background-color: transparent;
        }}
        hr {{
            border: none;
            /* border-top: 2px solid #e1e4e8; */
            margin: 2.5em 0;
        }}
        ul, ol {{
            padding-left: 2em;
        }}
        li {{
            margin: 0.3em 0;
        }}
        a {{
            color: #0366d6;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .highlight {{
            background: #f6f8fa;
        }}
        .toc {{
            background: #f6f8fa;
            padding: 1em 1.5em;
            border-radius: 6px;
            margin: 1em 0;
        }}
        .mermaid {{
            background: #ffffff;
            border: 1px solid #e1e4e8;
            border-radius: 8px;
            padding: 16px;
            margin: 1.2em 0;
            text-align: center;
            overflow-x: auto;
            min-height: 32px;
        }}
        .mermaid svg {{
            max-width: 100%;
            height: auto;
        }}
        .mermaid-error {{
            text-align: left;
            white-space: pre-wrap;
            font-family: Consolas, "Courier New", monospace;
            font-size: 0.85em;
            color: #b31d28;
            background: #fff5f5;
            border-color: #f5c6cb;
        }}
        .mermaid-error .mermaid-error-msg {{
            margin-top: 8px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    {body}
    {mermaid_script}
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_template)

    print(f"✅ HTML 转换成功: {output_path}")


def convert_to_pdf(input_path: str, output_path: str) -> None:
    """
    将 Markdown 文件转换为 PDF 文档（纯 Python，无系统依赖）。

    使用 `markdown-pdf` 库（底层基于 PyMuPDF）直接将 Markdown
    渲染为 PDF，无需安装 GTK、Pango 等外部库，在 Windows 上
    开箱即用。支持自定义 CSS、书签、嵌入图片等功能。

    Args:
        input_path (str): 输入的 Markdown 文件路径。
        output_path (str): 输出的 PDF 文件路径（应包含 .pdf 后缀）。

    Returns:
        None

    Raises:
        ImportError: 如果未安装 `markdown-pdf` 库。
        FileNotFoundError: 如果输入文件不存在（由调用方捕获处理）。
        UnicodeDecodeError: 如果文件编码不是 UTF-8。

    Example:
        >>> convert_to_pdf("报告.md", "输出.pdf")
        ✅ PDF 转换成功: 输出.pdf
    """
    try:
        from markdown_pdf import MarkdownPdf, Section
    except ImportError:
        print("❌ 缺少依赖，请执行: pip install markdown-pdf")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # ===== 文首 YAML frontmatter：转为 Markdown 表格（避免被当作普通段落）=====
    frontmatter_text, md_content = _split_frontmatter(md_content)
    if frontmatter_text:
        rows = _parse_frontmatter(frontmatter_text)
        if rows:
            lines = ['| 字段 | 值 |', '| --- | --- |']
            for key, value in rows:
                lines.append('| ' + key + ' | ' + value.replace('|', '\\|') + ' |')
            md_content = '\n'.join(lines) + '\n\n' + md_content
            print("ℹ️ 已识别文首 YAML frontmatter，已转为表格")

    if _MERMAID_LEFTOVER_RE.search(md_content):
        print("ℹ️ 提示: 检测到 mermaid 流程图。PDF 渲染（markdown-pdf）不执行 "
              "JavaScript，图中内容将以代码块形式呈现；如需渲染后的流程图请转 HTML。")

    pdf = MarkdownPdf()
    # 添加章节，toc=False 不自动生成目录（可按需开启）
    pdf.add_section(Section(md_content, toc=False))
    pdf.save(output_path)

    print(f"✅ PDF 转换成功: {output_path}")


def _setup_console() -> None:
    """
    加固控制台输出。

    Windows 下 stdout 编码可能是 GBK（stdout 不是控制台句柄时，
    例如经管道 / 重定向），而脚本使用 ✅ / ❌ / ⚠️ / ℹ️ 等符号打印结果，
    会触发 UnicodeEncodeError 并中断整个转换流程。

    这里在**不改变编码**（避免中文乱码）的前提下把错误处理设为 replace，
    保证打印环节永远不会中断转换。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors='replace')
        except (AttributeError, ValueError, OSError):
            pass


def main() -> None:
    """
    命令行入口函数。

    解析命令行参数，检查输入文件是否存在，并根据用户指定的输出格式
    （HTML 或 PDF）调用相应的转换函数。如果未指定输出格式，则根据
    输出文件后缀（.html / .pdf）自动判断；若后缀不明确，默认转为 HTML。

    Returns:
        None

    Raises:
        SystemExit: 当输入文件不存在或参数错误时，退出程序。
    """
    _setup_console()

    parser = argparse.ArgumentParser(
        description='将 Markdown 文件转换为 HTML 或 PDF',
        epilog='''
使用示例:
  python md_convert.py README.md                    # 转为 HTML，同名文件
  python md_convert.py 报告.md -o 输出.pdf         # 转为 PDF
  python md_convert.py 文档.md --format pdf        # 强制转为 PDF（自动生成同名 .pdf）
  python md_convert.py 笔记.md -o 笔记.html        # 显式指定输出 HTML
  python md_convert.py -h                          # 显示此帮助信息
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('input', help='输入的 .md 文件路径')
    parser.add_argument('-o', '--output', help='输出文件路径（根据后缀 .html/.pdf 决定格式）')
    parser.add_argument('--format', choices=['html', 'pdf'], help='手动指定输出格式（可选）')
    parser.add_argument('--no-mermaid', action='store_true',
                        help='不渲染 mermaid 流程图（代码块按纯文本显示）')

    args = parser.parse_args()

    # 检查输入文件是否存在
    if not os.path.exists(args.input):
        print(f"❌ 文件不存在: {args.input}")
        sys.exit(1)

    # 确定输出格式和路径
    fmt = args.format
    output_path = args.output

    if not output_path:
        base = os.path.splitext(args.input)[0]
        if fmt == 'pdf':
            output_path = base + '.pdf'
        else:
            output_path = base + '.html'
    else:
        if not fmt:
            ext = os.path.splitext(output_path)[1].lower()
            if ext == '.pdf':
                fmt = 'pdf'
            elif ext in ('.html', '.htm'):
                fmt = 'html'
            else:
                print(f"⚠️ 警告: 输出后缀 '{ext}' 不识别，默认转为 HTML")
                fmt = 'html'
                # 如果后缀不识别，追加 .html
                output_path = output_path + '.html'

    if not fmt:
        fmt = 'html'

    # 执行转换
    if fmt == 'html':
        convert_to_html(args.input, output_path, render_mermaid=not args.no_mermaid)
    else:
        convert_to_pdf(args.input, output_path)


if __name__ == "__main__":
    main()
