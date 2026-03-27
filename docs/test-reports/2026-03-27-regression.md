# 回归测试报告

- **日期**: 2026-03-27
- **测试环境**: macOS Darwin 25.3.0 / Python 3.14.3
- **测试框架**: pytest 8.x + pytest-cov 5.x
- **触发原因**: 首次全模块回归测试（Web + Mobile）

---

## 测试结果总览

| 指标 | 结果 |
|------|------|
| 总用例数 | 220 |
| 通过 | 220 |
| 失败 | 0 |
| 跳过 | 0 |
| 错误 | 0 |
| 执行时间 | 3.18s |
| 总覆盖率 | **81.64%** (目标 80% :white_check_mark:) |

---

## 模块覆盖率

| 模块 | 语句数 | 未覆盖 | 分支数 | 未覆盖分支 | 覆盖率 |
|------|--------|--------|--------|-----------|--------|
| web/damai.py | 63 | 2 | 6 | 0 | **97.10%** |
| mobile/damai_app.py | 148 | 15 | 36 | 3 | **89.13%** |
| web/check_environment.py | 195 | 17 | 60 | 10 | **88.63%** |
| web/concert.py | 1015 | 194 | 412 | 75 | **78.07%** |
| **合计** | **1467** | **228** | **516** | **88** | **81.64%** |

> mobile/config.py 和 web/config.py 已达到 100% 覆盖率（报告中 skip_covered）

---

## Bug 发现与修复

本次回归测试前的代码审查发现 6 个 Bug，全部已修复并有对应测试覆盖。

| # | 严重程度 | 模块 | 描述 | 修复文件 | 验证测试 |
|---|---------|------|------|----------|----------|
| 1 | HIGH | mobile | `run_ticket_grabbing()` finally 块中调用 `driver.quit()`，与 `run_with_retry()` 重复调用导致异常 | `mobile/damai_app.py` | `test_run_ticket_grabbing_no_driver_quit_in_finally` |
| 2 | MEDIUM | mobile | `run_with_retry()` 使用 bare `except:` 捕获所有异常（含 KeyboardInterrupt） | `mobile/damai_app.py` | `test_run_with_retry_quit_exception_handled` |
| 3 | LOW | mobile | `smart_wait_and_click` 提交订单返回值未检查，失败时无提示 | `mobile/damai_app.py` | `test_run_ticket_grabbing_submit_warns_on_failure` |
| 4 | MEDIUM | mobile | `Config.load_config()` 无错误处理，文件不存在或 JSON 解析失败时报错不友好 | `mobile/config.py` | `test_load_config_file_not_found`, `test_load_config_invalid_json`, `test_load_config_missing_keys` |
| 5 | HIGH | mobile | `config.jsonc` 使用 JSONC 格式（含 `//` 注释），但 `json.load()` 不支持注释解析 | `mobile/config.py` | `test_load_config_jsonc_with_comments` |
| 6 | LOW | tests | `test_setup_validation.py` 引用过时包名 `damai`/`damai_appium`（实际为 `web`/`mobile`） | `tests/test_setup_validation.py` | `test_packages_importable`, `test_coverage_configured` |

---

## 按模块测试分布

| 模块 | 单元测试 | 集成测试 | 合计 |
|------|---------|---------|------|
| 基础设施 | 17 | - | 17 |
| Web Config | 3 | - | 3 |
| Web Check Environment | 22 | - | 22 |
| Web Concert | 120 | - | 120 |
| Web Damai | 8 | - | 8 |
| Web 工作流 | - | 9 | 9 |
| Mobile Config | 10 | - | 10 |
| Mobile DamaiApp | 24 | - | 24 |
| Mobile 工作流 | - | 7 | 7 |
| **合计** | **204** | **16** | **220** |

---

## 未覆盖的主要区域

以下是 concert.py 中覆盖率低于 100% 的主要区域（不影响整体 80% 达标）：

| 区域 | 行数 | 原因 |
|------|------|------|
| `choice_seat()` 内部循环 | 251-257 | 需要模拟实时页面交互（选座场景） |
| `_try_select_user_method1` 部分分支 | 453-514 | 嵌套异常处理的极端边界路径 |
| `_try_select_user_method2` 部分分支 | 533-566 | 多层回退的极端路径 |
| `scan_page_elements()` 文本搜索 | 1143-1169 | 调试输出分支 |
| PC/Mobile 非快速模式详细输出 | 多处 | `fast_mode=False` 的打印分支 |

---

## 测试基础设施说明

- **Appium mock**: 测试环境未安装 appium，通过 `conftest.py` 中 `sys.modules` 注入完整 mock 层
- **sys.path 管理**: `web/` 目录加入 sys.path 以支持 bare import；`mobile/` 不加入以避免 Config 名称冲突
- **覆盖率排除**: `web/quick_diagnosis.py` 为诊断工具，不纳入覆盖率统计

---

## 结论

:white_check_mark: **回归测试通过** — 220 个测试全部通过，总覆盖率 81.64% 达到 80% 阈值。6 个已知 Bug 全部修复并有测试覆盖。

---

*报告生成时间: 2026-03-27*
