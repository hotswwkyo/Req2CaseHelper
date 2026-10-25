# -*- coding: utf-8 -*-
import os
import stest
import typing
import argparse
from stest import hook
# from tkinter import messagebox
from stest.utils import sutils
from playwright.sync_api import Locator
from stest.testobjs.useful.table_locator import Table
from stest.utils.autoit_helper import input_upload_file_path
from stest.core.abstract_data_provider import AbsractDataProvider
from stest.testobjs.abstract_playwright_page import AbstractPlaywrightPage as Page


# 点【保存】后等待"跳回用例列表"的默认超时（秒）。
# 批量条数多时禅道保存较慢（实测 90 条 > 10s），旧值 10s 会把"保存已成功"误报为失败。
# 运行时可通过 -savewait 覆盖；parse_command_line() 会把结果写入 SAVE_WAIT_TIMEOUT_MS。
DEFAULT_SAVE_WAIT_SECONDS = 60
SAVE_WAIT_TIMEOUT_MS = DEFAULT_SAVE_WAIT_SECONDS * 1000


class TestCaseDataProvider(AbsractDataProvider):
    def __init__(self):
        super().__init__()
        self.testdata: dict = None
        self.report_args: list = []

    def parse_command_line(self):
        """
        解析命令行参数，包括业务参数和报告参数。
        返回 report_args 列表，供 stest.run_test 使用。
        """
        parser = argparse.ArgumentParser(description="导入测试用例到禅道")
        # 业务参数
        parser.add_argument("-sname", "--select_name", type=str, required=True, dest="select_name",
                            help="下拉列表中选中的项目名称")
        parser.add_argument("-fname", "--finally_name", type=str, default=None, dest="finally_name",
                            help="最终显示的项目名称（若不指定，则与 -sname 相同）")
        parser.add_argument("-mpath", "--module_path", type=str, required=True, dest="module_path",
                            help="目标模块路径，如 /产品/模块/子模块")
        parser.add_argument("-tcdir", "--testcase_dir", type=str, required=True, dest="testcase_dir",
                            help="测试用例文件所在目录")
        parser.add_argument("-tcfile", "--testcase_file", type=str, required=True, dest="testcase_file", nargs="+",
                            help="测试用例文件名（可指定多个，空格分隔）")
        # 报告参数（显式添加，避免与 -h 冲突）
        parser.add_argument("-html", "--html", type=str, dest="html", help="html测试报告文件名（相对或绝对路径皆可）")
        parser.add_argument("-sfile", "--settings_file", type=str,
                            dest="settings_file", help="配置文件目录或路径，默认为 ./settings.py", default="./settings.py")
        parser.add_argument("-savewait", "--save_wait", type=int, default=DEFAULT_SAVE_WAIT_SECONDS,
                            dest="save_wait",
                            help=f"点【保存】后等待跳回用例列表的超时秒数（默认 {DEFAULT_SAVE_WAIT_SECONDS}）")

        known_args, unknown_args = parser.parse_known_args()

        # 保存等待超时（秒 → 毫秒），供 LoginPage.Actions.submit() 使用
        global SAVE_WAIT_TIMEOUT_MS
        SAVE_WAIT_TIMEOUT_MS = max(1, int(known_args.save_wait)) * 1000

        # 存储业务数据
        self.testdata = {
            "下拉列表中的项目名称": known_args.select_name,
            "最终显示的项目名称": known_args.finally_name or known_args.select_name,
            "要导入到的模块路径": known_args.module_path,
            "测试用例文件路径": [os.path.join(known_args.testcase_dir, filename)
                         for filename in known_args.testcase_file]
        }

        htmlfile: str = known_args.html
        if htmlfile and not htmlfile.endswith(".html"):
            htmlfile += ".html"
        xmlfile = htmlfile.replace(".html", ".xml") if htmlfile else None

        sfilepath: str = os.path.abspath(
            known_args.settings_file) if known_args.settings_file else None
        if sfilepath and os.path.isdir(sfilepath):
            sfilepath = os.path.join(sfilepath, "settings.py")

        # 构建报告参数
        self.report_args = ["-html", known_args.html, "-junit_xml", xmlfile] if htmlfile else []
        self.report_args += ["-sfile", sfilepath] if sfilepath else []

        # 如果有未知参数，可以记录警告（此处忽略）
        if unknown_args:
            print(f"警告: 忽略未识别的参数: {unknown_args}")

        return self.report_args

    def get_testdata(self, test_class_name, test_method_name, *args, **kwargs):
        """
        获取测试数据
        """
        if self.testdata is None:
            raise ValueError("请先调用 parse_command_line() 方法获取测试数据。")
        return [self.testdata]


testdata_provider = TestCaseDataProvider()


class LoginPage(Page):

    def _build_elements(self):
        rv = super()._build_elements()
        self.elements = typing.cast(LoginPage.Elements, self.elements)
        return rv

    def _build_actions(self):
        rv = super()._build_actions()
        self.actions = typing.cast(LoginPage.Actions, self.actions)
        return rv

    def subpage(self):
        pass

    class Elements(Page.Elements):

        def init(self):

            self.page = typing.cast(LoginPage, self.page)

        def __html_input(self, label):
            """html input"""
            xpath = '//form//label[normalize-space()="{}"]/following-sibling::div//input'.format(label)
            return self.page.get_by_xpath(xpath)

        def __html_textarea(self, label):
            """html input"""
            xpath = '//form//label[normalize-space()="{}"]/following-sibling::div//textarea'.format(label)
            return self.page.get_by_xpath(xpath)

        def __html_button(self, name):

            xpath = '//button/span[normalize-space()="{}"]'.format(name)
            return self.page.get_by_xpath(xpath)

        def __btn_bar(self, name):

            xpath = '//div[@class="el-card__body"]//button/span[normalize-space()="{}"]'.format(name)
            return self.page.get_by_xpath(xpath)

        @property
        def username(self):

            # name = "用户名"
            xpath = '//div[@id="login-panel"]//input[@id="account"]'
            return self.page.get_by_xpath(xpath)

        @property
        def passwrod(self):
            name = "密码"
            xpath = '//div[@id="login-panel"]//tr/th[normalize-space()="{}"]/following-sibling::td/input[@name="password"]'.format(name)
            return self.page.get_by_xpath(xpath)

        def __top_menu(self, name):
            """顶部菜单"""

            xpath = '//nav[@id="mainmenu"]/ul/li[@data-id="qa"]/a[normalize-space()="{}"]/parent::li'.format(
                name)
            return self.page.get_by_xpath(xpath)

        def __module_menu(self, name):

            xpath = '//nav[@id="modulemenu"]/ul/li/a[normalize-space()="{}"]'.format(
                name)
            return self.page.get_by_xpath(xpath)

        def tc_tab(self):
            name = "用例"
            return self.__module_menu(name)

        def product(self, name=None):

            if name:
                wy = 'normalize-space()="{}"'.format(name)
            else:
                wy = '@class="title"'
            xpath = '//nav[@id="modulemenu"]/ul/li[@data-id="product"]/a[@id="currentItem"]/span[{}]'.format(
                wy)
            return self.page.get_by_xpath(xpath)

        def product_list(self, name):

            xpath = '//nav[@id="modulemenu"]/ul/li[@data-id="product"]/div[@id="dropMenu"]//div[@id="defaultMenu"]/ul/li/a[normalize-space()="{}"]'.format(
                name)
            return self.page.get_by_xpath(xpath)

        def feature_bar(self, name, lvn=None):

            subxpath = ""
            xpath = '//div[@id="featurebar"]//div[contains(@class,"btn-group")]/button[normalize-space()="{}"]'.format(
                name)
            if lvn:
                subxpath = 'following-sibling::ul/li/a[normalize-space()="{}"]'.format(lvn)

            xpath = self.page.join_xpaths(xpath, subxpath)
            return self.page.get_by_xpath(xpath)

        def __side_menu(self, lv1_menu: typing.Union[str, Locator], *lvn_menus):
            """侧边菜单"""

            lvn_menu_xpath = '/ancestor::li/ul[@role="menu"]//li/span[normalize-space()="{}"]/parent::li'
            xpathlist = []
            for lvn_menu in lvn_menus:
                xpathlist.append(lvn_menu_xpath.format(lvn_menu))
            if isinstance(lv1_menu, Locator):
                return lv1_menu.locator(self.page.join_xpaths(*xpathlist, prefix="xpath="))
            else:
                lv1_menu_xpath = '//ul[@role="menubar"]//li[@role="menuitem"]/div[@class="el-submenu__title"]/span[normalize-space()="{}"]/parent::div'.format(lv1_menu)
                xpathlist.insert(0, lv1_menu_xpath)
                xpath = self.page.join_xpaths(*xpathlist)
                return self.page.get_by_xpath(xpath)

        top_menu = __top_menu
        side_menu = __side_menu

        def __combobox(self, name):
            xpath = '//form//label[normalize-space()="{}"]/following-sibling::div[class="el-form-item__content"]//input'.format(name)
            return self.page.get_by_xpath(xpath)

        def __search_input(self, label):
            """html input"""
            xpath = '//div[@class="fixed-assets-container"]//form//div[contains(@class,"el-form-item__content")]//input[@placeholder="{}"]'.format(
                label)
            return self.page.get_by_xpath(xpath)

        @property
        def add(self):
            """添加按钮"""

            name = "添加"
            return self.__btn_bar(name)

        @property
        def submit(self):
            """提交"""

            name = '提交'
            return self.page.pwpage.get_by_role("button", name=name)

        @property
        def save(self):
            """保存"""

            name = '保存'
            return self.page.pwpage.get_by_role("button", name=name)

        @property
        def login(self):
            name = "登录"
            return self.page.get_by_xpath('//div[@id="login-form"]//button[@id="submit" and normalize-space()="{}"]'.format(name))

        def belong_moudle(self, row: Locator, mpath=None):

            qz = 'xpath='
            if mpath is None:
                xpath = './td[4]/select[@id]/following-sibling::div[contains(@id,"module")]/a[contains(@class,"chosen-single")]/span[@title]'
            else:
                xpath = './td[4]/select[@id]/following-sibling::div[contains(@id,"module")]/a[contains(@class,"chosen-single")]/span[normalize-space()="{}"]'.format(
                    mpath)
            selector = qz + xpath
            return row.locator(selector)

    class Actions(Page.Actions):
        def __init__(self, page):
            super().__init__(page)
            self.page = typing.cast(LoginPage, self.page)

            titles = ['行号', '用例编号', '用例标题', '所属模块']
            self.tctable = Table(page, *titles)
            self.tctable.default_head_xpath = '//form/table[@id="showData"]/thead'
            self.tctable.default_body_xpath = './following-sibling::tbody'
            self.tctable.set_head_cell_xpath("./parent::tr/th", '行号', '用例编号', '用例标题', '所属模块')

        def login(self, name, pwd):

            self.page.elements.username.fill(name)
            self.page.elements.passwrod.fill(pwd)
            self.page.elements.login.click()
            return self

        def _select_module(self, row: Locator, mpaths, sep="/"):

            # target = sep.join(mpaths)
            target = mpaths
            if not target.startswith(sep):
                target = sep + target
            curr = self.page.elements.belong_moudle(row).text_content().strip()
            td_xpath = './parent::a/following-sibling::div[contains(@class,"chosen-drop")]/ul[contains(@class,"chosen-results")]/li[normalize-space()="{}"]'
            if curr != target:
                self.page.elements.belong_moudle(row).click()
                self.sleep(1)
                selector = "xpath=" + td_xpath.format(target)
                self.page.elements.belong_moudle(row).locator(selector).click()
            return self

        def import_testcase(self, pname, module_paths, testcasefile, show_name=None):
            """

            Parameters
            ----------
            pname: 下拉列表中的项目名称
            module_paths: 所属模块路径
            testcasefile: 测试用例文件完整路径
            show_name: 选择后显示的项目名称
            """

            mpaths = module_paths
            self.page.elements.top_menu("测试").click()
            self.sleep(1)
            el_product = self.page.elements.product()
            count = 1
            maxcount = 10
            if show_name is None:
                show_name = pname
            while el_product.text_content().strip() != show_name:
                count += 1
                el_product.click()
                self.sleep(1)
                self.page.elements.product_list(pname).click()
                self.sleep(1)
                if count > maxcount:
                    break
            self.page.elements.product(show_name).highlight()
            self.page.elements.tc_tab().click()
            self.page.elements.feature_bar("导入").click()
            self.sleep(1)
            self.page.elements.feature_bar("导入", "导入Excel").click()

            iselector = 'xpath=//form/table//tr/td/input[@type="file"]'
            btnselector = 'xpath=//form/table//tr/td/button[@id="submit"]'
            iframe = self.page.frame_locator("#modalIframe")
            e_input = iframe.locator(iselector)
            e_input.click()
            self.sleep(1)
            input_upload_file_path(testcasefile)
            self.sleep(1)
            e_btn = iframe.locator(btnselector)
            e_btn.click()
            # 1. 等待模态框 (iframe) 从 DOM 中移除
            self.page.pwpage.wait_for_selector("#modalIframe", state="detached", timeout=10000)
            # 3. 【关键】显式等待表格出现，确保新页面的内容已经渲染
            self.page.pwpage.wait_for_selector(
                "xpath=//form/table[@id='showData']/tbody/tr", state="visible", timeout=10000)
            el_rows = self.tctable.all_rows.all()
            for i, el_row in enumerate(el_rows):
                self._select_module(el_row, mpaths)
                if i == len(el_rows) - 1:
                    self.tctable.cell(el_row, "所属模块").focus()
            return self

        def click_side_menu(self, *side_menus):
            """点击菜单

            Parameters
            ----------
            top_menu: 顶部菜单名称
            side_menus: 侧边栏菜单 side_menus=[一级菜单, 二级菜单, ...]
            """

            count = len(side_menus)
            loop = (count - 1) if count > 1 else 1
            for i in range(loop):
                name = side_menus[i]
                menu = self.page.elements.side_menu(name)
                el_is_opened = menu.locator(self.page.join_xpaths(
                    './ancestor::li', prefix="xpath="))
                while (True):
                    is_opened = el_is_opened.get_attribute("class").find("is-opened")
                    if is_opened != -1:
                        break
                    menu.click()
                    self.sleep(1)

                if count > 1:
                    next_ids = i + 1
                    submenu = self.page.elements.side_menu(menu, side_menus[next_ids])
                    submenu.click()
            return self

        def submit(self):
            self.page.elements.save.click()
            # 等待跳回用例列表（featurebar 里重新出现"导入"按钮）。
            # 超时值可配置：批量条数多时保存较慢，若过短会把"保存已成功"误报为失败。
            self.page.elements.feature_bar("导入").wait_for(
                state="visible", timeout=SAVE_WAIT_TIMEOUT_MS)
            # 或等待列表表格首行
            # self.page.pwpage.wait_for_selector("xpath=//form/table[@id='showData']/tbody/tr", state="visible", timeout=SAVE_WAIT_TIMEOUT_MS)
            return self


class ZT_Import(stest.AbstractTestCase):
    """禅道导用例"""

    @classmethod
    def setUpClass(cls):

        cls.is_set_stoptest = False
        cls.yes = ["y", "yes", "是"]
        cls.savedir = stest.settings.SEVEN_DATA_PROVIDER_DATA_FILE_DIR
        if not os.path.exists(cls.savedir):
            os.makedirs(cls.savedir)
        cls.savepath = os.path.join(cls.savedir, "imported_testcase_files.txt")

    def setUp(self):

        return super().setUp()

    @property
    def cmp(self):
        """数字后缀比较器: (1233) 提取括号中的数字作比较"""
        return sutils.digital_suffix_cmp_wrapper(lambda suffix: suffix.lstrip("(").rstrip(")"))

    def record(self, tcfile: str):
        """记录已导入到禅道的测试用例数据，方便后续查询和删除"""
        tcfile = tcfile.strip()
        with open(self.savepath, "a", encoding="utf-8") as f:
            f.write(tcfile + "\n")
        return self

    @stest.Test(name="导测试用例到禅道中", groups=["it2zt"], data_provider=testdata_provider.get_testdata, screenshot=True)
    def import_testcase_to_zentaopms(self, testdata: dict):

        runit = testdata.pop("是否执行", self.yes[0])
        if runit.lower() not in [one.lower() for one in self.yes]:
            return
        url = stest.settings.ZENTAO_URL
        user = stest.settings.ZENTAO_USER
        pwd = stest.settings.ZENTAO_PWD
        pname = testdata.get("下拉列表中的项目名称")
        show_name = testdata.get("最终显示的项目名称")
        tcfilelist = testdata.get("测试用例文件路径")
        module_paths = testdata.get("要导入到的模块路径")
        # d_suffix_regex = r"\(\d+\)$"
        # module_paths = sutils.group_by_suffix_regex(testdata, d_suffix_regex, True, self.cmp)

        if os.path.exists(self.savepath):

            with open(self.savepath, "r", encoding="utf-8") as f:
                imported_files = [line.strip() for line in f.readlines()]
            aready_imported_files = []
            unimported_files = []
            for tcfile in tcfilelist:
                if tcfile in imported_files:
                    aready_imported_files.append(tcfile)
                else:
                    unimported_files.append(tcfile)
        else:
            unimported_files = tcfilelist
            aready_imported_files = []
        if aready_imported_files:
            print("以下测试用例文件已导入到禅道中，跳过导入：")
            for one in aready_imported_files:
                print(one)

        if unimported_files:
            page = LoginPage()
            page.chrome(browser_context_args=dict(ignore_https_errors=True)).open_url(url)
            page.actions.login(user, pwd).sleep(2)
            for unimported_file in unimported_files:
                page.actions.import_testcase(pname, module_paths, unimported_file, show_name=show_name).sleep(
                    1).show2html(self, name="导入测试用例文件: {}".format(os.path.basename(unimported_file)))
                # messagebox.askokcancel("暂停")
                page.actions.submit()
                self.record(unimported_file)

            print("所有测试用例文件已导入到禅道中，导入完成。")
        else:
            print("没有需要导入的测试用例文件，导入完成。")

    def tearDown(self):

        if not self.is_set_stoptest:
            hook.wrapper(hook.RunStage.stopTest, runpolicy=hook.RunPolicy.AFTER)(
                lambda settings, result, testcase: LoginPage.DRIVER_MANAGER.close_all_drivers())
            self.is_set_stoptest = True

    @classmethod
    def tearDownClass(cls):
        return super().tearDownClass()


if __name__ == '__main__':
    report_args = testdata_provider.parse_command_line()
    ZT_Import.run_test(buffer=True, argv=["python -m stest", "-g", "it2zt"] + report_args)
