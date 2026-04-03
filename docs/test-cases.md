# 测试用例说明文档

> 本文档记录项目所有自动化测试用例，按模块和类型分类。
> 最后更新：2026-03-27

## 概览

| 分类                           | 文件                                        | 用例数  |
| ------------------------------ | ------------------------------------------- | ------- |
| 基础设施验证                   | `tests/test_setup_validation.py`            | 17      |
| Web Config 单元测试            | `tests/unit/test_web_config.py`             | 3       |
| Web Check Environment 单元测试 | `tests/unit/test_web_check_environment.py`  | 22      |
| Web Concert 单元测试           | `tests/unit/test_web_concert.py`            | 120     |
| Web Damai 单元测试             | `tests/unit/test_web_damai.py`              | 8       |
| Mobile Config 单元测试         | `tests/unit/test_mobile_config.py`          | 10      |
| Mobile DamaiApp 单元测试       | `tests/unit/test_mobile_damai_app.py`       | 24      |
| Web 集成测试                   | `tests/integration/test_web_workflow.py`    | 9       |
| Mobile 集成测试                | `tests/integration/test_mobile_workflow.py` | 7       |
| **合计**                       | **9 个文件**                                | **220** |

---

## 1. 基础设施验证 (`tests/test_setup_validation.py`)

验证测试框架本身是否正确配置。

| #   | 测试类                    | 测试方法                          | 说明                                          |
| --- | ------------------------- | --------------------------------- | --------------------------------------------- |
| 1   | TestInfrastructureSetup   | test_project_structure_exists     | 验证项目目录结构（web/、mobile/、tests/）存在 |
| 2   | TestInfrastructureSetup   | test_pyproject_toml_exists        | 验证 pyproject.toml 存在且可解析              |
| 3   | TestInfrastructureSetup   | test_conftest_exists              | 验证 conftest.py 存在                         |
| 4   | TestInfrastructureSetup   | test_packages_importable          | 验证 web、mobile 包可以导入                   |
| 5   | TestInfrastructureSetup   | test_unit_marker_works            | 验证 pytest unit marker 正常工作              |
| 6   | TestInfrastructureSetup   | test_integration_marker_works     | 验证 pytest integration marker 正常工作       |
| 7   | TestInfrastructureSetup   | test_slow_marker_works            | 验证 pytest slow marker 正常工作              |
| 8   | TestFixturesAvailable     | test_temp_dir_fixture             | 验证 temp_dir fixture 返回有效临时目录        |
| 9   | TestFixturesAvailable     | test_mock_config_fixture          | 验证 mock_config fixture 返回字典             |
| 10  | TestFixturesAvailable     | test_mock_selenium_driver_fixture | 验证 mock_selenium_driver fixture             |
| 11  | TestFixturesAvailable     | test_mock_u2_driver_fixture       | 验证 mock_u2_driver fixture                   |
| 12  | TestFixturesAvailable     | test_sample_html_response_fixture | 验证 HTML 响应 fixture                        |
| 13  | TestFixturesAvailable     | test_mock_time_fixture            | 验证时间 mock fixture                         |
| 14  | TestFixturesAvailable     | test_mock_file_operations_fixture | 验证文件操作 fixture                          |
| 15  | TestCoverageConfiguration | test_coverage_configured          | 验证覆盖率配置（源目录、排除规则、阈值）      |
| 16  | (module)                  | test_pytest_can_discover_tests    | 验证 pytest 能发现测试用例                    |

---

## 2. Web 模块 — Config (`tests/unit/test_web_config.py`)

| #   | 测试类        | 测试方法                                   | 说明                                                            |
| --- | ------------- | ------------------------------------------ | --------------------------------------------------------------- |
| 1   | TestWebConfig | test_config_init_stores_all_attributes     | 验证 12 个参数全部正确存储                                      |
| 2   | TestWebConfig | test_config_init_default_values            | 验证默认值：max_retries=1000, fast_mode=True, page_load_delay=2 |
| 3   | TestWebConfig | test_config_init_custom_overrides_defaults | 验证自定义值覆盖默认值                                          |

---

## 3. Web 模块 — Check Environment (`tests/unit/test_web_check_environment.py`)

环境检查模块测试，验证 Chrome/ChromeDriver 检测与安装逻辑。

| #   | 测试类                   | 测试方法                                             | 说明                                   |
| --- | ------------------------ | ---------------------------------------------------- | -------------------------------------- |
| 1   | TestGetVersionFromOutput | test_extracts_major_version_from_chrome_string       | 从 Chrome 版本字符串提取主版本号       |
| 2   | TestGetVersionFromOutput | test_extracts_major_version_from_chromedriver_string | 从 ChromeDriver 版本字符串提取主版本号 |
| 3   | TestGetVersionFromOutput | test_returns_none_for_string_without_version         | 无版本号字符串返回 None                |
| 4   | TestGetVersionFromOutput | test_returns_none_for_empty_string                   | 空字符串返回 None                      |
| 5   | TestRunCommandGetVersion | test_returns_stdout_on_success                       | 命令成功时返回 stdout                  |
| 6   | TestRunCommandGetVersion | test_returns_none_on_nonzero_returncode              | 非零退出码返回 None                    |
| 7   | TestRunCommandGetVersion | test_returns_none_on_exception                       | 异常返回 None                          |
| 8   | TestCheckPythonVersion   | test_returns_true_for_python_3_10                    | Python 3.10 通过检查                   |
| 9   | TestCheckPythonVersion   | test_returns_false_for_python_2_7                    | Python 2.7 不通过                      |
| 10  | TestCheckPythonVersion   | test_returns_true_for_python_3_7_boundary            | Python 3.7 边界值通过                  |
| 11  | TestCheckPythonVersion   | test_returns_false_for_python_3_6                    | Python 3.6 不通过                      |
| 12  | TestCheckDependencies    | test_returns_true_when_all_importable                | 所有依赖可导入时通过                   |
| 13  | TestCheckDependencies    | test_returns_false_when_selenium_missing             | selenium 缺失时不通过                  |
| 14  | TestCheckChrome          | test_returns_true_when_chrome_found                  | Chrome 可执行文件存在                  |
| 15  | TestCheckChrome          | test_returns_false_when_no_chrome_found              | Chrome 不存在                          |
| 16  | TestCheckChromedriver    | test_returns_true_when_driver_found_via_exists       | ChromeDriver 通过 exists 找到          |
| 17  | TestCheckChromedriver    | test_returns_true_when_driver_found_via_islink       | ChromeDriver 通过 islink 找到          |
| 18  | TestCheckChromedriver    | test_returns_false_when_no_driver_found              | ChromeDriver 不存在                    |
| 19  | TestCheckVersionMatch    | test_returns_true_when_versions_match                | Chrome 和 ChromeDriver 版本匹配        |
| 20  | TestCheckVersionMatch    | test_returns_false_when_versions_mismatch            | 版本不匹配                             |
| 21  | TestCheckVersionMatch    | test_returns_false_when_chrome_not_found             | Chrome 未安装                          |
| 22  | TestGetChromedriverPath  | test_returns_matching_driver_path                    | 返回匹配的 ChromeDriver 路径           |
| 23  | TestGetChromedriverPath  | test_raises_when_chrome_not_found                    | Chrome 不存在时抛出 RuntimeError       |
| 24  | TestGetChromedriverPath  | test_raises_when_chrome_version_undetectable         | 版本检测失败时抛出 RuntimeError        |
| 25  | TestCheckConfigFile      | test_returns_true_for_valid_config                   | 合法配置文件通过                       |
| 26  | TestCheckConfigFile      | test_returns_false_when_config_missing               | 配置文件不存在                         |
| 27  | TestCheckConfigFile      | test_returns_false_when_required_fields_missing      | 缺少必需字段                           |
| 28  | TestCheckConfigFile      | test_returns_false_for_invalid_json                  | 无效 JSON                              |
| 29  | TestMain                 | test_returns_zero_when_all_checks_pass               | 全部检查通过返回 0                     |
| 30  | TestMain                 | test_returns_one_when_any_check_fails                | 任一检查失败返回 1                     |

---

## 4. Web 模块 — Concert (`tests/unit/test_web_concert.py`)

核心自动化模块，覆盖完整购票流程。

### 4.1 生命周期

| #   | 测试类        | 测试方法                               | 说明                          |
| --- | ------------- | -------------------------------------- | ----------------------------- |
| 1   | TestLifecycle | test_init_creates_driver_status_0      | 构造成功，初始 status=0       |
| 2   | TestLifecycle | test_init_chromedriver_not_found_exits | ChromeDriver 不存在时 exit(1) |
| 3   | TestLifecycle | test_finish_quits_driver               | finish() 调用 driver.quit()   |

### 4.2 认证流程

| #   | 测试类       | 测试方法                                     | 说明                                |
| --- | ------------ | -------------------------------------------- | ----------------------------------- |
| 4   | TestAuthFlow | test_login_cookie_no_file_calls_set_cookie   | 无 cookie 文件 → 调用 set_cookie    |
| 5   | TestAuthFlow | test_login_cookie_with_file_calls_get_cookie | 有 cookie 文件 → 调用 get_cookie    |
| 6   | TestAuthFlow | test_get_cookie_loads_and_adds_cookies       | 读取 pickle 并添加 cookie 到 driver |
| 7   | TestAuthFlow | test_get_cookie_handles_exception            | pickle 读取异常不传播               |

### 4.3 set_cookie

| #   | 测试类        | 测试方法                       | 说明                           |
| --- | ------------- | ------------------------------ | ------------------------------ |
| 8   | TestSetCookie | test_set_cookie_writes_cookies | 模拟标题变化，验证 cookie 写入 |

### 4.4 登录

| #   | 测试类    | 测试方法                            | 说明                        |
| --- | --------- | ----------------------------------- | --------------------------- |
| 9   | TestLogin | test_login_method_0_opens_login_url | login_method=0 时打开登录页 |

### 4.5 导航

| #   | 测试类         | 测试方法                         | 说明                 |
| --- | -------------- | -------------------------------- | -------------------- |
| 10  | TestNavigation | test_enter_concert_sets_status_2 | 登录后 status 设为 2 |
| 11  | TestNavigation | test_is_element_exist_true       | 元素存在返回 True    |
| 12  | TestNavigation | test_is_element_exist_false      | 元素不存在返回 False |

### 4.6 选票 (choose_ticket)

| #   | 测试类           | 测试方法                                      | 说明                |
| --- | ---------------- | --------------------------------------------- | ------------------- |
| 13  | TestChooseTicket | test_choose_ticket_status_not_2_returns_early | status≠2 时直接返回 |
| 14  | TestChooseTicket | test_choose_ticket_detects_mobile_url         | 检测移动端 URL      |
| 15  | TestChooseTicket | test_choose_ticket_detects_pc_url             | 检测 PC 端 URL      |

### 4.7 选票轮询

| #   | 测试类                  | 测试方法                                 | 说明                               |
| --- | ----------------------- | ---------------------------------------- | ---------------------------------- |
| 16  | TestChooseTicketPolling | test_choose_ticket_clicks_buy_button     | "立即预订" 按钮点击，status→3      |
| 17  | TestChooseTicketPolling | test_choose_ticket_refreshes_on_sold_out | "提交缺货登记" → 刷新页面          |
| 18  | TestChooseTicketPolling | test_choose_ticket_calls_choice_seat     | "选座购买" 标题 → 调用 choice_seat |
| 19  | TestChooseTicketPolling | test_choose_ticket_by_link               | "不，立即预订" 链接点击            |

### 4.8 选座

| #   | 测试类         | 测试方法                                  | 说明                           |
| --- | -------------- | ----------------------------------------- | ------------------------------ |
| 20  | TestChoiceSeat | test_choice_seat_exits_when_title_changes | 标题不是 "选座购买" 时立即退出 |

### 4.9 选择订单

| #   | 测试类          | 测试方法                                        | 说明                       |
| --- | --------------- | ----------------------------------------------- | -------------------------- |
| 21  | TestChoiceOrder | test_choice_order_selects_dates_prices_quantity | 选择场次、票价、数量、确认 |

### 4.10 选项匹配 (\_select_option_by_config)

| #   | 测试类                     | 测试方法                                  | 说明                 |
| --- | -------------------------- | ----------------------------------------- | -------------------- |
| 22  | TestSelectOptionByConfig   | test_select_option_by_config_match_found  | 匹配成功并点击       |
| 23  | TestSelectOptionByConfig   | test_select_option_by_config_skip_soldout | 跳过含 "无票" 的选项 |
| 24  | TestSelectOptionByConfig   | test_select_option_by_config_no_match     | 无匹配返回 False     |
| 25  | TestSelectOptionByConfig   | test_select_option_by_config_empty_lists  | 空列表返回 False     |
| 26  | TestSelectOptionAdditional | test_select_option_exception_in_element   | 元素异常被安全跳过   |

### 4.11 用户选择 — 扫描

| #   | 测试类            | 测试方法                                 | 说明                    |
| --- | ----------------- | ---------------------------------------- | ----------------------- |
| 27  | TestUserSelection | test_scan_user_elements_found            | 找到用户元素返回 True   |
| 28  | TestUserSelection | test_scan_user_elements_all_retries_fail | 重试耗尽返回 False      |
| 29  | TestUserSelection | test_select_users_tries_methods          | \_select_users 遍历方法 |
| 30  | TestUserSelection | test_select_users_stops_at_ticket_count  | 选够人数后跳过后续用户  |

### 4.12 用户选择 — 方法 1-4

| #   | 测试类                   | 测试方法                                          | 说明                          |
| --- | ------------------------ | ------------------------------------------------- | ----------------------------- |
| 31  | TestUserSelectionMethods | test_method1_finds_div_and_clicks_checkbox        | 方法1: 找到 div 并点击复选框  |
| 32  | TestUserSelectionMethods | test_method1_no_div_found                         | 方法1: 未找到 div             |
| 33  | TestUserSelectionMethods | test_method1_clicks_div_directly_when_no_checkbox | 方法1: 无复选框时直接点击 div |
| 34  | TestUserSelectionMethods | test_method1_skip_when_enough_selected            | 方法1: 已选够跳过             |
| 35  | TestUserSelectionMethods | test_method1_scroll_fallback                      | 方法1: 点击失败→滚动后重试    |
| 36  | TestUserSelectionMethods | test_method2_label_match                          | 方法2: 通过 label 匹配复选框  |
| 37  | TestUserSelectionMethods | test_method2_checkbox_nearby_text                 | 方法2: 通过复选框附近文本匹配 |
| 38  | TestUserSelectionMethods | test_method2_skip_when_enough                     | 方法2: 已选够跳过             |
| 39  | TestUserSelectionMethods | test_method3_clicks_matching_element              | 方法3: 点击匹配元素           |
| 40  | TestUserSelectionMethods | test_method3_no_match                             | 方法3: 无匹配                 |
| 41  | TestUserSelectionMethods | test_method3_skip_when_enough                     | 方法3: 已选够跳过             |
| 42  | TestUserSelectionMethods | test_method4_js_click                             | 方法4: JavaScript 查找并点击  |
| 43  | TestUserSelectionMethods | test_method4_no_divs_found                        | 方法4: JS 未找到 div          |
| 44  | TestUserSelectionMethods | test_method4_skip_when_enough                     | 方法4: 已选够跳过             |

### 4.13 用户选择 — 编排器

| #   | 测试类                      | 测试方法                                | 说明                 |
| --- | --------------------------- | --------------------------------------- | -------------------- |
| 45  | TestSelectUsersOrchestrator | test_select_users_falls_through_methods | 方法1失败→尝试方法2  |
| 46  | TestSelectUsersOrchestrator | test_select_users_all_methods_fail      | 所有方法失败打印警告 |
| 47  | TestSelectUsersOrchestrator | test_select_users_multiple_users        | 依次选择多个用户     |

### 4.14 订单提交

| #   | 测试类              | 测试方法                                  | 说明                            |
| --- | ------------------- | ----------------------------------------- | ------------------------------- |
| 48  | TestOrderSubmission | test_submit_order_by_text_success         | 文本匹配成功提交                |
| 49  | TestOrderSubmission | test_submit_order_all_methods_fail        | 所有方法失败不抛异常            |
| 50  | TestSubmitMethods   | test_try_submit_by_text_exact_match       | 精确匹配 span 路径              |
| 51  | TestSubmitMethods   | test_try_submit_by_text_all_fail          | 文本匹配全部失败                |
| 52  | TestSubmitMethods   | test_try_submit_by_view_name_success      | view-name 属性匹配成功          |
| 53  | TestSubmitMethods   | test_try_submit_by_view_name_fail         | view-name 匹配失败              |
| 54  | TestSubmitMethods   | test_try_submit_by_class_success          | class 名匹配成功                |
| 55  | TestSubmitMethods   | test_try_submit_by_class_all_fail         | class 名全部失败                |
| 56  | TestSubmitMethods   | test_try_submit_by_original_xpath_success | 原有 XPath 成功                 |
| 57  | TestSubmitMethods   | test_try_submit_by_original_xpath_fail    | 原有 XPath 失败                 |
| 58  | TestSubmitMethods   | test_submit_order_tries_all_methods       | \_submit_order 链式尝试所有方法 |

### 4.15 确认订单 (commit_order)

| #   | 测试类                  | 测试方法                                       | 说明                         |
| --- | ----------------------- | ---------------------------------------------- | ---------------------------- |
| 59  | TestCommitOrder         | test_commit_order_status_not_3_returns         | status≠3 直接返回            |
| 60  | TestCommitOrder         | test_commit_order_selects_users_and_submits    | 正常模式：选择用户后提交     |
| 61  | TestCommitOrder         | test_commit_order_skip_submit_when_disabled    | if_commit_order=False 不提交 |
| 62  | TestCommitOrderDetailed | test_commit_order_fast_mode_uses_webdriverwait | 快速模式使用显式等待         |
| 63  | TestCommitOrderDetailed | test_commit_order_exception_in_user_selection  | 用户选择异常被捕获           |
| 64  | TestCommitOrderDetailed | test_commit_order_normal_mode_scans_page       | 正常模式扫描页面信息         |

### 4.16 PC 端平台选择

| #   | 测试类                 | 测试方法                                               | 说明                    |
| --- | ---------------------- | ------------------------------------------------------ | ----------------------- |
| 65  | TestPlatformPC         | test_select_city_on_page_pc_match                      | 城市匹配成功            |
| 66  | TestPlatformPC         | test_select_date_on_page_pc_match                      | 场次匹配成功            |
| 67  | TestPlatformPC         | test_select_price_on_page_pc_match                     | 票价匹配成功            |
| 68  | TestPlatformPC         | test_select_quantity_by_buttons                        | + 按钮点击正确次数      |
| 69  | TestPlatformPC         | test_select_quantity_always_returns_true               | 无选择器时不阻塞流程    |
| 70  | TestPlatformPC         | test_select_details_page_pc                            | PC 详情页完整流程       |
| 71  | TestPlatformPCDetailed | test_select_city_on_page_pc_no_match                   | 城市无匹配→回退文本搜索 |
| 72  | TestPlatformPCDetailed | test_select_city_on_page_pc_exception                  | 城市选择异常返回 False  |
| 73  | TestPlatformPCDetailed | test_select_date_on_page_pc_no_match_uses_text_search  | 场次无匹配→文本搜索     |
| 74  | TestPlatformPCDetailed | test_select_date_on_page_pc_exception                  | 场次选择异常返回 False  |
| 75  | TestPlatformPCDetailed | test_select_price_on_page_pc_no_match_uses_text_search | 票价无匹配→文本搜索     |
| 76  | TestPlatformPCDetailed | test_select_price_on_page_pc_exception                 | 票价选择异常返回 False  |
| 77  | TestPlatformPCDetailed | test_select_details_page_pc_normal_mode                | 非快速模式含页面扫描    |

### 4.17 移动端平台选择

| #   | 测试类                     | 测试方法                                    | 说明                 |
| --- | -------------------------- | ------------------------------------------- | -------------------- |
| 78  | TestPlatformMobile         | test_select_city_on_page_mobile             | 城市选择（移动端）   |
| 79  | TestPlatformMobile         | test_select_date_on_page_mobile             | 场次选择（移动端）   |
| 80  | TestPlatformMobile         | test_select_price_on_page_mobile            | 票价选择（移动端）   |
| 81  | TestPlatformMobile         | test_select_details_page_mobile             | 移动端详情页完整流程 |
| 82  | TestPlatformMobileDetailed | test_select_date_on_page_no_match           | 场次无匹配           |
| 83  | TestPlatformMobileDetailed | test_select_date_on_page_exception          | 场次异常             |
| 84  | TestPlatformMobileDetailed | test_select_price_on_page_no_match          | 票价无匹配           |
| 85  | TestPlatformMobileDetailed | test_select_city_on_page_exception          | 城市异常             |
| 86  | TestPlatformMobileDetailed | test_select_details_page_mobile_normal_mode | 非快速模式           |
| 87  | TestPlatformMobileDetailed | test_select_quantity_on_page_mobile         | 移动端数量选择       |
| 88  | TestPlatformMobileDetailed | test_select_quantity_on_page_pc_alias       | PC 端数量选择别名    |

### 4.18 数量选择

| #   | 测试类               | 测试方法                                         | 说明                          |
| --- | -------------------- | ------------------------------------------------ | ----------------------------- |
| 89  | TestQuantityDetailed | test_try_set_quantity_directly_success           | 直接设置输入框值成功          |
| 90  | TestQuantityDetailed | test_try_set_quantity_directly_not_found         | 输入框不存在                  |
| 91  | TestQuantityDetailed | test_get_quantity_input_value_found              | 获取输入框值                  |
| 92  | TestQuantityDetailed | test_get_quantity_input_value_not_found          | 输入框不存在返回 None         |
| 93  | TestQuantityDetailed | test_click_plus_buttons_disabled_skipped         | 禁用按钮被跳过                |
| 94  | TestQuantityDetailed | test_select_quantity_on_page_attribute_error     | AttributeError 不阻塞流程     |
| 95  | TestQuantityDetailed | test_select_quantity_on_page_webdriver_exception | WebDriverException 不阻塞流程 |

### 4.19 页面扫描

| #   | 测试类               | 测试方法                              | 说明                        |
| --- | -------------------- | ------------------------------------- | --------------------------- |
| 96  | TestScanMethods      | test_scan_page_text_prints_body       | 打印页面文本                |
| 97  | TestScanMethods      | test_scan_page_text_empty_body        | 空页面显示警告              |
| 98  | TestScanMethods      | test_scan_page_text_exception         | 扫描异常被捕获              |
| 99  | TestScanMethods      | test_scan_elements_buttons            | 扫描按钮元素                |
| 100 | TestScanMethods      | test_scan_elements_inputs             | 扫描输入框元素              |
| 101 | TestScanMethods      | test_scan_elements_empty              | 无元素显示提示              |
| 102 | TestScanMethods      | test_scan_submit_buttons_found        | 找到提交按钮                |
| 103 | TestScanMethods      | test_scan_submit_buttons_none         | 未找到提交按钮              |
| 104 | TestScanPageElements | test_scan_elements_by_class_found     | 按 class 扫描找到元素       |
| 105 | TestScanPageElements | test_scan_elements_by_class_not_found | 按 class 扫描未找到         |
| 106 | TestScanPageElements | test_scan_page_elements_runs          | scan_page_elements 完整执行 |

### 4.20 工具方法

| #   | 测试类      | 测试方法                                         | 说明                       |
| --- | ----------- | ------------------------------------------------ | -------------------------- |
| 107 | TestHelpers | test_click_element_by_text_found                 | 按文本查找并点击成功       |
| 108 | TestHelpers | test_click_element_by_text_not_found             | 按文本查找失败             |
| 109 | TestHelpers | test_find_and_click_element_success              | 查找并点击成功             |
| 110 | TestHelpers | test_find_and_click_element_skip_keywords        | 跳过含关键词的元素         |
| 111 | TestHelpers | test_scan_page_info                              | 打印页面 URL 和标题        |
| 112 | TestHelpers | test_get_wait_time_fast_mode                     | 快速模式等待时间           |
| 113 | TestHelpers | test_get_wait_time_normal_mode                   | 正常模式等待时间           |
| 114 | TestHelpers | test_get_element_text_safe_returns_text          | 安全获取元素文本           |
| 115 | TestHelpers | test_get_element_text_safe_returns_none_on_empty | 无元素返回 None            |
| 116 | TestHelpers | test_click_element_safe_success                  | 安全点击成功               |
| 117 | TestHelpers | test_click_element_safe_failure                  | 安全点击失败返回 False     |
| 118 | TestHelpers | test_is_order_confirmation_page_by_title         | 通过标题判断订单确认页     |
| 119 | TestHelpers | test_is_order_confirmation_page_false            | 非订单确认页               |
| 120 | TestHelpers | test_is_order_confirmation_page_by_body_text     | 通过页面文本判断订单确认页 |

---

## 5. Web 模块 — Damai 入口 (`tests/unit/test_web_damai.py`)

| #   | 测试类              | 测试方法                   | 说明                         |
| --- | ------------------- | -------------------------- | ---------------------------- |
| 1   | TestCheckConfigFile | test_missing_file_exits    | 配置文件缺失 → exit          |
| 2   | TestCheckConfigFile | test_valid_config          | 合法配置通过校验             |
| 3   | TestCheckConfigFile | test_missing_fields_exits  | 缺少必需字段 → exit          |
| 4   | TestCheckConfigFile | test_empty_users_exits     | users 为空 → exit            |
| 5   | TestCheckConfigFile | test_invalid_json_exits    | 无效 JSON → exit             |
| 6   | TestLoadConfig      | test_returns_config_object | 返回 Config 对象             |
| 7   | TestLoadConfig      | test_default_values        | 缺省值正确填充               |
| 8   | TestGrab            | test_full_flow             | 完整抢票流程（mock Concert） |
| 9   | TestGrab            | test_keyboard_interrupt    | 键盘中断安全退出             |
| 10  | TestGrab            | test_generic_exception     | 通用异常安全退出             |

---

## 6. Mobile 模块 — Config (`tests/unit/test_mobile_config.py`)

| #   | 测试类                     | 测试方法                               | 说明                      |
| --- | -------------------------- | -------------------------------------- | ------------------------- |
| 1   | TestStripJsoncComments     | test_strip_single_line_comments        | 移除 `//` 注释            |
| 2   | TestStripJsoncComments     | test_strip_multi_line_comments         | 移除 `/* */` 注释         |
| 3   | TestStripJsoncComments     | test_preserves_urls                    | 保留 URL 中的 `//`        |
| 4   | TestStripJsoncComments     | test_no_comments                       | 无注释文本不变            |
| 5   | TestMobileConfigInit       | test_config_init_stores_all_attributes | 8 个参数全部正确存储      |
| 6   | TestMobileConfigLoadConfig | test_load_config_success               | 正常读取 JSON 返回 Config |
| 7   | TestMobileConfigLoadConfig | test_load_config_file_not_found        | 文件不存在报友好错误      |
| 8   | TestMobileConfigLoadConfig | test_load_config_invalid_json          | JSON 格式错误             |
| 9   | TestMobileConfigLoadConfig | test_load_config_missing_keys          | 缺少必需字段              |
| 10  | TestMobileConfigLoadConfig | test_load_config_jsonc_with_comments   | JSONC 含注释正常解析      |

---

## 7. Mobile 模块 — DamaiApp (`tests/unit/test_mobile_damai_app.py`)

| #   | 测试类                | 测试方法                                              | 说明                        |
| --- | --------------------- | ----------------------------------------------------- | --------------------------- |
| 1   | TestInitialization    | test_init_loads_config_and_driver                     | 初始化加载配置和驱动        |
| 2   | TestInitialization    | test_setup_driver_sets_wait                           | 驱动设置 WebDriverWait      |
| 3   | TestUltraFastClick    | test_ultra_fast_click_success                         | 坐标点击成功                |
| 4   | TestUltraFastClick    | test_ultra_fast_click_timeout                         | 超时返回 False              |
| 5   | TestBatchClick        | test_batch_click_all_success                          | 批量点击全部成功            |
| 6   | TestBatchClick        | test_batch_click_some_fail                            | 部分点击失败                |
| 7   | TestUltraBatchClick   | test_ultra_batch_click_collects_and_clicks            | 收集坐标并快速点击          |
| 8   | TestUltraBatchClick   | test_ultra_batch_click_timeout_skips                  | 超时元素被跳过              |
| 9   | TestSmartWaitAndClick | test_smart_wait_and_click_primary_success             | 主选择器成功                |
| 10  | TestSmartWaitAndClick | test_smart_wait_and_click_backup_success              | 备用选择器成功              |
| 11  | TestSmartWaitAndClick | test_smart_wait_and_click_all_fail                    | 所有选择器失败              |
| 12  | TestSmartWaitAndClick | test_smart_wait_and_click_no_backups                  | 无备用选择器                |
| 13  | TestRunTicketGrabbing | test_run_ticket_grabbing_success                      | 完整流程成功                |
| 14  | TestRunTicketGrabbing | test_run_ticket_grabbing_city_fail                    | 城市选择失败 → False        |
| 15  | TestRunTicketGrabbing | test_run_ticket_grabbing_book_fail                    | 预约按钮失败 → False        |
| 16  | TestRunTicketGrabbing | test_run_ticket_grabbing_price_exception_tries_backup | 票价异常→备用方案           |
| 17  | TestRunTicketGrabbing | test_run_ticket_grabbing_exception_returns_false      | 全局异常返回 False          |
| 18  | TestRunTicketGrabbing | test_run_ticket_grabbing_submit_warns_on_failure      | 提交失败打印警告 (Bug 3)    |
| 19  | TestRunTicketGrabbing | test_run_ticket_grabbing_no_driver_quit_in_finally    | finally 不调用 quit (Bug 1) |
| 20  | TestRunWithRetry      | test_run_with_retry_success_first_attempt             | 首次尝试成功                |
| 21  | TestRunWithRetry      | test_run_with_retry_success_second_attempt            | 第二次尝试成功              |
| 22  | TestRunWithRetry      | test_run_with_retry_all_fail                          | 所有尝试失败                |
| 23  | TestRunWithRetry      | test_run_with_retry_driver_quit_between_retries       | 重试间重建驱动              |
| 24  | TestRunWithRetry      | test_run_with_retry_quit_exception_handled            | quit 异常被捕获 (Bug 2)     |

---

## 8. Web 集成测试 (`tests/integration/test_web_workflow.py`)

| #   | 测试类                         | 测试方法                                           | 说明                                     |
| --- | ------------------------------ | -------------------------------------------------- | ---------------------------------------- |
| 1   | TestConfigToConcertInit        | test_load_config_creates_concert                   | load_config → Config → Concert 链路      |
| 2   | TestEnterConcertToChooseTicket | test_enter_sets_status_2_then_choose_checks_status | enter_concert → status=2 → choose_ticket |
| 3   | TestOrderFlowPC                | test_pc_details_page_flow                          | PC 端完整详情页流程                      |
| 4   | TestOrderFlowMobile            | test_mobile_details_page_flow                      | 移动端完整详情页流程                     |

---

## 9. Mobile 集成测试 (`tests/integration/test_mobile_workflow.py`)

| #   | 测试类                        | 测试方法                     | 说明                                 |
| --- | ----------------------------- | ---------------------------- | ------------------------------------ |
| 1   | TestConfigToBotInit           | test_load_config_to_bot_init | Config.load_config → DamaiBot 初始化 |
| 2   | TestFullTicketGrabbingFlow    | test_all_phases_succeed      | 7 阶段完整流程（mock driver）        |
| 3   | TestRetryWithDriverRecreation | test_retry_recreates_driver  | 重试循环中驱动重建                   |

---

## 运行方式

```bash
# 运行全部测试（含覆盖率）
poetry run pytest -v

# 仅运行单元测试
poetry run pytest tests/unit/ -v

# 仅运行集成测试
poetry run pytest tests/integration/ -v

# 按 marker 运行
poetry run pytest -m unit -v
poetry run pytest -m integration -v

# 运行单个文件
poetry run pytest tests/unit/test_web_concert.py -v

# 运行单个测试
poetry run pytest -k "test_method1_finds_div" -v

# 生成覆盖率报告
poetry run pytest --cov-report=html    # HTML 报告在 htmlcov/
poetry run pytest --cov-report=term    # 终端输出
```

## 覆盖率目标

- 最低要求：**80%**（在 `pyproject.toml` 的 `--cov-fail-under=80` 中强制执行）
- 覆盖范围：`web/` 和 `mobile/` 目录
- 排除：`tests/`、`__init__.py`、`conftest.py`、`web/quick_diagnosis.py`
