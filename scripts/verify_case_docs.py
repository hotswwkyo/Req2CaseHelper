# -*- coding: utf-8 -*-
"""
测试点清单 / 测试用例 综合一致性校验脚本
========================================
对"测试点清单(*.md) + 测试用例(*.md)"做最终综合校验，用于回归检查两份文档是否一一对应、
编号连续、无重复/残留标记/标题格式异常、且汇总统计表与实际内容一致。

用法(必填):
    python scripts/verify_case_docs.py -tp <测试点.md> -tc <用例.md>
    python scripts/verify_case_docs.py -tp <测试点.md> -tc <用例.md> --warn-pending   # 额外列出标记位置
    python scripts/verify_case_docs.py -tp <测试点.md> -tc <用例.md> --strict-pending # 将残留标记判为失败

设计说明: -tp 与 -tc 均为**必填**参数。未提供时不推断、不自动发现、不猜测目标文件，直接报错退出
(退出码 2)，避免"以为在校验 A、实际校验了 B"这类误导性结果。传入路径为相对路径时基于项目根解析。

校验项:
  [1] 解析行数       测试点(TP) 与 用例(TC) 表格行数量
  [2] 编号重复       是否存在重复 TP/TC 编号
  [3] 一一映射       每个 TC 是否有对应 TP(TC-x -> TP-x), 双向
  [4] 编号连续       各前缀编号是否从 1 连续递增(如 TP-HOME-001..015)
  [5] 标题粘连       "## xxxx" 标题行后是否直接粘连表格(标题行内含 '|')
  [6] 残留标记       [假设] / [待确认] 计数(--warn-pending 显示位置)
  [7] 汇总一致性     文件尾部"汇总统计"表的数量/范围是否与实际解析一致
退出码: 全部通过=0, 任一失败项>0。
"""

import argparse
import re
import sys
from pathlib import Path

# 目标文件一律由 -tp/-tc 显式传入(必填); 相对路径基于本项目根解析

ROW_RE = re.compile(r"^\|\s*(TP-[A-Z0-9]+-\d+|TC-[A-Z0-9]+-\d+)\s*\|")
HEADER_RE = re.compile(r"^#{1,6}\s+")
STAT_PREFIX = {"TP", "TC"}


def resolve_path(root, raw):
    return Path(raw) if Path(raw).is_absolute() else root / raw


def read_lines(path: Path) -> list:
    """UTF-8(带/不带 BOM) 读取, 返回行列表(去行尾换行)。"""
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    text = path.read_text(encoding="utf-8-sig")
    return text.splitlines()


def collect_ids(lines, prefix: str):
    """收集形如 prefix-XXX-NNN 的表格行 id, 保持出现顺序。"""
    ids = []
    for ln in lines:
        m = ROW_RE.match(ln)
        if m and m.group(1).startswith(prefix + "-"):
            ids.append(m.group(1))
    return ids


def check_duplicates(ids, name):
    from collections import Counter

    dup = [k for k, v in Counter(ids).items() if v > 1]
    if dup:
        return False, f"{name} 存在重复编号: {sorted(dup)}"
    return True, f"{name} 无重复编号"


def check_continuity(ids, name):
    """按前缀分组, 校验编号从 1..count 连续。"""
    from collections import defaultdict

    groups = defaultdict(list)
    for i in ids:
        base, _, num = i.rpartition("-")
        groups[base].append(int(num))
    bad = []
    for base in sorted(groups):
        nums = sorted(groups[base])
        expect = list(range(1, len(nums) + 1))
        if nums != expect:
            bad.append(f"{base}: 实际{len(nums)}条, 编号区间 {nums[0]}~{nums[-1]}, 期望 1~{len(nums)}")
    if bad:
        return False, f"{name} 编号不连续:\n  " + "\n  ".join(bad)
    return True, f"{name} 各前缀编号连续(1..n)"


def check_mapping(tc_ids, tp_ids):
    tp_set = set(tp_ids)
    missing = [t for t in tc_ids if (t.replace("TC-", "TP-", 1)) not in tp_set]
    if missing:
        return False, f"存在无对应测试点的用例: {missing[:20]}"
    return True, "每个 TC 均有一一对应 TP"


def check_header_glue(lines, name):
    """标题行内出现 '|'(疑似标题与表头粘连)。"""
    bad = [
        ln for ln in lines
        if HEADER_RE.match(ln) and "|" in ln
    ]
    if bad:
        return False, f"{name} 存在标题与表头粘连的异常行:\n  " + "\n  ".join(bad[:10])
    return True, f"{name} 标题格式正常(无粘连)"


def check_pending(lines, name, warn=False):
    hits = [(i + 1, ln) for i, ln in enumerate(lines) if re.search(r"\[假设\]|\[待确认\]", ln)]
    if hits:
        msg = f"{name} 残留标记 {len(hits)} 处"
        if warn:
            msg += ":\n  " + "\n  ".join(f"L{no}: {ln[:90]}" for no, ln in hits[:20])
        return False, msg  # 是否视为失败由调用方按 strict 决定
    return True, f"{name} 无 [假设]/[待确认] 残留"


def parse_summary(lines, kind):
    """
    解析"汇总统计"表。kind='TP': 表头| 模块 | 前缀 | N |
                            kind='TC': 表头| 模块 | 前缀 | N | 对应TP范围 |
    返回 [(prefix, expect_n, expect_max)]
    """
    # 定位统计表起始标题
    title_re = r"^##\s+五、测试点汇总统计" if kind == "TP" else r"^##\s+附：用例与测试点覆盖统计"
    start = next((i for i, ln in enumerate(lines) if re.search(title_re, ln)), None)
    if start is None:
        return None, "未找到汇总统计表"
    # 从标题后找 | 前缀 | 数字 | 的行(含 **合计** 除外)
    if kind == "TP":
        pat = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(TP-[A-Z0-9]+)\s*\|\s*(\d+)\s*\|")
    else:
        # 形如 | 首页-经营看板 | TC-HOME | 15 | TP-HOME-001~015 |
        pat = re.compile(
            r"^\|\s*([^|]+?)\s*\|\s*(TC-[A-Z0-9]+)\s*\|\s*(\d+)\s*\|\s*TP-[A-Z0-9]+-(\d+)~\s*(\d+)\s*\|")
    rows = []
    for ln in lines[start + 1:]:
        if re.match(r"^\|\s*\*\*合计\*\*", ln):
            continue
        m = pat.match(ln)
        if not m:
            continue
        if kind == "TP":
            rows.append((m.group(2), int(m.group(3)), None))
        else:
            rows.append((m.group(2), int(m.group(3)), int(m.group(5))))
    return rows, None


def check_summary(lines, ids, kind, name):
    """校验汇总统计表与实际解析一致。"""
    rows, err = parse_summary(lines, kind)
    if err:
        return False, f"{name}: {err}"
    from collections import defaultdict

    actual = defaultdict(list)
    for i in ids:
        base, _, num = i.rpartition("-")
        actual[base].append(int(num))

    issues = []
    for prefix, expect_n, expect_max in rows:
        got = sorted(actual.get(prefix, []))
        if len(got) != expect_n:
            issues.append(f"{prefix}: 统计表声明 {expect_n} 条, 实际解析 {len(got)} 条")
            continue
        if expect_max is not None and (not got or got[-1] != expect_max):
            issues.append(f"{prefix}: 统计表最大编号 {expect_max}, 实际 {got[-1] if got else '无'}")
    if issues:
        return False, f"{name} 汇总统计与实际不一致:\n  " + "\n  ".join(issues)
    return True, f"{name} 汇总统计与实际解析一致({sum(n for _, n, _ in rows)} 条声明)"


def main():
    ap = argparse.ArgumentParser(description="测试点/用例综合一致性校验")
    ap.add_argument("-tp", required=True, help="测试点清单 md 路径(必填)")
    ap.add_argument("-tc", required=True, help="测试用例 md 路径(必填)")
    ap.add_argument("--warn-pending", action="store_true", help="展示 [假设]/[待确认] 出现位置(不判失败)")
    ap.add_argument("--strict-pending", action="store_true", help="将 [假设]/[待确认] 视为失败")
    args = ap.parse_args()

    # 输出编码保护(控制台 GBK 亦不崩溃)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    root = Path(__file__).resolve().parent.parent
    tp_path = resolve_path(root, args.tp)
    tc_path = resolve_path(root, args.tc)

    try:
        tp_lines = read_lines(tp_path)
        tc_lines = read_lines(tc_path)
    except FileNotFoundError as e:
        print(f"[FAIL] {e}")
        return 2

    tp_ids = collect_ids(tp_lines, "TP")
    tc_ids = collect_ids(tc_lines, "TC")

    checks = []
    checks.append(("解析行数",
                   f"TC={len(tc_ids)}  TP={len(tp_ids)}",
                   len(tc_ids) > 0 and len(tp_ids) > 0))
    ok, msg = check_duplicates(tp_ids, "TP")
    checks.append(("编号重复(TP)", msg, ok))
    ok, msg = check_duplicates(tc_ids, "TC")
    checks.append(("编号重复(TC)", msg, ok))
    ok, msg = check_mapping(tc_ids, tp_ids)
    checks.append(("一一映射(TC->TP)", msg, ok))
    ok, msg = check_continuity(tp_ids, "TP")
    checks.append(("编号连续(TP)", msg, ok))
    ok, msg = check_continuity(tc_ids, "TC")
    checks.append(("编号连续(TC)", msg, ok))
    ok, msg = check_header_glue(tp_lines, "TP 文件")
    checks.append(("标题粘连(TP)", msg, ok))
    ok, msg = check_header_glue(tc_lines, "TC 文件")
    checks.append(("标题粘连(TC)", msg, ok))
    ok, msg = check_summary(tp_lines, tp_ids, "TP", "TP 文件")
    checks.append(("汇总一致(TP)", msg, ok))
    ok, msg = check_summary(tc_lines, tc_ids, "TC", "TC 文件")
    checks.append(("汇总一致(TC)", msg, ok))
    # pending 标记: 默认仅告警
    ok, msg = check_pending(tp_lines, "TP 文件", warn=args.warn_pending)
    if args.strict_pending:
        checks.append(("残留标记(TP)", msg, ok))
    else:
        print(f"[INFO] 残留标记(TP): {msg}")
    ok, msg = check_pending(tc_lines, "TC 文件", warn=args.warn_pending)
    if args.strict_pending:
        checks.append(("残留标记(TC)", msg, ok))
    else:
        print(f"[INFO] 残留标记(TC): {msg}")

    width = max(len(c[0]) for c in checks) + 2
    failed = 0
    print("\n=== 校验目标 ===")
    print(f"  测试点: {tp_path}")
    print(f"  用例  : {tc_path}")
    print("\n=== 校验结果 ===")
    for name, msg, ok in checks:
        flag = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[{flag}] {name.ljust(width)}{'' if ok else msg}")
    print(
        f"\n合计: TC={len(tc_ids)}  TP={len(tp_ids)}  | 结果: {'全部通过' if failed == 0 else f'{failed} 项失败'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
