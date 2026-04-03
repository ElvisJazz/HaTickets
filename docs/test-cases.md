# 测试用例说明文档

> 本文档记录项目所有自动化测试用例，按模块和类型分类。
> 最后更新：2026-03-27

## 概览

| 分类                     | 文件                                        | 用例数 |
| ------------------------ | ------------------------------------------- | ------ |
| 基础设施验证             | `tests/test_setup_validation.py`            | 14     |
| Mobile Config 单元测试   | `tests/unit/test_mobile_config.py`          | 10     |
| Mobile DamaiApp 单元测试 | `tests/unit/test_mobile_damai_app.py`       | 24     |
| Mobile 集成测试          | `tests/integration/test_mobile_workflow.py` | 7      |
| **合计**                 | **4 个文件**                                | **55** |

---

## 1. 基础设施验证 (`tests/test_setup_validation.py`)

验证测试框架本身是否正确配置。

| #   | 测试类                    | 测试方法                          | 说明                                     |
| --- | ------------------------- | --------------------------------- | ---------------------------------------- |
| 1   | TestInfrastructureSetup   | test_project_structure_exists     | 验证项目目录结构（mobile/、tests/）存在  |
| 2   | TestInfrastructureSetup   | test_pyproject_toml_exists        | 验证 pyproject.toml 存在且可解析         |
| 3   | TestInfrastructureSetup   | test_conftest_exists              | 验证 conftest.py 存在                    |
| 4   | TestInfrastructureSetup   | test_packages_importable          | 验证 mobile 包可以导入                   |
| 5   | TestInfrastructureSetup   | test_unit_marker_works            | 验证 pytest unit marker 正常工作         |
| 6   | TestInfrastructureSetup   | test_integration_marker_works     | 验证 pytest integration marker 正常工作  |
| 7   | TestInfrastructureSetup   | test_slow_marker_works            | 验证 pytest slow marker 正常工作         |
| 8   | TestFixturesAvailable     | test_temp_dir_fixture             | 验证 temp_dir fixture 返回有效临时目录   |
| 9   | TestFixturesAvailable     | test_mock_config_fixture          | 验证 mock_config fixture 返回字典        |
| 10  | TestFixturesAvailable     | test_mock_u2_driver_fixture       | 验证 mock_u2_driver fixture              |
| 12  | TestFixturesAvailable     | test_sample_html_response_fixture | 验证 HTML 响应 fixture                   |
| 13  | TestFixturesAvailable     | test_mock_time_fixture            | 验证时间 mock fixture                    |
| 14  | TestFixturesAvailable     | test_mock_file_operations_fixture | 验证文件操作 fixture                     |
| 15  | TestCoverageConfiguration | test_coverage_configured          | 验证覆盖率配置（源目录、排除规则、阈值） |
| 16  | (module)                  | test_pytest_can_discover_tests    | 验证 pytest 能发现测试用例               |

---

## 2. Mobile 模块 — Config (`tests/unit/test_mobile_config.py`)

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

## 3. Mobile 模块 — DamaiApp (`tests/unit/test_mobile_damai_app.py`)

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

## 4. Mobile 集成测试 (`tests/integration/test_mobile_workflow.py`)

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
poetry run pytest tests/unit/test_mobile_damai_app.py -v

# 运行单个测试
poetry run pytest -k "test_init_loads_config" -v

# 生成覆盖率报告
poetry run pytest --cov-report=html    # HTML 报告在 htmlcov/
poetry run pytest --cov-report=term    # 终端输出
```

## 覆盖率目标

- 最低要求：**80%**（在 `pyproject.toml` 的 `--cov-fail-under=80` 中强制执行）
- 覆盖范围：`mobile/` 目录
- 排除：`tests/`、`__init__.py`、`conftest.py`
