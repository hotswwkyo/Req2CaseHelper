#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 .docx 按文档顺序提取为 Markdown 文本（段落 + 表格 + 列表样式）。

用法:
    python scripts/docx2md.py <input.docx> [-o output.md] [--no-style]

- 按 body 顺序遍历：段落 -> 文本，表格 -> Markdown 表格。
- 段落样式为 "List Paragraph"/"List Bullet"/"List Number" 时，前面加 "- "，
  以便后续「列表项挖掘」检查（列表项可能隐藏独立功能点）。
- 输出 UTF-8。无 -o 时输出到与输入同目录同名 .md。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from docx import Document
    from docx.document import Document as _Doc
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph
except ImportError:  # pragma: no cover
    print("缺少依赖 python-docx，请先安装：pip install python-docx", file=sys.stderr)
    raise SystemExit(3)


def _iter_block_items(parent: "_Doc"):
    """按文档顺序产出 Paragraph / Table 对象。"""
    if isinstance(parent, _Doc):
        parent_elm = parent.element.body
    else:  # 单元格内嵌套
        parent_elm = parent._tc
    for child in parent_elm.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)


def _cell_text(cell) -> str:
    """单元格文本：段落用 <br> 连接，转义竖线。"""
    parts = [p.text.strip() for p in cell.paragraphs if p.text.strip()]
    text = "<br>".join(parts)
    return text.replace("|", "\\|")


def _table_to_md(table: Table) -> str:
    rows = []
    for row in table.rows:
        rows.append([_cell_text(c) for c in row.cells])
    if not rows:
        return ""
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |",
             "|" + "---|" * ncol]
    for r in rows[1:]:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def _para_text(p: Paragraph, use_style: bool) -> str:
    text = p.text.rstrip()
    if not text.strip():
        return ""
    style = ""
    if use_style and p.style is not None:
        style = p.style.name or ""
    low = style.lower()
    if "list" in low:
        if "number" in low:
            return f"- {text}"
        return f"- {text}"
    # 依据段落层级给标题加 #（Heading 1/2/3）
    if low.startswith("heading"):
        try:
            lvl = int(style.split()[-1])
        except ValueError:
            lvl = 1
        lvl = min(max(lvl, 1), 6)
        return "#" * lvl + " " + text
    return text


def convert(in_path: Path, out_path: Path, use_style: bool = True) -> int:
    doc = Document(str(in_path))
    blocks: list[str] = []
    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            t = _para_text(block, use_style)
            if t:
                blocks.append(t)
        elif isinstance(block, Table):
            t = _table_to_md(block)
            if t:
                blocks.append(t)
    content = "\n\n".join(blocks) + "\n"
    out_path.write_text(content, encoding="utf-8")
    return len(blocks)


def main() -> int:
    ap = argparse.ArgumentParser(description="docx -> markdown 文本提取")
    ap.add_argument("input", help="输入 .docx 路径")
    ap.add_argument("-o", "--output", help="输出 .md 路径（缺省同名 .md）")
    ap.add_argument("--no-style", action="store_true",
                    help="忽略段落样式（不加标题/列表前缀）")
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.is_file():
        print(f"找不到输入文件：{in_path}", file=sys.stderr)
        return 2
    out_path = Path(args.output) if args.output else in_path.with_suffix(".md")
    n = convert(in_path, out_path, use_style=not args.no_style)
    print(f"已提取 {n} 个块 -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
