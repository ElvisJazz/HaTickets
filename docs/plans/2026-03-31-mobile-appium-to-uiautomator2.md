# 迁移计划：Mobile 模块 Appium → openatx/uiautomator2

## 背景与目标

**目标**：去掉 Appium Server（Node.js 进程）这一中间层，改用 `openatx/uiautomator2` 直连设备，降低每次操作的通信延迟，简化启动流程。

**收益**：
- 连接建立时间：~3s → ~0.5s（一次性，不影响热路径计时）
- 每次 find_element 少一层 HTTP relay（节省 10–30ms/次，热路径 ~20 次操作 → ~200–500ms）
- recovery 时间预计从 ~8.9s 降到 ~6–7s（元素查找密集）
- 不再依赖 Node.js / Appium Server 进程
- 无需先运行 `start_appium.sh`，消除常见"忘记启动服务"失败模式

**风控与虚拟机注意事项**：
- 底层仍使用 UIAutomator2 框架，检测向量与 Appium 相同；仅 APK 包名不同（`io.appium.uiautomator2.server` → `com.github.uiautomator`）
- 不要在 Android 模拟器上运行正式抢票：模拟器硬件指纹（`ro.hardware=goldfish`、x86 架构、Play Integrity 失败）极易被风控检测，可能导致静默失败
- 迁移本身不改变行为模式（坐标点击已是最优解），风控暴露面不增不减

**回滚保障**：通过 `driver_backend` 配置开关，任意阶段可切回 Appium。

---

## 关键架构洞察：热路径已是纯坐标操作

**迁移复杂度的核心结论**：当 `rush_mode=True` 且配置了 `sell_start_time` 时，`_prepare_detail_page_hot_path()` 在开售前已完成所有元素查找（日期/城市预选、票价坐标抓取），实际抢票热路径中**没有任何 container.find_elements() 调用**：

```
热路径实际步骤（全部为坐标操作或简单 ID 查找）：
1. 点击购票按钮 ← ID 查找或预缓存坐标
2. 按 price_index 坐标直击票价 ← 预缓存坐标，零元素查询
3. +号加数量 ← ID 查找 + clickGesture
4. 确定购买 ← 预缓存坐标 + burst_click
5. 勾选观演人 ← By.ID checkbox 列表 + get_attribute
6. 等待提交按钮 ← By.ID 轮询
```

`container.find_elements()` 的 7 处复杂调用全部在**冷路径**（价格探测、搜索结果解析、详情页文本读取）。这使得迁移可以**分两阶段**：先迁移热路径（低风险，可 benchmark 验证），再处理冷路径（复杂，可暂用 Appium 回退）。

---

## 当前代码状态（2026-03-31 代码审查，已同步最新改动）

迁移前必须了解的已有实现，迁移时不得破坏。

### `_setup_driver()` 当前配置

```python
def _setup_driver(self):
    self._preflight_validate_device_target()
    device_app_info = AppiumOptions()
    device_app_info.load_capabilities(self._build_capabilities())
    self.driver = webdriver.Remote(self.config.server_url, options=device_app_info)
    self.driver.update_settings({
        "waitForIdleTimeout": 0,
        "actionAcknowledgmentTimeout": 0,
        "keyInjectionDelay": 0,
        "waitForSelectorTimeout": 100,   # 已从 300 优化到 100ms
        "ignoreUnimportantViews": False,
        "allowInvisibleElements": True,
        "enableNotificationListener": False,
    })
    self.wait = WebDriverWait(self.driver, 2)
```

### `config.py` 已有 `update_runtime_mode()`

```python
def update_runtime_mode(probe_only, if_commit_order, config_path=None):
    """Update runtime mode flags in the target config file and persist them."""
```

由 `start_ticket_grabbing.sh` 调用用于在运行前自动回写配置。Step 2 新增字段时不得破坏此函数签名。

### `start_ticket_grabbing.sh` 已有 `--probe` 标志

脚本已实现命令语义固定：
- `./start_ticket_grabbing.sh --probe [--yes]`：安全探测（强制 probe_only=true, if_commit_order=false）
- `./start_ticket_grabbing.sh [--yes]`：正式抢票（强制 probe_only=false, if_commit_order=true）

配置与命令不一致时会自动提示并回写配置文件。**Step 6 只需去掉 Appium 检查，不需要重新设计此脚本。**

### `run_ticket_grabbing()` 的 `fast_validation_hot_path`

当同时满足以下条件时，跳过 `dismiss_startup_popups()` 和 `check_session_valid()`：
```python
fast_validation_hot_path = (
    config.rush_mode
    and not config.if_commit_order
    and initial_page_probe is not None
    and page_probe["state"] in {"detail_page", "sku_page"}
)
```

迁移后 `_setup_u2_driver()` 中的 `app_start(stop=False)` 只在初始化时执行一次，不影响此跳过逻辑。

### rush_mode 热路径坐标预缓存机制

`_prepare_detail_page_hot_path()` 在开售前调用，返回：
- `price_coords`：价格卡片坐标（来自 `_get_price_option_coordinates_by_config_index()`）
- `buy_button_coords`：购票按钮坐标

`_get_price_option_coordinates_by_config_index()` 内部使用 `container.find_element` + `container.find_elements`，但这在开售**前**执行，不在热路径计时范围内，迁移时需要处理但不影响热路径性能目标。

### `_ensure_attendees_selected_on_confirm_page()` rush 模式快速路径

```python
if self.config.rush_mode:
    # 极速模式：checkbox 存在即说明观演人区域可见，跳过额外的 UiSelector 文本查找
    if not checkbox_elements:
        return not require_attendee_section
    required_count = max(1, len(self.config.users or []))
else:
    attendee_section_visible = self._has_element(...)   # 额外查找
    required_count = self._attendee_required_count_on_confirm_page()  # 额外查找
```

### `_attendee_selected_count(use_source_fallback=True)` 新参数

```python
selected_count = self._attendee_selected_count(
    checkbox_elements,
    use_source_fallback=not self.config.rush_mode,
)
```

rush_mode 下传 `use_source_fallback=False`，跳过 `driver.page_source` XML 扫描（~300–500ms）。u2 中 `driver.page_source` 对应 `d.dump_hierarchy()`，行为相同，直接替换即可。

### `_click_attendee_checkbox_fast()` 低延迟路径

```python
def _click_attendee_checkbox_fast(self, checkbox):
    """Low-latency checkbox click path for rush-mode validation."""
    click_actions = [
        lambda: checkbox.click(),
        lambda: self._click_element_center(checkbox, duration=28),
    ]
```

u2 element 也支持 `.click()`，`_click_element_center` 经过 `_click_coordinates()` 适配层，迁移后自动生效。

### `burst_count` 行为

```python
burst_count = 1 if not self.config.if_commit_order else 2
```

验证模式单击购买按钮，正式提交模式双击。测试断言已更新为 `count=1`（validation 路径），迁移时不得恢复为 `count=2`。

### `_select_price_option_by_text_or_index()` 中的 `elementId` 用法

```python
self.driver.execute_script('mobile: clickGesture', {'elementId': target_price.id})
```

此处出现 **2 次**，是文本匹配失败后的备用路径。u2 无 WebDriver elementId 概念。迁移方案：改为获取元素 bounds 后用 `d.click(cx, cy)`。**注意**：rush_mode 下不会走这条路径（已使用预缓存坐标），故不影响热路径性能。

### `hot_path_benchmark.py` 已有 `StepTimelineRecorder`

benchmark 步骤级耗时采集依赖 logger 名称 `"mobile.damai_app"` / `"damai_app"`。迁移后此功能应继续正常工作，u2 版本中 logger 名称不变。

### 当前测试行为

- commit-disabled 路径：完成观演人勾选后返回 `True`（有意为之），迁移时不得回退
- `burst_click_coords` 断言已改为 `count=1`（validation 路径），不得恢复为 `count=2`
- 所有涉及提交流程的测试均已 mock `_ensure_attendees_selected_on_confirm_page`，迁移后新增测试保持此模式

---

## 架构变化

```
【当前架构】
Python (damai_app.py)
    ↓ HTTP (WebDriver Protocol)
Appium Server (Node.js :4723)    ← 要去掉的层
    ↓ JSON-RPC over HTTP
ATX Agent (Android device)
    ↓
UIAutomator2 Framework

【目标架构】
Python (damai_app.py)
    ↓ HTTP (JSON-RPC 直连)
ATX Agent (Android device)
    ↓
UIAutomator2 Framework
```

---

## 涉及文件

```
mobile/
├── damai_app.py              ← 主要改动（driver 初始化 + API 替换）
├── config.py                 ← server_url 变为可选，新增 serial/driver_backend 字段
├── config.jsonc              ← 更新字段（serial 替代 server_url，删 platform_version）
├── config.example.jsonc      ← 更新示例
└── scripts/
    ├── start_ticket_grabbing.sh  ← 仅去掉 Appium 检查，--probe 逻辑已有，不动
    └── start_appium.sh           ← 保留但注释标注已不需要

pyproject.toml                ← 依赖变更
tests/conftest.py             ← 新增 mock_u2_driver fixture（保留 mock_appium_driver）
tests/unit/test_mobile_config.py  ← 新增 serial/driver_backend 字段测试
```

---

## API 映射表

| 当前 Appium 调用 | uiautomator2 等价 | 备注 |
|---|---|---|
| `webdriver.Remote(url, options)` | `u2.connect(serial)` | serial=None 自动选第一台设备 |
| `driver.find_element(By.ID, "cn.damai:id/foo")` | `d(resourceId="cn.damai:id/foo")` | |
| `driver.find_elements(By.ID, "...")` | `list(d(resourceId="..."))` | |
| `driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("X")')` | `d(text="X")` | |
| `driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("X")')` | `d(textContains="X")` | |
| `driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches(".*X.*")')` | `d(textMatches=".*X.*")` | |
| `driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, '...className("X").clickable(true).instance(N)')` | `d(className="X", clickable=True, instance=N)` | |
| `driver.find_element(By.XPATH, '//*[@text="X"]')` | `d.xpath('//*[@text="X"]').get_element()` | |
| `driver.find_elements(By.CLASS_NAME, "android.widget.FrameLayout")` | `list(d(className="android.widget.FrameLayout"))` | |
| `container.find_elements(By.CLASS_NAME, "X")` | `list(container.child(className="X"))` | container 为 u2 selector，不是 element |
| `container.find_elements(By.ID, "cn.damai:id/foo")` | `list(container.child(resourceId="cn.damai:id/foo"))` | 同上 |
| `container.find_elements(By.XPATH, ".//*")` | `d.xpath(absolute_xpath + '//*').all()` | u2 不支持相对 XPath；需先获取容器绝对 XPath 或 bounds |
| `element.rect` → `{'x','y','width','height'}` | `el.info['bounds']` → `{'left','top','right','bottom'}` + `_element_rect()` 转换 | 见下方 |
| `element.text` | `el.get_text()` 或 `el.info['text']` | |
| `element.get_attribute("clickable")` | `el.info.get('clickable', False)` | 返回 bool，删除 `.lower() == "true"` 转换 |
| `element.get_attribute("checked")` | `el.info.get('checked', False)` | 同上，用于 checkbox 状态 |
| `execute_script("mobile: clickGesture", {"x":x,"y":y})` | `d.click(x, y)` | duration≤50 直接 click |
| `execute_script("mobile: clickGesture", {"elementId": el.id})` | 获取 `el.info['bounds']` 计算中心坐标，再 `d.click(cx, cy)` | u2 无 elementId 概念 |
| `execute_script("mobile: swipeGesture", {...})` | `d.swipe(fx, fy, tx, ty, duration)` | 参数格式不同，需换算 |
| `driver.current_activity` | `d.app_current()['activity']` | |
| `driver.update_settings({...})` | `d.settings[key] = value` | key 名称有差异，见下方 |
| `WebDriverWait(driver, t).until(EC.presence_of_element_located(...))` | `d(...).wait(timeout=t)` 返回 bool | |
| `driver.page_source` | `d.dump_hierarchy()` | 返回 XML 字符串，格式相同 |
| `driver.get_screenshot_as_file(path)` | `d.screenshot(path)` | |
| `driver.press_keycode(keycode)` | `d.press(keycode)` | |
| `driver.activate_app(package)` | `d.app_start(package, stop=False)` | |

### settings 映射

| Appium `update_settings` key | u2 等价 |
|---|---|
| `waitForIdleTimeout: 0` | `d.settings['wait_timeout'] = 0` |
| `waitForSelectorTimeout: 100` | 无直接等价；u2 默认每次 `.wait()` 超时由调用方传入，整体已足够激进 |
| `actionAcknowledgmentTimeout: 0` | 无直接等价，u2 默认已足够激进 |
| `keyInjectionDelay: 0` | `d.settings['key_injection_delay'] = 0` |
| `disableWindowAnimation: True` | 通过 `adb shell settings put global window_animation_scale 0` 等 adb 命令设置 |

---

## 实施步骤

### Step 1：依赖变更（`pyproject.toml`）

```toml
[tool.poetry.dependencies]
python = "^3.8"
selenium = ">=4.22.0,<4.28"   # 保留（Web 模块仍用 Selenium）
# 删除：appium-python-client = "^4.0.0"
uiautomator2 = "^3.2"         # 新增
adbutils = "^2.9"             # 新增（u2 依赖，显式声明）
```

**验证**：`poetry install && poetry run pytest` 仍通过（此时代码尚未改动，测试应全部通过）。

---

### Step 2：Config 字段变更（`config.py` + `config.jsonc`）

**`config.py` 的 `Config.__init__` 新增参数：**

```python
def __init__(self, ...,
             serial=None,              # 新增：设备序列号（替代 server_url 的角色）
             driver_backend="u2",      # 新增："u2" | "appium"
             server_url=None):         # 变为可选（driver_backend="appium" 时需要）
```

**`server_url` 校验逻辑改为条件校验：**
```python
if driver_backend == "appium":
    validate_url(server_url, "server_url")
```

**注意**：`update_runtime_mode()` 函数签名和行为不变，只是增量添加新字段的读取。

**`Config.load_config()` 新增字段读取：**
```python
return Config(...,
              config.get('serial'),
              config.get('driver_backend', 'u2'),
              config.get('server_url'))
```

**`config.jsonc` 新增/变更字段：**
```jsonc
{
  "serial": null,            // 新增：null = 自动检测；或填 "emulator-5554" / "c6c4eb67"
  "driver_backend": "u2",   // 新增：回滚开关，"u2"（默认）| "appium"
  // "server_url": "http://127.0.0.1:4723",  // 变为可选，driver_backend="appium" 时才需要
  // 删除 platform_version（u2 不需要）
}
```

**验证**：`poetry run pytest tests/unit/test_mobile_config.py`

---

### Step 3：新增 `_setup_u2_driver()`，保留 Appium 分支

在 `damai_app.py` 的 `_setup_driver()` 中添加分支：

```python
def _setup_driver(self):
    if getattr(self.config, 'driver_backend', 'u2') == 'appium':
        self._setup_appium_driver()
    else:
        self._setup_u2_driver()

def _setup_appium_driver(self):
    """原 _setup_driver() 逻辑，完整保留，改名。"""
    self._preflight_validate_device_target()
    device_app_info = AppiumOptions()
    device_app_info.load_capabilities(self._build_capabilities())
    self.driver = webdriver.Remote(self.config.server_url, options=device_app_info)
    self.driver.update_settings({
        "waitForIdleTimeout": 0,
        "actionAcknowledgmentTimeout": 0,
        "keyInjectionDelay": 0,
        "waitForSelectorTimeout": 100,   # 当前值，勿改回 300
        "ignoreUnimportantViews": False,
        "allowInvisibleElements": True,
        "enableNotificationListener": False,
    })
    self.wait = WebDriverWait(self.driver, 2)

def _setup_u2_driver(self):
    """uiautomator2 直连驱动初始化。"""
    import uiautomator2 as u2
    serial = getattr(self.config, 'serial', None) or self.config.udid or None
    self.d = u2.connect(serial)
    self.d.settings['wait_timeout'] = 0
    self.d.settings['operation_delay'] = (0, 0)
    self.d.app_start(
        self.config.app_package,
        activity=self.config.app_activity,
        stop=False,
    )
    # 兼容：令 self.driver 指向同一对象，避免其他 None 检查报错
    self.driver = self.d
```

**ATX Agent 自动升级风险**：`u2.connect()` 首次或版本不匹配时会触发设备端升级（需联网）。生产用途建议提前手动执行 `python -m uiautomator2 init`，并在 `_setup_u2_driver()` 注释说明。

**验证**：`driver_backend="appium"` 路径行为不变；`driver_backend="u2"` 可连通设备并启动 APP。

---

### Step 4：添加坐标/rect 适配方法

在 `DamaiBot` 中新增，替换所有 `element.rect` 直接访问（共 9 处）：

```python
def _element_rect(self, el):
    """统一返回 {'x', 'y', 'width', 'height'}，兼容 Appium 和 u2。"""
    if hasattr(el, 'rect'):
        return el.rect   # Appium element
    b = el.info['bounds']
    return {
        'x': b['left'],
        'y': b['top'],
        'width': b['right'] - b['left'],
        'height': b['bottom'] - b['top'],
    }
```

改写 `_click_coordinates()`：

```python
def _click_coordinates(self, x, y, duration=50):
    if getattr(self.config, 'driver_backend', 'u2') == 'appium':
        self.driver.execute_script(
            "mobile: clickGesture",
            {"x": x, "y": y, "duration": duration},
        )
    else:
        if duration <= 50:
            self.d.click(x, y)
        else:
            self.d.long_click(x, y, duration / 1000)
```

同时处理 `execute_script('mobile: clickGesture', {'elementId': el.id})` 的 2 处调用：

```python
# 原来（_select_price_option_by_text_or_index 中）
self.driver.execute_script('mobile: clickGesture', {'elementId': target_price.id})

# 改为（通用写法，兼容两端）
rect = self._element_rect(target_price)
cx = rect['x'] + rect['width'] // 2
cy = rect['y'] + rect['height'] // 2
self._click_coordinates(cx, cy, duration=30)
```

**验证**：坐标点击单元测试通过；rush_mode burst_click 行为不变；`burst_count=1`（validation）断言不变。

---

### Step 5a：迁移简单 find_element 调用（热路径 + 无 container 的冷路径）

#### 新增统一查找辅助方法

```python
def _find(self, by, value):
    """统一查找入口，返回 u2 selector 或 Appium element。"""
    if getattr(self.config, 'driver_backend', 'u2') != 'u2':
        return self.driver.find_element(by, value)
    return self._appium_selector_to_u2(by, value)

def _find_all(self, by, value):
    """返回元素列表（u2 或 Appium）。"""
    if getattr(self.config, 'driver_backend', 'u2') != 'u2':
        return self.driver.find_elements(by=by, value=value)
    return list(self._appium_selector_to_u2(by, value))

def _appium_selector_to_u2(self, by, value):
    """将 (by, value) 对转换为 u2 selector。"""
    from selenium.webdriver.common.by import By
    try:
        from appium.webdriver.common.appiumby import AppiumBy
        UIAUTOMATOR = AppiumBy.ANDROID_UIAUTOMATOR
    except ImportError:
        UIAUTOMATOR = "android uiautomator"

    if by == By.ID:
        return self.d(resourceId=value)
    if by == By.CLASS_NAME:
        return self.d(className=value)
    if by == By.XPATH:
        return self.d.xpath(value)
    if by == UIAUTOMATOR:
        return self._parse_uiselector(value)
    raise ValueError(f"不支持的 by 类型: {by}")

def _parse_uiselector(self, uiselector_str):
    """将常见的 UiSelector 字符串解析为 u2 selector kwargs。"""
    import re
    kwargs = {}
    for pattern, key in [
        (r'\.text\("([^"]+)"\)', 'text'),
        (r'\.textContains\("([^"]+)"\)', 'textContains'),
        (r'\.textMatches\("([^"]+)"\)', 'textMatches'),
        (r'\.className\("([^"]+)"\)', 'className'),
    ]:
        m = re.search(pattern, uiselector_str)
        if m:
            kwargs[key] = m.group(1)
    m = re.search(r'\.clickable\((true|false)\)', uiselector_str)
    if m:
        kwargs['clickable'] = (m.group(1) == 'true')
    m = re.search(r'\.instance\((\d+)\)', uiselector_str)
    if m:
        kwargs['instance'] = int(m.group(1))
    if not kwargs:
        raise ValueError(f"无法解析 UiSelector: {uiselector_str}")
    return self.d(**kwargs)
```

#### `_has_element()` 改写

```python
def _has_element(self, by, value):
    try:
        if getattr(self.config, 'driver_backend', 'u2') != 'u2':
            return len(self.driver.find_elements(by=by, value=value)) > 0
        return self._find(by, value).exists(timeout=0)
    except Exception:
        return False
```

#### 本步骤替换范围（15 处，无 container 子查找）

以下调用可以安全替换为 `_find()` / `_find_all()`：
- `driver.find_elements(By.ID, "cn.damai:id/checkbox")` ← 3 处
- `driver.find_elements(By.ID, "cn.damai:id/ll_search_item")` ← 2 处
- `driver.find_elements(By.ID, "cn.damai:id/tv_date")` ← 1 处
- `driver.find_element(By.ID, "img_jia")` / `driver.find_elements(By.ID, "layout_num")` ← 2 处
- `driver.find_element(By.ID, "btn_buy_view")` ← 1 处
- `driver.find_element(By.ID, "cn.damai:id/trade_project_detail_purchase_status_bar_container_fl")` ← 1 处（`hot_path_benchmark.py` 快速检测）
- UiSelector 文本查找（`_attendee_required_count`、`dismiss_startup_popups`、城市/日期选择）← 其余

`get_attribute("clickable")` / `get_attribute("checked")` 改写（共 4 处）：
```python
# 改为（u2 的 info 直接是 bool，删除 .lower() == "true" 转换）
el.info.get('clickable', False)
el.info.get('checked', False)
```

**验证**：设备上完整跑一遍 `--probe` 模式；`benchmark_hot_path.sh --runs 3` 耗时与迁移前相比不退步；`StepTimelineRecorder` 日志正常输出。

---

### Step 5b：迁移 container 子查找（冷路径，可延后）

这是改动最复杂的部分，涉及 7 处 `container.find_elements()` 和 3 个辅助方法。

**受影响的方法**：
- `_get_price_option_coordinates_by_config_index()` — `price_container.find_element()` + `price_container.find_elements()`
- `_click_visible_price_option()` — `price_container.find_elements()`
- `get_visible_price_options()` — `price_container.find_elements()`
- `_safe_element_text(container, by, value)` — `container.find_elements()`，container 可能是 element（搜索结果卡片、价格卡片）
- `_safe_element_texts(container, by, value)` — 同上
- `_collect_descendant_texts(container)` — `container.find_elements(By.XPATH, ".//*")`，container 是 element

**迁移策略**：

对于 `container.find_elements(By.CLASS_NAME/By.ID, ...)` ← u2 有 `.child()` API：
```python
# 原来
cards = price_container.find_elements(By.CLASS_NAME, "android.widget.FrameLayout")
# 改为（price_container 是 u2 selector，不是 element）
cards = list(price_container.child(className="android.widget.FrameLayout"))
```

对于 `container.find_elements(By.XPATH, ".//*")` ← u2 不支持相对 XPath，两种方案：
```python
# 方案 A：从容器 bounds 构造绝对 XPath（较脆，依赖坐标稳定）
bounds = container.info['bounds']
cards = d.xpath(f'//node[@bounds="{bounds_str}"]/*').all()

# 方案 B（推荐）：直接用 dump_hierarchy() 解析容器 ID 下的子树
# 结构与 page_source 相同，可用 ElementTree 解析
```

对于 `_safe_element_text(card, By.ID, resource_id)` 中 `card` 是搜索结果 element 的情况：
- 改为先获取 card 的 bounds，用 `d(resourceId=resource_id).within(bounds)` 或直接绝对路径查找

**验证**：`get_visible_price_options()` 返回结果与 Appium 版一致；搜索结果评分测试通过。

---

### Step 6：更新 `start_ticket_grabbing.sh`

仅删除 Appium 检查段，其余逻辑完整保留：

```bash
# 删除（约 5 行）：
if ! curl -s http://127.0.0.1:4723/status > /dev/null; then
    echo "❌ Appium服务器未运行"
    exit 1
fi

# 新增 adb 设备检查：
if ! adb devices 2>/dev/null | grep -q "device$"; then
    echo "❌ 未检测到已连接的 Android 设备"
    echo "   请通过 USB 连接设备并开启 USB 调试模式"
    exit 1
fi
echo "✅ 设备连接正常"
```

**验证**：`./start_ticket_grabbing.sh --probe --yes` 不再提示"Appium未运行"。

---

### Step 7：切换默认值 + 更新测试

1. 确认 `config.py` 中 `driver_backend` 默认值为 `"u2"`
2. `config.example.jsonc`：注释 `server_url`、删除 `platform_version`、新增 `serial: null`
3. **新增** `tests/conftest.py` fixture：

```python
@pytest.fixture
def mock_u2_driver(mocker):
    mock_d = MagicMock()
    mock_d.app_current.return_value = {
        'activity': '.launcher.splash.SplashMainActivity',
        'package': 'cn.damai',
    }
    mock_d.settings = {}
    mock_d.xpath.return_value = MagicMock()
    mocker.patch("uiautomator2.connect", return_value=mock_d)
    return mock_d

# 保留原 mock_appium_driver fixture（driver_backend="appium" 回滚路径仍需要）
```

4. `tests/unit/test_mobile_config.py` 新增：
   - `serial` 字段：null / 字符串校验
   - `driver_backend` 字段：`"u2"` / `"appium"` 合法；其他值抛 ValueError
   - `server_url` 在 `driver_backend="u2"` 时可为 None，在 `driver_backend="appium"` 时必须合法 URL
   - 已有 `test_update_runtime_mode_*` 测试无需改动

5. `tests/unit/test_mobile_damai_app.py` 注意事项：
   - commit-disabled 测试当前预期返回 `True`（已更新），不得回退
   - `_setup_driver` mock 需同时覆盖 Appium 和 u2 两条路径
   - `burst_click_coords` 断言已改为 `count=1`，不得恢复

**验证**：`poetry run pytest --cov-fail-under=80` 通过。

---

### Step 8：清理（观察稳定 1 周后）

1. 删除 `_setup_appium_driver()` 及所有 `driver_backend == "appium"` 分支
2. 删除 `_appium_selector_to_u2()` 中的 Appium import 和兼容逻辑
3. `pyproject.toml` 彻底删除 `appium-python-client`
4. `config.py` 移除 `server_url` / `platform_version` 字段及其校验
5. `config.jsonc` / `config.example.jsonc` 删除注释掉的 `server_url` 行
6. 归档 `start_appium.sh`（重命名为 `start_appium.sh.deprecated` 或直接删除）
7. `conftest.py` 删除 `mock_appium_driver` fixture

---

## 改动量估算

| 文件 | 预计净改动行数 | 主要内容 |
|---|---|---|
| `damai_app.py` | ~150–200 行 | Step 3–5：driver 初始化分支、`_element_rect`、`_find`/`_find_all`、API 替换 |
| `config.py` | ~20 行 | Step 2：新增 2 字段，条件校验 |
| `conftest.py` | ~30 行 | Step 7：新增 `mock_u2_driver` fixture |
| `test_mobile_damai_app.py` | ~150–200 行 | Step 7：新增 u2 路径测试 |
| `test_mobile_config.py` | ~40 行 | Step 7：新增字段测试 |
| `pyproject.toml` | ~3 行 | Step 1：依赖变更 |
| shell 脚本 | ~10 行 | Step 6：替换 Appium 检查 |
| **合计** | **~400–500 行** | 瓶颈在 Step 5b 的 container 查找重构 |

---

## 验证检查点（每步完成后执行）

```bash
# 单元测试（无需设备）
poetry run pytest tests/unit/ -v

# 全量测试 + 覆盖率
poetry run pytest --cov-fail-under=80

# 设备冒烟测试（需真机）
./mobile/scripts/start_ticket_grabbing.sh --probe --yes

# 热路径 benchmark（需真机停在演出详情页）
./mobile/scripts/benchmark_hot_path.sh --runs 3
```

---

## 风险点与缓解

| 风险 | 影响范围 | 缓解措施 |
|---|---|---|
| `container.find_elements(By.XPATH, ".//*")` 在 u2 中不支持 | `_collect_descendant_texts()`（冷路径：价格文本读取、详情页标题）| Step 5b 改用 `dump_hierarchy()` 解析；冷路径可先用 `driver_backend="appium"` 回退 |
| `container.child()` 行为与 Appium 子查找不完全一致 | 价格卡片 clickable 过滤逻辑 | 逐一验证 `_get_price_option_coordinates_by_config_index()` 返回坐标正确 |
| UiSelector 复杂表达式解析不完整 | `_parse_uiselector()` 漏掉某些组合 | 遇到 ValueError 时逐一补充；提供明确异常信息；当前已覆盖所有实际用到的模式 |
| `get_attribute("clickable"/"checked")` 返回类型变化 | 价格卡片过滤、checkbox 状态读取 | 改为 `el.info.get('clickable/checked', False)`，直接用 bool，删 `.lower()` 转换 |
| ATX Agent 在连接时自动升级 | 首次 `u2.connect()` 可能触发设备端安装/升级（需联网） | 生产前手动 `python -m uiautomator2 init`；在 `_setup_u2_driver()` 中注释说明 |
| rush_mode 热路径行为改变 | 抢票成功率敏感 | Step 5a 完成后必须跑 `benchmark_hot_path.sh`，对比迁移前后耗时；不得在热路径引入新等待 |
| `StepTimelineRecorder` 依赖 logger 名称 | benchmark 步骤计时失效 | u2 版本的 logger 名称需与 `"mobile.damai_app"` / `"damai_app"` 保持一致 |
| `burst_count = 1`（validation 模式）被意外恢复 | 测试断言失败 + 开发验证路径双击提交 | 测试已有 `count=1` 断言保护；code review 时重点检查 |
| `_select_price_option_by_text_or_index()` 的 elementId 调用 | 文本匹配失败的备用路径 | Step 4 中统一改为 bounds 坐标点击；rush_mode 不走此路径，不影响热路径 |
| 模拟器硬件指纹被风控检测 | 正式抢票静默失败 | 迁移全程在真机上验证；benchmark 数据只信真机数据 |

---

## Agent Team 分工方案

### 编排概览

六个 Agent 分三波并行推进，每波结束前须通过验证检查点方可解锁下一波。

```
Wave 1 ──────────────────────────────────────────────
  Agent A  Infrastructure & Config
           (pyproject.toml / config.py / shell script)

Wave 2 ──────────────────────────────────────────────  (A 完成后解锁)
  Agent B  Driver Adapter Layer
           (_setup_driver split / _element_rect / _click_coordinates)
  Agent F1 Config Tests                               (可与 B 并行)
           (test_mobile_config.py new fields)

Wave 3 ──────────────────────────────────────────────  (B 完成后解锁)
  Agent C  Selector Adapter Layer
           (_find / _find_all / _parse_uiselector / _has_element)

Wave 4 ──────────────────────────────────────────────  (C 完成后解锁)
  Agent D  Hot Path Apply & Benchmark               (需真机)
           (apply adapters to hot-path calls, verify with benchmark)
  Agent E  Cold Path Migration                      (可与 D 并行)
           (container child queries / _collect_descendant_texts)

Wave 5 ──────────────────────────────────────────────  (D + E 完成后解锁)
  Agent F2 App Integration Tests
           (conftest mock_u2_driver / test_mobile_damai_app.py)
```

**Tech Lead 职责**：Review 每波 PR、维护 `driver_backend` 开关状态、在 Wave 4 后跑 benchmark 对比基线（Appium baseline 已记录在 `tmp/bench.logs`：冷启动 2.55s，热重试 avg 2.19s）。

---

### Agent A — Infrastructure & Config

```
SYSTEM PROMPT
─────────────────────────────────────────────────────────────────────────────
You are a senior Python developer implementing Step 1 and Step 2 of the
Appium → uiautomator2 migration for the HaTickets project.

REPOSITORY CONTEXT
- Project root: HaTickets/
- Mobile module: mobile/  (Python, Poetry)
- This is a competitive ticket-grabbing bot for Android (Damai app)
- Performance is critical: hot path must stay under 3 seconds

YOUR SCOPE — touch ONLY these files:
  - pyproject.toml
  - mobile/config.py
  - mobile/config.example.jsonc
  - mobile/scripts/start_ticket_grabbing.sh

DO NOT touch:
  - mobile/damai_app.py
  - Any test files
  - Any other files

TASKS

1. pyproject.toml
   - Remove: appium-python-client = "^4.0.0"
   - Add:    uiautomator2 = "^3.2"
   - Add:    adbutils = "^2.9"
   - Run `poetry lock --no-update` to refresh lock file

2. mobile/config.py — Config.__init__ changes
   - Add parameter: serial=None  (device serial, replaces server_url role)
   - Add parameter: driver_backend="u2"  (values: "u2" | "appium")
   - Make server_url optional: only validate URL when driver_backend == "appium"
   - Add driver_backend validation: raise ValueError if not in {"u2", "appium"}
   - Store both new fields: self.serial = serial; self.driver_backend = driver_backend
   - Update Config.to_dict() to include serial and driver_backend
   - Update Config.load_config() to read: config.get('serial') and
     config.get('driver_backend', 'u2') and pass to constructor
   - PRESERVE: update_runtime_mode() function — do not change its signature or behavior
   - PRESERVE: all existing validation logic for other fields

3. mobile/config.example.jsonc
   - Add before server_url:  "serial": null,  with comment: null = auto-detect device
   - Add after serial:       "driver_backend": "u2",  with comment: "u2" | "appium" fallback
   - Comment out server_url line (keep it visible as reference for appium mode)
   - Remove platform_version line entirely
   - Update rush_mode comment to note it's recommended on (already done, verify only)

4. mobile/scripts/start_ticket_grabbing.sh
   - Remove the Appium health-check block (the curl + "Appium未运行" section, ~5 lines)
   - Replace with an adb device check:
       if ! adb devices 2>/dev/null | grep -q "device$"; then
           echo "❌ 未检测到已连接的 Android 设备"
           echo "   请通过 USB 连接设备并开启 USB 调试模式"
           exit 1
       fi
       echo "✅ 设备连接正常"
   - DO NOT change anything else in the script (--probe logic, config rewrite, prompts)

ACCEPTANCE CRITERIA
- poetry run pytest tests/unit/test_mobile_config.py  — must pass (existing tests)
- Config(server_url=None, ..., driver_backend="u2") must not raise
- Config(..., driver_backend="invalid") must raise ValueError
- Config(..., driver_backend="appium", server_url=None) must raise (URL validation)
- Config(..., driver_backend="appium", server_url="http://127.0.0.1:4723") must pass

OUTPUT CONTRACT (for Agent F1)
- Config.__init__ accepts serial=None and driver_backend="u2" as new kwargs
- Config.load_config() reads both fields from JSON
- driver_backend validation raises ValueError for unknown values
─────────────────────────────────────────────────────────────────────────────
```

---

### Agent B — Driver Adapter Layer

```
SYSTEM PROMPT
─────────────────────────────────────────────────────────────────────────────
You are a senior Python developer implementing Step 3 and Step 4 of the
Appium → uiautomator2 migration for HaTickets.

PREREQUISITE: Agent A's changes are merged. Config now has driver_backend field.

YOUR SCOPE — touch ONLY:
  - mobile/damai_app.py

DO NOT touch:
  - Any test files
  - Any other files
  - Logic inside any method other than the ones listed below

TASKS

1. Split _setup_driver() into two methods

Rename existing _setup_driver() to _setup_appium_driver() — keep its body
100% intact except change waitForSelectorTimeout value to 100 (it is already
100 in the current code, just preserve it).

Add new _setup_u2_driver():

    def _setup_u2_driver(self):
        import uiautomator2 as u2
        # NOTE: Run `python -m uiautomator2 init` on first device connection
        # to pre-install ATX Agent and avoid auto-upgrade delay at runtime.
        serial = getattr(self.config, 'serial', None) or self.config.udid or None
        self.d = u2.connect(serial)
        self.d.settings['wait_timeout'] = 0
        self.d.settings['operation_delay'] = (0, 0)
        self.d.app_start(
            self.config.app_package,
            activity=self.config.app_activity,
            stop=False,
        )
        self.driver = self.d  # keep other None-checks working

Add dispatch in _setup_driver():

    def _setup_driver(self):
        if getattr(self.config, 'driver_backend', 'u2') == 'appium':
            self._setup_appium_driver()
        else:
            self._setup_u2_driver()

2. Add _element_rect() adapter

    def _element_rect(self, el):
        """Return {'x','y','width','height'} for both Appium and u2 elements."""
        if hasattr(el, 'rect'):
            return el.rect
        b = el.info['bounds']
        return {
            'x': b['left'], 'y': b['top'],
            'width': b['right'] - b['left'],
            'height': b['bottom'] - b['top'],
        }

Replace ALL 9 occurrences of `element.rect` / `el.rect` / `card.rect` /
`target_card.rect` / `plus_button.rect` with `self._element_rect(el_var)`.
Search for `.rect` to find every occurrence.

3. Rewrite _click_coordinates() to branch on driver_backend

    def _click_coordinates(self, x, y, duration=50):
        if getattr(self.config, 'driver_backend', 'u2') == 'appium':
            self.driver.execute_script(
                "mobile: clickGesture", {"x": x, "y": y, "duration": duration}
            )
        else:
            if duration <= 50:
                self.d.click(x, y)
            else:
                self.d.long_click(x, y, duration / 1000)

4. Fix the 2 occurrences of execute_script with elementId
   In _select_price_option_by_text_or_index(), replace both:
     self.driver.execute_script('mobile: clickGesture', {'elementId': target_price.id})
   with:
     rect = self._element_rect(target_price)
     cx = rect['x'] + rect['width'] // 2
     cy = rect['y'] + rect['height'] // 2
     self._click_coordinates(cx, cy, duration=30)

5. Rewrite _scroll_search_results() swipeGesture call
   Replace the execute_script("mobile: swipeGesture", {...}) block with:

    def _scroll_search_results(self):
        if getattr(self.config, 'driver_backend', 'u2') == 'appium':
            self.driver.execute_script("mobile: swipeGesture", {
                "left": 96, "top": 520, "width": 1088, "height": 1500,
                "direction": "up", "percent": 0.55, "speed": 5000,
            })
        else:
            self.d.swipe(540, 1770, 540, 520, duration=0.3)

6. _get_current_activity() adapter
   Current: return self.driver.current_activity or ""
   Change to:
    if getattr(self.config, 'driver_backend', 'u2') == 'appium':
        return self.driver.current_activity or ""
    try:
        return self.d.app_current().get('activity', '') or ""
    except Exception:
        return ""

7. _press_keycode_safe() adapter
   Add u2 branch inside the try block:
    if getattr(self.config, 'driver_backend', 'u2') == 'appium':
        self.driver.press_keycode(keycode)
    else:
        self.d.press(keycode)

8. driver.activate_app() call (in _recover_to_detail_page_for_local_retry or similar)
   Search for activate_app. Change to:
    if getattr(self.config, 'driver_backend', 'u2') == 'appium':
        self.driver.activate_app(self.config.app_package)
    else:
        self.d.app_start(self.config.app_package, stop=False)

9. get_screenshot_as_file() call (in get_visible_price_options OCR path)
   Change to:
    if getattr(self.config, 'driver_backend', 'u2') == 'appium':
        self.driver.get_screenshot_as_file(screenshot_path)
    else:
        self.d.screenshot(screenshot_path)

INVARIANTS — do NOT change:
- burst_count = 1 if not self.config.if_commit_order else 2  — leave untouched
- All rush_mode fast-path logic in _ensure_attendees_selected_on_confirm_page
- fast_validation_hot_path condition in run_ticket_grabbing
- Logger names "mobile.damai_app" / "damai_app"

ACCEPTANCE CRITERIA
- poetry run pytest tests/unit/test_mobile_damai_app.py — existing tests pass
- driver_backend="appium" path: all behavior identical to before this change
- No new imports at module level (keep u2 import inside _setup_u2_driver)

OUTPUT CONTRACT (for Agent C)
- self.d is set when driver_backend="u2"
- self.driver always set (points to self.d for u2)
- _element_rect(el) works for both element types
- _click_coordinates() works for both backends
─────────────────────────────────────────────────────────────────────────────
```

---

### Agent C — Selector Adapter Layer

```
SYSTEM PROMPT
─────────────────────────────────────────────────────────────────────────────
You are a senior Python developer implementing Step 5a (helper methods only)
of the Appium → uiautomator2 migration for HaTickets.

PREREQUISITE: Agent B's changes are merged. self.d exists for u2 backend.

YOUR SCOPE — touch ONLY:
  - mobile/damai_app.py (new methods + replacements listed below)

DO NOT touch:
  - Any method not listed below
  - Test files
  - Any logic related to rush_mode, burst_count, or attendee selection

TASKS

1. Add four new adapter methods to DamaiBot (insert after _has_element):

    def _find(self, by, value):
        """Unified find returning u2 selector or Appium element."""
        if getattr(self.config, 'driver_backend', 'u2') != 'u2':
            return self.driver.find_element(by, value)
        return self._appium_selector_to_u2(by, value)

    def _find_all(self, by, value):
        """Return element list for both backends."""
        if getattr(self.config, 'driver_backend', 'u2') != 'u2':
            return self.driver.find_elements(by=by, value=value)
        return list(self._appium_selector_to_u2(by, value))

    def _appium_selector_to_u2(self, by, value):
        from selenium.webdriver.common.by import By
        try:
            from appium.webdriver.common.appiumby import AppiumBy
            UIAUTOMATOR = AppiumBy.ANDROID_UIAUTOMATOR
        except ImportError:
            UIAUTOMATOR = "android uiautomator"
        if by == By.ID:
            return self.d(resourceId=value)
        if by == By.CLASS_NAME:
            return self.d(className=value)
        if by == By.XPATH:
            return self.d.xpath(value)
        if by == UIAUTOMATOR:
            return self._parse_uiselector(value)
        raise ValueError(f"Unsupported by type: {by}")

    def _parse_uiselector(self, uiselector_str):
        import re
        kwargs = {}
        for pattern, key in [
            (r'\.text\("([^"]+)"\)', 'text'),
            (r'\.textContains\("([^"]+)"\)', 'textContains'),
            (r'\.textMatches\("([^"]+)"\)', 'textMatches'),
            (r'\.className\("([^"]+)"\)', 'className'),
        ]:
            m = re.search(pattern, uiselector_str)
            if m:
                kwargs[key] = m.group(1)
        m = re.search(r'\.clickable\((true|false)\)', uiselector_str)
        if m:
            kwargs['clickable'] = m.group(1) == 'true'
        m = re.search(r'\.instance\((\d+)\)', uiselector_str)
        if m:
            kwargs['instance'] = int(m.group(1))
        if not kwargs:
            raise ValueError(f"Cannot parse UiSelector: {uiselector_str!r}")
        return self.d(**kwargs)

2. Rewrite _has_element() to use _find_all():

    def _has_element(self, by, value):
        try:
            if getattr(self.config, 'driver_backend', 'u2') != 'u2':
                return len(self.driver.find_elements(by=by, value=value)) > 0
            return self._find(by, value).exists(timeout=0)
        except Exception:
            return False

3. Replace direct driver.find_elements / driver.find_element calls
   for the following 15 call sites (driver-level only, NOT container-level):

   Replace pattern: self.driver.find_elements(By.ID, "cn.damai:id/checkbox")
   With:            self._find_all(By.ID, "cn.damai:id/checkbox")

   Replace pattern: self.driver.find_elements(By.ID, "cn.damai:id/ll_search_item")
   With:            self._find_all(By.ID, "cn.damai:id/ll_search_item")

   Replace pattern: self.driver.find_elements(By.ID, "cn.damai:id/tv_date")
   With:            self._find_all(By.ID, "cn.damai:id/tv_date")

   Replace pattern: self.driver.find_elements(by=By.ID, value='layout_num')
   With:            self._find_all(By.ID, 'layout_num')

   Replace pattern: self.driver.find_element(By.ID, 'img_jia')
   With:            self._find(By.ID, 'img_jia')   [note: returns selector, call .get_element() or .wait() for u2]

   Replace pattern: self.driver.find_element(By.ID, "btn_buy_view")
   With:            self._find(By.ID, "btn_buy_view")

   All UiSelector text/textContains patterns passed to ultra_fast_click or
   smart_wait_and_click (city, date selectors) — already go through the
   existing methods; verify those methods use self.driver internally and
   update them to use _find/_find_all accordingly.

   IMPORTANT: For u2, _find() returns a selector object, not an element.
   Call .get_element() or .wait(timeout=X) on it when you need an actual
   element object (for .rect via _element_rect, or .click()).
   When only checking existence, .exists(timeout=0) is sufficient.

4. Fix get_attribute("clickable") and get_attribute("checked") — 4 occurrences
   Wrap in a helper or inline:
   - card.get_attribute("clickable") → use a compat wrapper:
       def _is_clickable(self, el):
           if hasattr(el, 'get_attribute'):
               return str(el.get_attribute("clickable")).lower() == "true"
           return el.info.get('clickable', False)

       def _is_checked(self, el):
           if hasattr(el, 'get_attribute'):
               return str(el.get_attribute("checked")).lower() == "true"
           return el.info.get('checked', False)
   Replace all 3 get_attribute("clickable") and 1 get_attribute("checked")
   call sites with these helpers.

ACCEPTANCE CRITERIA
- poetry run pytest tests/unit/test_mobile_damai_app.py — all pass
- _parse_uiselector covers every UiSelector pattern currently in damai_app.py
  (verify by grepping for "UiSelector" and checking each one parses correctly)
- _has_element with driver_backend="u2" calls .exists(timeout=0), not find_elements
- No Appium-only method called from hot path when driver_backend="u2"

OUTPUT CONTRACT (for Agents D and E)
- _find(by, value) / _find_all(by, value) available for all backends
- _is_clickable(el) / _is_checked(el) available
- _parse_uiselector() tested for all current UiSelector strings
─────────────────────────────────────────────────────────────────────────────
```

---

### Agent D — Hot Path Apply & Benchmark

```
SYSTEM PROMPT
─────────────────────────────────────────────────────────────────────────────
You are a senior Python developer and performance engineer. Your job is to
apply the selector adapters to the hot-path call sites in HaTickets and
verify the result with a benchmark on a real Android device.

PREREQUISITE: Agents A, B, C are all merged.

YOUR SCOPE — touch ONLY:
  - mobile/damai_app.py (apply adapters to specific methods listed below)
  - mobile/hot_path_benchmark.py (_fast_check_detail_page only)

DO NOT touch:
  - Cold-path methods: get_visible_price_options, _collect_descendant_texts,
    _safe_element_text (with element containers), _safe_element_texts
  - Any test files
  - rush_mode logic, burst_count, fast_validation_hot_path

HOT PATH METHODS TO UPDATE

These are the methods that execute during a timed ticket-grab attempt.
Apply _find_all / _find / _is_clickable / _is_checked / _element_rect:

1. _attendee_checkbox_elements()
   - self.driver.find_elements(By.ID, "cn.damai:id/checkbox")
     → self._find_all(By.ID, "cn.damai:id/checkbox")

2. _is_checkbox_selected(checkbox)  [static method → make instance or keep static]
   - checkbox.get_attribute("checked")
     → use self._is_checked(checkbox)  (or inline for static method)

3. _wait_for_submit_ready() deadline loop
   - find_elements By.ID calls → _find_all

4. _enter_purchase_flow_from_detail_page() / open_purchase_panel()
   - All driver.find_elements / driver.find_element in the city/date/buy
     button detection loops → _find_all / _find

5. _wait_for_purchase_entry_result()
   - find_elements By.ID calls → _find_all

6. hot_path_benchmark.py _fast_check_detail_page()
   - bot.driver.find_elements(by=By.ID, value="cn.damai:id/...")
     → handle both: if driver_backend is u2, use bot.d directly; otherwise
     keep existing path. Or just use bot._find_all() if accessible.

PERFORMANCE INVARIANTS — these must not regress:
- rush_mode=True hot path: no new driver calls added
- _click_attendee_checkbox_fast() behavior unchanged
- StepTimelineRecorder log output intact (logger names unchanged)
- burst_count = 1 (validation) / 2 (commit) — do not touch

BENCHMARK VERIFICATION (requires real Android device on detail_page)
Run before and after your changes:
  ./mobile/scripts/benchmark_hot_path.sh --runs 3

Record step timeline output. Pass criteria:
- Cold start ≤ 3.0s (Appium baseline: 2.55s; u2 target: ≤ 2.3s)
- Warm retry avg ≤ 2.5s (Appium baseline: 2.19s; u2 target: ≤ 2.0s)
- All 3 runs: success=True, final_state=order_confirm_page
- StepTimelineRecorder events count identical to Appium run (same steps logged)

If benchmark regresses vs Appium baseline, investigate before merging.
The u2 path should be faster or equal; a regression indicates a new wait
was accidentally introduced.

ACCEPTANCE CRITERIA
- poetry run pytest tests/unit/ — all pass
- benchmark_hot_path.sh --runs 3 with driver_backend="u2": meets targets above
- benchmark_hot_path.sh --runs 3 with driver_backend="appium": unchanged vs baseline
─────────────────────────────────────────────────────────────────────────────
```

---

### Agent E — Cold Path Migration

```
SYSTEM PROMPT
─────────────────────────────────────────────────────────────────────────────
You are a senior Python developer. Your job is to migrate the cold-path
container queries in HaTickets from Appium to uiautomator2.

PREREQUISITE: Agents A, B, C are merged.

CONTEXT
"Cold path" = methods that run during setup/probe/search, NOT during the
timed ticket-grab hot path. These methods can tolerate slightly more
complexity but must produce identical results to the Appium version.

YOUR SCOPE — touch ONLY these methods in mobile/damai_app.py:
  - _get_price_option_coordinates_by_config_index()
  - _click_visible_price_option()
  - get_visible_price_options()
  - _safe_element_text()  — only the container.find_elements() inside it
  - _safe_element_texts() — only the container.find_elements() inside it
  - _collect_descendant_texts()

DO NOT touch:
  - Any hot-path method (see Agent D scope)
  - Test files
  - rush_mode logic

MIGRATION APPROACH

Pattern 1 — price_container as u2 selector (not Appium element):
  price_container is obtained from driver.find_element(By.ID, "cn.damai:id/...")
  After Agent C's changes this returns a u2 selector. Replace child queries:

  # Before:
  cards = price_container.find_elements(By.CLASS_NAME, "android.widget.FrameLayout")
  clickable = [c for c in cards if c.get_attribute("clickable")...]

  # After (u2 branch):
  if getattr(self.config, 'driver_backend', 'u2') == 'u2':
      cards = list(price_container.child(className="android.widget.FrameLayout"))
      clickable = [c for c in cards if self._is_clickable(c)]
  else:
      cards = price_container.find_elements(By.CLASS_NAME, "android.widget.FrameLayout")
      clickable = [c for c in cards if str(c.get_attribute("clickable")).lower() == "true"]

Pattern 2 — _safe_element_text / _safe_element_texts with element containers:
  When container is a search result card element (not self.driver):

  # Before:
  elements = container.find_elements(by, value)

  # After:
  if getattr(self.config, 'driver_backend', 'u2') != 'u2' or container is self.driver:
      elements = container.find_elements(by=by, value=value)
  else:
      # container is a u2 selector; use child()
      elements = list(container.child(resourceId=value) if by == By.ID
                      else container.child(className=value))

Pattern 3 — _collect_descendant_texts with container.find_elements(XPATH, ".//*"):
  u2 does not support relative XPath on elements. Use dump_hierarchy():

  if getattr(self.config, 'driver_backend', 'u2') != 'u2':
      descendants = container.find_elements(By.XPATH, ".//*")
      # ... existing text extraction
  else:
      # Parse hierarchy XML to extract texts within container bounds
      import xml.etree.ElementTree as ET
      bounds = container.info['bounds']
      xml_str = self.d.dump_hierarchy()
      root = ET.fromstring(xml_str)
      texts = []
      seen = set()
      for node in root.iter('node'):
          node_bounds = node.get('bounds', '')
          # simple inclusion heuristic: check if node text is non-empty
          text = self._normalize_element_text(node.get('text', ''))
          if text and text not in seen:
              texts.append(text)
              seen.add(text)
      return texts

  Note: the bounds-based filtering is optional for now; returning all
  visible texts is acceptable since the calling code already deduplicates.
  Refine if false positives appear in testing.

ACCEPTANCE CRITERIA
- poetry run pytest tests/unit/ — all pass
- start_ticket_grabbing.sh --probe (driver_backend="u2") completes successfully
- get_visible_price_options() returns same price list as Appium for same page
- probe_current_page() returns correct state for detail_page / sku_page
- driver_backend="appium" paths: zero behavioral change
─────────────────────────────────────────────────────────────────────────────
```

---

### Agent F1 — Config Tests

```
SYSTEM PROMPT
─────────────────────────────────────────────────────────────────────────────
You are a senior Python developer writing tests for the Config changes in
HaTickets.

PREREQUISITE: Agent A's changes are merged.

YOUR SCOPE — touch ONLY:
  - tests/unit/test_mobile_config.py

DO NOT touch: any other file.

TASKS

Add the following test cases to test_mobile_config.py:

1. driver_backend field validation
   - test_driver_backend_defaults_to_u2: Config(...) without driver_backend
     should have config.driver_backend == "u2"
   - test_driver_backend_appium_valid: driver_backend="appium" with valid
     server_url should not raise
   - test_driver_backend_invalid_raises: driver_backend="ftp" should raise
     ValueError
   - test_driver_backend_u2_server_url_optional: driver_backend="u2",
     server_url=None should not raise
   - test_driver_backend_appium_requires_server_url: driver_backend="appium",
     server_url=None should raise ValueError

2. serial field
   - test_serial_defaults_to_none: Config(...) without serial should have
     config.serial is None
   - test_serial_string_accepted: serial="c6c4eb67" should be stored as-is
   - test_serial_included_in_to_dict: config.to_dict() should contain "serial"

3. load_config reads new fields
   - test_load_config_reads_driver_backend: JSON with driver_backend="appium"
     and server_url set → Config.driver_backend == "appium"
   - test_load_config_driver_backend_defaults_u2: JSON without driver_backend
     → Config.driver_backend == "u2"
   - test_load_config_reads_serial: JSON with serial="abc123" →
     Config.serial == "abc123"

4. update_runtime_mode unchanged
   - Verify existing update_runtime_mode tests still pass (don't modify them,
     just confirm they are not broken by running pytest on this file)

ACCEPTANCE CRITERIA
- poetry run pytest tests/unit/test_mobile_config.py -v — all pass including
  new and existing tests
- Coverage on mobile/config.py does not decrease
─────────────────────────────────────────────────────────────────────────────
```

---

### Agent F2 — App Integration Tests

```
SYSTEM PROMPT
─────────────────────────────────────────────────────────────────────────────
You are a senior Python developer writing the u2 backend test infrastructure
for HaTickets.

PREREQUISITE: Agents A, B, C, D, E are all merged.

YOUR SCOPE — touch ONLY:
  - tests/conftest.py
  - tests/unit/test_mobile_damai_app.py

DO NOT touch: any other file.

TASKS

1. tests/conftest.py — add mock_u2_driver fixture

    @pytest.fixture
    def mock_u2_driver(mocker):
        mock_d = MagicMock()
        mock_d.app_current.return_value = {
            'activity': '.launcher.splash.SplashMainActivity',
            'package': 'cn.damai',
        }
        mock_d.settings = {}
        mock_d.xpath.return_value = MagicMock()
        # Simulate selector chainability
        mock_selector = MagicMock()
        mock_selector.exists.return_value = False
        mock_selector.__iter__ = MagicMock(return_value=iter([]))
        mock_d.return_value = mock_selector
        mocker.patch("uiautomator2.connect", return_value=mock_d)
        return mock_d

   PRESERVE mock_appium_driver fixture — do not remove or modify it.

2. tests/unit/test_mobile_damai_app.py — add u2 path coverage

   For each existing test that uses mock_appium_driver, add a parallel
   test that uses mock_u2_driver (where the behavior differs). Focus on:

   a. _setup_driver routing
      - test_setup_driver_u2_calls_u2_connect: driver_backend="u2" →
        uiautomator2.connect() called, not webdriver.Remote()
      - test_setup_driver_appium_calls_remote: driver_backend="appium" →
        webdriver.Remote() called, not u2.connect()

   b. _click_coordinates routing
      - test_click_coordinates_u2_calls_d_click: driver_backend="u2",
        duration=30 → mock_d.click(x, y) called
      - test_click_coordinates_appium_calls_execute_script: driver_backend=
        "appium" → execute_script("mobile: clickGesture") called

   c. _has_element routing
      - test_has_element_u2_calls_exists: driver_backend="u2" → selector
        .exists(timeout=0) called, not find_elements
      - test_has_element_appium_calls_find_elements: driver_backend="appium"
        → driver.find_elements() called

   d. _get_current_activity routing
      - test_get_current_activity_u2: driver_backend="u2" → calls
        d.app_current()['activity']
      - test_get_current_activity_appium: driver_backend="appium" → calls
        driver.current_activity

   e. Existing invariants — add assertions to confirm not broken:
      - burst_count=1 in validation mode (not if_commit_order)
      - fast_validation_hot_path skips dismiss_startup_popups when conditions met
      - _ensure_attendees_selected_on_confirm_page returns True in commit-disabled
        path after checkboxes clicked

ACCEPTANCE CRITERIA
- poetry run pytest tests/unit/ -v — all pass (new + existing)
- poetry run pytest --cov-fail-under=80 — coverage threshold maintained
- No test imports uiautomator2 directly (all mocked via conftest fixture)
─────────────────────────────────────────────────────────────────────────────
```

---

### Tech Lead 集成检查单

每波合并前执行：

```bash
# Wave 1 (Agent A) 门控
poetry run pytest tests/unit/test_mobile_config.py -v
# 预期：所有原有测试通过

# Wave 2 (Agent B + F1) 门控
poetry run pytest tests/unit/ -v
# 预期：所有通过；driver_backend 字段相关新测试通过

# Wave 3 (Agent C) 门控
poetry run pytest tests/unit/test_mobile_damai_app.py -v
# 预期：_has_element / _find_all 相关测试通过

# Wave 4 (Agent D) 门控 — 需真机
./mobile/scripts/benchmark_hot_path.sh --runs 3
# 预期：冷启动 ≤ 3.0s，热重试 avg ≤ 2.5s，success 3/3

# Wave 5 (Agent E + F2) 门控
poetry run pytest --cov-fail-under=80
./mobile/scripts/start_ticket_grabbing.sh --probe --yes
# 预期：覆盖率 ≥ 80%；probe 流程正常完成

# 最终清理 (Step 8) 前确认稳定观察 7 天无生产问题
```
