# -*- coding: utf-8 -*-
import os
import html
from stest.report.html import elements

# settings.py 所在目录路径
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


# 测试用例数据目录
SEVEN_DATA_PROVIDER_DATA_FILE_DIR = os.path.join(PROJECT_DIR, "testdata")

# 测试报告存放目录
TEST_REPORT_DIR = os.path.join(PROJECT_DIR, "report")

# 截图存放目录
SCREENSHOT_SAVE_DIR = os.path.join(PROJECT_DIR, "screenshot")

# 禅道登录信息
# 使用前请将下方占位值替换为真实内网地址与账号，并复制本文件为 settings.py（切勿提交 settings.py）
ZENTAO_URL = "http://<zentao-host>/zentao/"
ZENTAO_USER = "<your-account>"
ZENTAO_PWD = "<your-password>"

TEST_PARAM_NAME_FORMAT_STRING = "{param} - {alias}"

TEST_PARAM_ALIAS = {"priority": "优先级",
                    "author": "编写者",
                    "editors": "修改者",
                    "last_modifyied_by": "最后修改者",
                    "last_modified_time": "最近修改时间",
                    "groups": "所属组",
                    "related_testcases": "相关用例"
                    }


def test_param_value_formatter(param, value):

    if isinstance(value, (list, tuple)):
        html_texts = []
        for one in value:
            text = one if isinstance(one, str) else str(one)
            html_texts.append(elements.P(html.escape(text, False)).to_html())
        return "".join(html_texts)
    else:
        return None


TEST_PARAM_VALUE_FORMATTER = dict(related_testcases=test_param_value_formatter)

# HTML 报告原始 HTML 输出前缀，print 输出中以该前缀开头的行不做 HTML 转义，直接作为原始 HTML 输出到报告
HTML_REPORT_RAW_HTML_PREFIX = "[RAW]"
