---
name: md2excel
description: '将 Markdown 格式的测试用例文件转换为 Excel（.xlsx）表格，用于禅道测试用例导入。Use when: 需要把测试用例 .md 转成 Excel / 转换为 xlsx / 测试用例导入禅道用表格 / 生成测试用例 Excel 文件。在生成 MD 格式测试用例后主动询问是否转换 Excel。'
user-invocable: true
---

# MD 转 Excel 技能

## 描述
在生成 Markdown 格式的测试用例文件后，询问用户是否需要将其转换为 Excel 格式。若用户确认，则调用 `.github/skills/md2excel/scripts/md2excel.py` 脚本完成转换。

## 触发条件
- 技能二（生成测试用例）执行完毕，已生成 MD 测试用例文件并保存到 `testcases/` 目录后
- 用户未明确拒绝转换为 Excel

## 执行步骤

1. **询问用户**
   > 测试用例已生成并保存至 `testcases/[文件名].md`，是否需要同时转换为 Excel 格式？

2. **若用户确认**
   - 在终端中执行以下命令：
     ```
     python .github/skills/md2excel/scripts/md2excel.py
     ```
   - 等待执行完成
   - 向用户报告转换结果（成功/失败、生成的文件名）

3. **若用户拒绝或未回应**
   - 跳过此步骤，继续后续流程

## 脚本使用说明

### 基本用法
```bash
# 转换 testcases 目录下所有 MD 文件（推荐）
python .github/skills/md2excel/scripts/md2excel.py

# 指定一个或多个 MD 文件进行转换
python .github/skills/md2excel/scripts/md2excel.py testcases/文件1.md testcases/文件2.md

# 转换到指定输出目录
python .github/skills/md2excel/scripts/md2excel.py -o ./output

# 强制重新转换（忽略已转换记录；仅作用于本次处理到的文件，其它文件的记录保留）
python .github/skills/md2excel/scripts/md2excel.py --force

# 按条数分页：每个文件最多 N 条用例（多页加 _001/_002 后缀；缺省 N=90）
python .github/skills/md2excel/scripts/md2excel.py --split 90 testcases/文件.md
python .github/skills/md2excel/scripts/md2excel.py --split testcases/文件.md

# 按"所属模块"拆分：每个模块一个文件（自动带上"所属模块"列）
python .github/skills/md2excel/scripts/md2excel.py --split-module testcases/文件.md

# 在"用例标题"前加前缀【所属模块】
python .github/skills/md2excel/scripts/md2excel.py --title-prefix-module testcases/文件.md
```

### 参数说明
| 参数 | 说明 |
|------|------|
| `files` | 指定一个或多个 MD 文件路径（可选，不指定则自动扫描 `testcases/` 目录） |
| `-o` / `--output` | 指定 Excel 输出目录（可选，不指定则与 MD 文件同目录） |
| `--force` | 强制重新转换，忽略已转换记录（**仅作用于本次处理到的文件**，其它文件的转换记录保留）（可选） |
| `--split [N]` | 按条数分页拆分，每文件最多 N 条用例，多页加 `_001/_002` 后缀；缺省 N=90；与 `--split-module` 互斥（可选） |
| `--split-module` | 按"所属模块"拆分，每个模块一个文件，自动开启 `--with-module`；MD 无该列时退化为单个文件（可选） |
| `--title-prefix-module` | 在"用例标题"前加前缀【所属模块】，如 `【首页-年份栏】年份栏默认显示当前年份`（需 MD 含"所属模块"列，缺列时自动跳过并提示）（可选） |

### 依赖安装
```bash
pip install openpyxl
```

### 转换记录机制
- 转换记录自动保存在项目根目录的 `md2excel_record.json` 文件中
- 记录格式：`[{"md": "MD文件完整路径", "excels": ["Excel文件1完整路径", ...]}, ...]`；一个 MD 可能拆分成多个 Excel，记录为该 MD **最近一次生成的输出集合**（替换式更新）
- 旧版 `excel`(字符串) 格式记录为测试数据、**不迁移**；检测到旧格式/结构不符时直接视为空记录，重新转换后写入新结构
- 已转换过的文件不会重复转换，除非使用 `--force` 参数（`--force` 只失效本次处理到的文件，**不再清空整份记录**）
- 若 Excel 输出路径发生变化（如指定了不同的输出目录），会自动更新记录并重新转换

### 注意事项
- 脚本会自动识别 `testcases/` 目录下包含测试用例表格（含"用例标题""前置条件""测试步骤""预期结果"表头）的 MD 文件
- 转换后的 Excel 文件列顺序：所属模块 → 相关需求 → 用例标题 → 前置条件 → 步骤 → 预期 → 关键词 → 优先级 → 用例类型 → 适用阶段 → 用例状态
- 开启 `--title-prefix-module` 时，"用例标题"列为 `【所属模块】原标题`；该参数不影响其余列
- 其中"优先级"固定为"2"，"用例类型"固定为"功能测试"，"用例状态"固定为"正常"
- Excel 字体使用"微软雅黑 Light"11号，表头加粗并带蓝灰色背景
