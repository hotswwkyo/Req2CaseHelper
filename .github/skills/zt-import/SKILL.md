---
name: zt-import
description: '自动化把测试用例 .xlsx 导入禅道:调用技能脚本 .github/skills/zt-import/scripts/zt_import.py,自动登录禅道、选产品、逐行设所属模块完成批量导入,可生成 html/xml 报告。Use when: 导入用例到禅道 / 禅道导入 / 批量导入禅道 / 用例入库禅道 / 运行 zt_import.py。需先经 md2excel 把 .md 转成 .xlsx(只有 .md 时先引导转换)。'
user-invocable: true
---

# 导入测试用例到禅道(ZenTao)

将 `md2excel` 生成的测试用例 `.xlsx`,经技能脚本 `.github/skills/zt-import/scripts/zt_import.py`(基于 `stest`+Playwright+AutoIt 的自动化浏览器)导入禅道指定产品/模块,可输出 html/xml 报告。本技能**只负责导入**;输入只有 `.md` 时,先引导用户用 `md2excel` 转成 `.xlsx`。

## 何时用
- 用户要"导入用例到禅道 / 禅道导入 / 批量导入禅道 / 用例入库",或已有 `testcases/*.xlsx` 需入库禅道。

## 执行
1. **核对**:`.xlsx` 已存在(缺则先走 md2excel);根目录 `settings.py` 已配 `ZENTAO_URL/USER/PWD`;本机可达禅道;`python -c "import stest"` 通过;与用户确认 `-sname`(项目)与 `-mpath`(模块路径)。
2. 在**项目根目录**运行。脚本已内置 `-sfile`(默认 `./settings.py`,即在项目根运行时直接命中根目录 `settings.py`;在其他目录运行需用 `-sfile` 显式指向项目根目录或其 `settings.py`):

   ```bash
   python .github/skills/zt-import/scripts/zt_import.py -sname <项目名> [-fname <显示名>] -mpath <模块路径> -tcdir <用例目录> -tcfile <文件1.xlsx> [<文件2.xlsx> ...] [-html <报告名>]
   ```

3. 汇报导入的文件、去重记录、`report/` 下报告路径;失败如实说明。

### 参数
| 参数 | 必填 | 说明 |
|------|------|------|
| `-sname` | 是 | 禅道下拉列表选中的项目名称 |
| `-fname` | 否 | 顶部实际显示名,与下拉名不同时用(缺省=sname) |
| `-mpath` | 是 | 目标模块路径,如 `/260528/系统管理/用户管理` |
| `-tcdir` | 是 | `.xlsx` 目录,建议绝对路径(如 `D:\workspace\Req2CaseHelper\testcases`) |
| `-tcfile` | 是 | 可多个;相对 tcdir 文件名或绝对路径均可 |
| `-html` | 否 | 生成 html+同名 xml;相对路径基于运行目录,建议用绝对路径写到 `report/` |
| `-sfile` | 否 | settings 目录或文件路径,默认 `./settings.py`(项目根运行即可命中) || `-savewait` | 否 | 点【保存】后等待跳回用例列表的超时秒数（默认 **60**）；批量条数多时禅道保存较慢，若报 `wait_for` 超时可调大（可选） |
## 注意
- **在项目根目录运行**(或任意目录加 `-sfile D:\workspace\Req2CaseHelper`):stest 默认按脚本文件位置回溯查找 `settings.py`,脚本在 `scripts/` 下会找不到根配置(报 `TypeError ... NoneType`);本脚本已用 `-sfile`(默认 `./settings.py`)显式加载根 `settings.py` 解决。
- **真实写入禅道**:导入前核对项目/模块,避免导错产品。
- **去重**:成功导入的文件路径记录在 `testdata/imported_testcase_files.txt`,下次自动跳过;重导需手动删对应行。- **分页/拆分文件**：md2excel 的 `--split`/`--split-module` 产出的多个 xlsx 可一次 `-tcfile` 全部导入；但 **`-mpath` 须询问用户**——文件名中的模块名/「所属模块」列 ≠ 禅道真实模块路径（如 `/260528/系统管理/用户管理`），由用户给出整批或每个文件对应的真实 `-mpath`。- **无人工交互**：脚本内 `messagebox` 调试弹窗已注释移除（已稳定运行），导入过程无需点按；如需临时中断，可自行取消注释。
- **失败 ≠ 未入库**：`submit()` = “点【保存】+ 等跳回列表页”。若禅道保存较慢而等待超时，**用例可能已真正入库**。重跑前**务必先到禅道确认**，否则会重复导入；必要时用 `-savewait` 调大超时（实测 90 条批量保存 > 10s）。
- 下拉名≠显示名时用 `-fname`。
- 脚本为**单一来源**存放于技能 scripts/(根目录无副本);与脚本不符时以 `python .github/skills/zt-import/scripts/zt_import.py -h` 为准。
