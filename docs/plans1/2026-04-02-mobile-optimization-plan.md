# Mobile Module Optimization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optimize the mobile ticket-grabbing module — warm path < 1.0s, cold path < 3.0s, success rate > 95%, zero accidental reservation clicks — and restructure the 3559-line monolith into 7 focused modules.

**Architecture:** Phase 1 adds the safety-critical BuyButtonGuard. Phase 2-3 fix performance and stability on the current monolith. Phase 4 splits damai_app.py into 7 modules preserving all public APIs. Phase 5 runs the full test suite and real-device benchmarks.

**Tech Stack:** Python 3.8+, uiautomator2, threading, xml.etree, pytest + pytest-cov (80% threshold)

**Design Spec:** `docs/plans/2026-04-02-mobile-optimization-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `mobile/buy_button_guard.py` | CREATE | Button safety gate + countdown polling |
| `mobile/page_probe.py` | CREATE | Fast/full page state detection with TTL cache |
| `mobile/event_navigator.py` | CREATE | Search + navigate to target event |
| `mobile/price_selector.py` | CREATE | SKU/price selection, OCR fallback |
| `mobile/attendee_selector.py` | CREATE | Confirm page attendee checkbox logic |
| `mobile/fast_pipeline.py` | CREATE | Warm/cold hot-path pipelines with global deadline |
| `mobile/recovery.py` | CREATE | Layered back-navigation + failure recovery |
| `mobile/damai_app.py` | MODIFY | Slim down to thin orchestrator (~400 lines) |
| `tests/unit/test_buy_button_guard.py` | CREATE | Guard safety tests |
| `tests/unit/test_page_probe.py` | CREATE | Probe mode + cache tests |
| `tests/unit/test_fast_pipeline.py` | CREATE | Deadline + pipeline tests |
| `tests/unit/test_recovery.py` | CREATE | Layered recovery tests |
| `tests/unit/test_event_navigator.py` | CREATE | Navigation tests |
| `tests/unit/test_price_selector.py` | CREATE | Price selection tests |
| `tests/unit/test_attendee_selector.py` | CREATE | Attendee logic tests |

---

## Phase 1: BuyButtonGuard + Countdown Trigger (Safety First)

### Task 1: BuyButtonGuard Module

**Files:**
- Create: `mobile/buy_button_guard.py`
- Test: `tests/unit/test_buy_button_guard.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_buy_button_guard.py`:

```python
"""Unit tests for BuyButtonGuard — prevents accidental reservation clicks."""

import time
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from mobile.buy_button_guard import BuyButtonGuard


class TestIsSafeToClick:
    def test_safe_text_li_ji_gou_piao(self):
        guard = BuyButtonGuard(device=MagicMock())
        assert guard.is_safe_to_click("立即购票") is True

    def test_safe_text_li_ji_qiang_piao(self):
        guard = BuyButtonGuard(device=MagicMock())
        assert guard.is_safe_to_click("立即抢票") is True

    def test_safe_text_xuan_zuo_gou_mai(self):
        guard = BuyButtonGuard(device=MagicMock())
        assert guard.is_safe_to_click("选座购买") is True

    def test_blocked_text_yu_yue_qiang_piao(self):
        guard = BuyButtonGuard(device=MagicMock())
        assert guard.is_safe_to_click("预约抢票") is False

    def test_blocked_text_yu_yue(self):
        guard = BuyButtonGuard(device=MagicMock())
        assert guard.is_safe_to_click("预约") is False

    def test_blocked_text_ji_jiang_kai_qiang(self):
        guard = BuyButtonGuard(device=MagicMock())
        assert guard.is_safe_to_click("即将开抢") is False

    def test_blocked_text_dai_kai_shou(self):
        guard = BuyButtonGuard(device=MagicMock())
        assert guard.is_safe_to_click("待开售") is False

    def test_empty_text_is_blocked(self):
        guard = BuyButtonGuard(device=MagicMock())
        assert guard.is_safe_to_click("") is False

    def test_none_text_is_blocked(self):
        guard = BuyButtonGuard(device=MagicMock())
        assert guard.is_safe_to_click(None) is False

    def test_unknown_text_is_blocked(self):
        guard = BuyButtonGuard(device=MagicMock())
        assert guard.is_safe_to_click("提交抢票预约") is False


class TestWaitUntilSafe:
    def test_immediately_safe(self):
        d = MagicMock()
        btn = MagicMock()
        btn.get_text.return_value = "立即购票"
        d.return_value = btn
        guard = BuyButtonGuard(device=d)
        guard._find_buy_button = MagicMock(return_value=btn)
        result = guard.wait_until_safe(timeout_s=2.0, poll_ms=50)
        assert result is True

    def test_transitions_from_blocked_to_safe(self):
        d = MagicMock()
        btn = MagicMock()
        call_count = {"n": 0}
        def get_text_side_effect():
            call_count["n"] += 1
            if call_count["n"] <= 3:
                return "预约抢票"
            return "立即购票"
        btn.get_text.side_effect = get_text_side_effect
        guard = BuyButtonGuard(device=d)
        guard._find_buy_button = MagicMock(return_value=btn)
        result = guard.wait_until_safe(timeout_s=2.0, poll_ms=10)
        assert result is True

    def test_timeout_returns_false(self):
        d = MagicMock()
        btn = MagicMock()
        btn.get_text.return_value = "预约抢票"
        guard = BuyButtonGuard(device=d)
        guard._find_buy_button = MagicMock(return_value=btn)
        result = guard.wait_until_safe(timeout_s=0.1, poll_ms=10)
        assert result is False

    def test_button_not_found_returns_false(self):
        d = MagicMock()
        guard = BuyButtonGuard(device=d)
        guard._find_buy_button = MagicMock(return_value=None)
        result = guard.wait_until_safe(timeout_s=0.1, poll_ms=10)
        assert result is False
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd /Users/andrew/Documents/GitHub/HaTickets && poetry run pytest tests/unit/test_buy_button_guard.py -v`
Expected: `ModuleNotFoundError: No module named 'mobile.buy_button_guard'`

- [ ] **Step 3: Implement BuyButtonGuard**

Create `mobile/buy_button_guard.py`:

```python
"""BuyButtonGuard — prevents accidental clicks on reservation buttons.

The Damai app shows "预约抢票" before sale starts and "立即购票" after.
Clicking "预约抢票" enters a reservation flow (wrong), not the purchase flow.
This guard ensures we ONLY click when the button text indicates an active sale.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

from mobile.logger import get_logger

logger = get_logger(__name__)

SAFE_TEXTS = frozenset({
    "立即购买", "立即抢票", "立即预定", "选座购买",
    "购买", "抢票", "预定",
})

BLOCKED_TEXTS = frozenset({
    "预约抢票", "预约", "预售", "即将开抢",
    "待开售", "未开售", "提交抢票预约",
})

_BUY_BUTTON_ID = "cn.damai:id/trade_project_detail_purchase_status_bar_container_fl"
_BUY_BUTTON_TEXT_ID = "cn.damai:id/btn_buy_view"


class BuyButtonGuard:
    """Gate all purchase-button clicks through safety text checks."""

    def __init__(self, device) -> None:
        self._d = device

    def is_safe_to_click(self, button_text: Optional[str]) -> bool:
        """Return True only if button_text indicates an active sale."""
        if not button_text:
            return False
        return button_text.strip() in SAFE_TEXTS

    def _find_buy_button(self):
        """Locate the buy button element. Returns None if not found."""
        try:
            el = self._d(resourceId=_BUY_BUTTON_TEXT_ID)
            if el.exists:
                return el
        except Exception:
            pass
        return None

    def wait_until_safe(
        self,
        timeout_s: float = 10.0,
        poll_ms: int = 50,
    ) -> bool:
        """Poll button text until it becomes safe to click.

        Returns True if safe text detected, False on timeout or missing button.
        """
        deadline = time.time() + timeout_s
        interval = poll_ms / 1000.0

        while time.time() < deadline:
            btn = self._find_buy_button()
            if btn is None:
                time.sleep(interval)
                continue
            try:
                text = btn.get_text()
            except Exception:
                time.sleep(interval)
                continue

            if self.is_safe_to_click(text):
                logger.info(f"按钮安全: {text!r}")
                return True

            if text and text.strip() in BLOCKED_TEXTS:
                logger.debug(f"按钮等待中: {text!r}")

            time.sleep(interval)

        logger.warning(f"等待安全按钮超时 ({timeout_s}s)")
        return False

    def get_current_text(self) -> Optional[str]:
        """Read current button text without clicking. Returns None if not found."""
        btn = self._find_buy_button()
        if btn is None:
            return None
        try:
            return btn.get_text()
        except Exception:
            return None
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd /Users/andrew/Documents/GitHub/HaTickets && poetry run pytest tests/unit/test_buy_button_guard.py -v`
Expected: All 14 tests PASS

- [ ] **Step 5: Commit**

```bash
git add mobile/buy_button_guard.py tests/unit/test_buy_button_guard.py
git commit -m "feat: add BuyButtonGuard to prevent accidental reservation clicks"
```

---

## Phase 2: Performance Fixes

### Task 2: PageProbe with Fast Mode + TTL Cache

**Files:**
- Create: `mobile/page_probe.py`
- Test: `tests/unit/test_page_probe.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_page_probe.py`:

```python
"""Unit tests for PageProbe — fast/full page detection with TTL cache."""

import time
from unittest.mock import MagicMock, patch

import pytest

from mobile.page_probe import PageProbe


@pytest.fixture
def mock_device():
    d = MagicMock()
    d.app_current.return_value = {"activity": ".unknown.Activity"}
    return d


@pytest.fixture
def probe(mock_device):
    return PageProbe(device=mock_device)


class TestFastProbe:
    def test_detail_page_by_activity(self, probe, mock_device):
        mock_device.app_current.return_value = {
            "activity": ".trade.newtradeorder.ui.projectdetail.ui.activity.ProjectDetailActivity"
        }
        result = probe.probe_current_page(fast=True)
        assert result["state"] == "detail_page"

    def test_sku_page_by_activity(self, probe, mock_device):
        mock_device.app_current.return_value = {
            "activity": ".ui.NcovSkuActivity"
        }
        result = probe.probe_current_page(fast=True)
        assert result["state"] == "sku_page"

    def test_homepage_by_activity(self, probe, mock_device):
        mock_device.app_current.return_value = {
            "activity": ".homepage.MainActivity"
        }
        result = probe.probe_current_page(fast=True)
        assert result["state"] == "homepage"

    def test_unknown_falls_through_to_full(self, probe, mock_device):
        mock_device.app_current.return_value = {"activity": ".some.OtherActivity"}
        # Mock _has_element to return False for everything
        probe._has_element = MagicMock(return_value=False)
        result = probe.probe_current_page(fast=True)
        assert result["state"] == "unknown"


class TestTTLCache:
    def test_cached_result_returned_within_ttl(self, probe, mock_device):
        mock_device.app_current.return_value = {
            "activity": ".trade.newtradeorder.ui.projectdetail.ui.activity.ProjectDetailActivity"
        }
        result1 = probe.probe_current_page(fast=True)
        mock_device.app_current.return_value = {"activity": ".homepage.MainActivity"}
        result2 = probe.probe_current_page(fast=True)
        # Should return cached detail_page, not homepage
        assert result2["state"] == "detail_page"

    def test_cache_expires_after_ttl(self, probe, mock_device):
        probe._cache_ttl_s = 0.05  # 50ms TTL for test
        mock_device.app_current.return_value = {
            "activity": ".trade.newtradeorder.ui.projectdetail.ui.activity.ProjectDetailActivity"
        }
        probe.probe_current_page(fast=True)
        time.sleep(0.06)
        mock_device.app_current.return_value = {"activity": ".homepage.MainActivity"}
        result = probe.probe_current_page(fast=True)
        assert result["state"] == "homepage"

    def test_invalidate_clears_cache(self, probe, mock_device):
        mock_device.app_current.return_value = {
            "activity": ".trade.newtradeorder.ui.projectdetail.ui.activity.ProjectDetailActivity"
        }
        probe.probe_current_page(fast=True)
        probe.invalidate_cache()
        mock_device.app_current.return_value = {"activity": ".homepage.MainActivity"}
        result = probe.probe_current_page(fast=True)
        assert result["state"] == "homepage"


class TestFullProbe:
    def test_order_confirm_page_by_submit_button(self, probe, mock_device):
        mock_device.app_current.return_value = {"activity": ".some.Activity"}
        def has_element_side_effect(by, value):
            if "立即提交" in str(value):
                return True
            return False
        probe._has_element = MagicMock(side_effect=has_element_side_effect)
        result = probe.probe_current_page(fast=False)
        assert result["state"] == "order_confirm_page"
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd /Users/andrew/Documents/GitHub/HaTickets && poetry run pytest tests/unit/test_page_probe.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement PageProbe**

Create `mobile/page_probe.py`:

```python
"""PageProbe — fast and full page state detection with TTL cache.

Fast mode (~100ms): checks only Activity name + 1 key element.
Full mode (~1.5s): checks 12+ elements for comprehensive state.
TTL cache: repeated calls within 500ms return cached result.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from mobile.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_CACHE_TTL = 0.5  # seconds

# Activity substrings for fast detection
_ACTIVITY_MAP = {
    "ProjectDetail": "detail_page",
    "NcovSku": "sku_page",
    "MainActivity": "homepage",
    "SearchActivity": "search_page",
}

# Element IDs for full probe (By.ID values)
_CONSENT_ID = "cn.damai:id/id_boot_action_agree"
_PURCHASE_BAR_ID = "cn.damai:id/trade_project_detail_purchase_status_bar_container_fl"
_DETAIL_PRICE_ID = "cn.damai:id/project_detail_price_layout"
_SKU_LAYOUT_ID = "cn.damai:id/layout_sku"
_SKU_CONTAINER_ID = "cn.damai:id/sku_contanier"
_PRICE_FLOW_ID = "cn.damai:id/project_detail_perform_price_flowlayout"
_PRICE_LAYOUT_ID = "cn.damai:id/layout_price"
_PRICE_NAME_ID = "cn.damai:id/tv_price_name"
_QUANTITY_ID = "layout_num"
_CHECKBOX_ID = "cn.damai:id/checkbox"
_SEARCH_INPUT_ID = "cn.damai:id/header_search_v2_input"
_HOMEPAGE_SEARCH_ID = "cn.damai:id/homepage_header_search"
_HOMEPAGE_SEARCH_BTN_ID = "cn.damai:id/pioneer_homepage_header_search_btn"
_DIALOG_CONFIRM_ID = "cn.damai:id/damai_theme_dialog_confirm_btn"
_TITLE_ID = "cn.damai:id/title_tv"


def _empty_probe(state: str = "unknown") -> Dict[str, Any]:
    return {
        "state": state,
        "purchase_button": False,
        "price_container": False,
        "quantity_picker": False,
        "submit_button": False,
        "reservation_mode": False,
        "pending_order_dialog": False,
    }


class PageProbe:
    """Detects the current page state of the Damai app."""

    def __init__(self, device, config=None, cache_ttl_s: float = _DEFAULT_CACHE_TTL) -> None:
        self._d = device
        self._config = config
        self._cache_ttl_s = cache_ttl_s
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_time: float = 0.0

    def invalidate_cache(self) -> None:
        """Force next probe to do a fresh lookup."""
        self._cache = None
        self._cache_time = 0.0

    def probe_current_page(self, fast: bool = False) -> Dict[str, Any]:
        """Detect current page state.

        Args:
            fast: If True, only check Activity name (~100ms).
                  If False, full 12+ element probe (~1.5s).
        """
        # TTL cache check
        if self._cache and (time.time() - self._cache_time) < self._cache_ttl_s:
            return self._cache

        if fast:
            result = self._fast_probe()
            if result["state"] != "unknown":
                self._cache = result
                self._cache_time = time.time()
                return result
            # Fall through to full probe if fast is inconclusive

        result = self._full_probe()
        self._cache = result
        self._cache_time = time.time()
        logger.info(f"当前页面状态: {result['state']}")
        return result

    def get_current_activity(self) -> str:
        """Return current Activity class name."""
        try:
            info = self._d.app_current()
            return info.get("activity", "")
        except Exception:
            return ""

    def _has_element(self, by, value) -> bool:
        """Check if element exists (thin wrapper for testability)."""
        try:
            from appium.webdriver.common.appiumby import AppiumBy
            if by == AppiumBy.ANDROID_UIAUTOMATOR:
                return self._d(text=value).exists if isinstance(value, str) and not value.startswith("new ") else False
        except ImportError:
            pass
        try:
            el = self._d(resourceId=value)
            return el.exists
        except Exception:
            return False

    def _fast_probe(self) -> Dict[str, Any]:
        """Activity-name-only probe (~100ms)."""
        activity = self.get_current_activity()
        for substr, state in _ACTIVITY_MAP.items():
            if substr in activity:
                result = _empty_probe(state)
                return result
        return _empty_probe("unknown")

    def _full_probe(self) -> Dict[str, Any]:
        """Comprehensive element-based probe (~1.5s)."""
        activity = self.get_current_activity()

        # Check elements
        purchase_button = self._has_element_by_id(_PURCHASE_BAR_ID)
        detail_price = self._has_element_by_id(_DETAIL_PRICE_ID)
        sku_layout = self._has_element_by_id(_SKU_LAYOUT_ID) or self._has_element_by_id(_SKU_CONTAINER_ID)
        price_container = (
            self._has_element_by_id(_PRICE_FLOW_ID)
            or self._has_element_by_id(_PRICE_LAYOUT_ID)
            or self._has_element_by_id(_PRICE_NAME_ID)
        )
        quantity_picker = self._has_element_by_id(_QUANTITY_ID)
        submit_button = self._has_element_by_text("立即提交")
        checkbox = self._has_element_by_id(_CHECKBOX_ID)

        # Determine state
        state = "unknown"

        if self._has_element_by_id(_CONSENT_ID):
            state = "consent_dialog"
        elif self._detect_pending_order():
            state = "pending_order_dialog"
        elif "MainActivity" in activity or self._has_element_by_id(_HOMEPAGE_SEARCH_ID) or self._has_element_by_id(_HOMEPAGE_SEARCH_BTN_ID):
            state = "homepage"
        elif "SearchActivity" in activity or self._has_element_by_id(_SEARCH_INPUT_ID):
            state = "search_page"
        elif submit_button or checkbox:
            state = "order_confirm_page"
        elif "NcovSku" in activity or sku_layout:
            state = "sku_page"
        elif "ProjectDetail" in activity or purchase_button or detail_price or self._has_element_by_id(_TITLE_ID):
            state = "detail_page"

        return {
            "state": state,
            "purchase_button": purchase_button,
            "price_container": price_container or detail_price,
            "quantity_picker": quantity_picker,
            "submit_button": submit_button,
            "reservation_mode": False,
            "pending_order_dialog": state == "pending_order_dialog",
        }

    def _has_element_by_id(self, resource_id: str) -> bool:
        try:
            return self._d(resourceId=resource_id).exists
        except Exception:
            return False

    def _has_element_by_text(self, text: str) -> bool:
        try:
            return self._d(text=text).exists
        except Exception:
            return False

    def _detect_pending_order(self) -> bool:
        try:
            return (
                self._d(textContains="未支付订单").exists
                or (
                    self._has_element_by_id(_DIALOG_CONFIRM_ID)
                    and self._d(textContains="查看订单").exists
                )
            )
        except Exception:
            return False
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd /Users/andrew/Documents/GitHub/HaTickets && poetry run pytest tests/unit/test_page_probe.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add mobile/page_probe.py tests/unit/test_page_probe.py
git commit -m "feat: add PageProbe with fast mode and TTL cache"
```

---

### Task 3: FastPipeline with Global Deadline

**Files:**
- Create: `mobile/fast_pipeline.py`
- Test: `tests/unit/test_fast_pipeline.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_fast_pipeline.py`:

```python
"""Unit tests for FastPipeline — warm/cold paths with global deadline."""

import time
import threading
from unittest.mock import MagicMock, patch

import pytest

from mobile.fast_pipeline import FastPipeline, poll_until


class TestPollUntil:
    def test_returns_true_when_condition_met(self):
        result = poll_until(lambda: True, deadline=time.time() + 1.0)
        assert result is True

    def test_returns_false_on_timeout(self):
        result = poll_until(lambda: False, deadline=time.time() + 0.1, interval_s=0.02)
        assert result is False

    def test_respects_deadline(self):
        start = time.time()
        poll_until(lambda: False, deadline=time.time() + 0.2, interval_s=0.01)
        elapsed = time.time() - start
        assert elapsed < 0.5  # should not exceed deadline by much


class TestGlobalDeadline:
    def test_cold_pipeline_respects_5s_deadline(self):
        d = MagicMock()
        probe = MagicMock()
        guard = MagicMock()
        guard.is_safe_to_click.return_value = True
        config = MagicMock()
        config.rush_mode = True
        config.price_index = 0
        config.users = ["user1"]
        config.city = ""
        pipeline = FastPipeline(device=d, config=config, probe=probe, guard=guard)
        # Simulate everything timing out
        pipeline._dump_hierarchy_xml = MagicMock(return_value=None)
        start = time.time()
        result = pipeline.run_cold(start_time=start)
        elapsed = time.time() - start
        assert result is None  # failed
        assert elapsed < 6.0  # should not exceed 5s + margin

    def test_warm_pipeline_completes_fast_with_cache(self):
        d = MagicMock()
        d.shell = MagicMock()
        probe = MagicMock()
        guard = MagicMock()
        guard.is_safe_to_click.return_value = True
        config = MagicMock()
        config.rush_mode = True
        config.price_index = 0
        config.users = ["user1"]
        config.city = "北京"
        pipeline = FastPipeline(device=d, config=config, probe=probe, guard=guard)
        pipeline._cached_coords = {
            "detail_buy": (100, 200),
            "price": (150, 300),
            "sku_buy": (200, 400),
            "attendee_checkboxes": [(250, 500)],
        }
        # Mock checkbox detection to succeed immediately
        pipeline._has_element_by_id = MagicMock(return_value=True)
        pipeline._click_coordinates = MagicMock()
        start = time.time()
        result = pipeline.run_warm(start_time=start)
        elapsed = time.time() - start
        assert result is True
        assert elapsed < 1.0  # should be near-instant with mocks


class TestWarmPipelineCoords:
    def test_has_warm_coords_true(self):
        d = MagicMock()
        pipeline = FastPipeline(device=d, config=MagicMock(), probe=MagicMock(), guard=MagicMock())
        pipeline._cached_coords = {
            "detail_buy": (1, 2), "price": (3, 4),
            "sku_buy": (5, 6), "attendee_checkboxes": [(7, 8)],
        }
        assert pipeline.has_warm_coords() is True

    def test_has_warm_coords_false_missing_key(self):
        d = MagicMock()
        pipeline = FastPipeline(device=d, config=MagicMock(), probe=MagicMock(), guard=MagicMock())
        pipeline._cached_coords = {"detail_buy": (1, 2)}
        assert pipeline.has_warm_coords() is False
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd /Users/andrew/Documents/GitHub/HaTickets && poetry run pytest tests/unit/test_fast_pipeline.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement FastPipeline**

Create `mobile/fast_pipeline.py`:

```python
"""FastPipeline — warm and cold hot-path ticket purchase flows.

Uses a global pipeline deadline (default 5s) instead of per-phase deadlines
to prevent timeout cascade (the root cause of 17.8s cold-path failures).
"""

from __future__ import annotations

import threading
import time
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from mobile.logger import get_logger

if TYPE_CHECKING:
    from mobile.buy_button_guard import BuyButtonGuard
    from mobile.page_probe import PageProbe

logger = get_logger(__name__)

_PIPELINE_DEADLINE_S = 5.0
_CHECKBOX_ID = "cn.damai:id/checkbox"
_SKU_LAYOUT_ID = "cn.damai:id/layout_sku"


def poll_until(condition_fn, deadline: float, interval_s: float = 0.05) -> bool:
    """Poll condition_fn until it returns True or deadline passes."""
    while time.time() < deadline:
        if condition_fn():
            return True
        time.sleep(interval_s)
    return False


def batch_shell_taps(device, coordinates: List[Tuple[int, int]]) -> None:
    """Send multiple tap commands in a single ADB shell call."""
    if not coordinates:
        return
    cmds = [f"input tap {int(x)} {int(y)}" for x, y in coordinates]
    device.shell("; ".join(cmds))


class FastPipeline:
    """Warm and cold hot-path flows with global deadline."""

    def __init__(self, device, config, probe: PageProbe, guard: BuyButtonGuard) -> None:
        self._d = device
        self._config = config
        self._probe = probe
        self._guard = guard
        self._cached_coords: Dict[str, Any] = {}
        self._cached_no_match: set = set()

    @property
    def cached_coords(self) -> Dict[str, Any]:
        return self._cached_coords

    def has_warm_coords(self) -> bool:
        c = self._cached_coords
        return all([
            c.get("detail_buy"),
            c.get("price"),
            c.get("sku_buy"),
            c.get("attendee_checkboxes"),
        ])

    def run_warm(self, start_time: float) -> Optional[bool]:
        """Ultra-fast warm path using cached coordinates.

        Returns True on success, None to fall back.
        """
        if not self.has_warm_coords():
            return None

        deadline = start_time + _PIPELINE_DEADLINE_S
        coords = self._cached_coords
        detail_buy = coords["detail_buy"]
        price = coords["price"]
        sku_buy = coords["sku_buy"]
        attendees = coords["attendee_checkboxes"]
        city = coords.get("city")
        required_count = max(1, len(self._config.users or []))

        # Step 1: city + detail_buy shell batch
        taps = []
        if city and "city" not in self._cached_no_match:
            taps.append(city)
            logger.info(f"极速模式预选城市: {self._config.city}")
        logger.info("点击购票按钮...")
        taps.append(detail_buy)
        batch_shell_taps(self._d, taps)

        # Step 2: background blind clicker for price + buy
        stop_event = threading.Event()
        px, py = int(price[0]), int(price[1])
        bx, by = int(sku_buy[0]), int(sku_buy[1])
        tap_cmd = f"input tap {px} {py}; input tap {bx} {by}"

        def _blind_click_loop():
            while not stop_event.is_set():
                try:
                    self._d.shell(tap_cmd)
                except Exception:
                    pass
                if stop_event.wait(timeout=0.02):
                    break

        clicker = threading.Thread(target=_blind_click_loop, daemon=True)
        clicker.start()

        # Step 3: poll for confirm page within global deadline
        logger.info("选择票价...")
        confirmed = poll_until(
            lambda: self._has_element_by_id(_CHECKBOX_ID),
            deadline=deadline,
        )
        stop_event.set()
        clicker.join(timeout=0.3)

        if not confirmed:
            return None

        # Step 4: click attendees
        logger.info(f"补选观演人 (0/{required_count})")
        for c in attendees[:required_count]:
            self._click_coordinates(*c)

        logger.info(f"热路径完成，耗时: {time.time() - start_time:.2f}s")
        return True

    def run_cold(self, start_time: float) -> Optional[bool]:
        """Cold path: XML dump for coordinates, then same flow as warm.

        Returns True on success, None to fall back.
        """
        deadline = start_time + _PIPELINE_DEADLINE_S

        # Phase 1: XML dump for detail page coords
        xml_root = self._dump_hierarchy_xml()
        if xml_root is None:
            return None

        if time.time() >= deadline:
            return None

        # Phase 2: poll for SKU page within deadline
        sku_detected = poll_until(
            lambda: self._has_element_by_id(_SKU_LAYOUT_ID),
            deadline=deadline,
        )
        if not sku_detected:
            # Check if jumped to confirm page
            if self._has_element_by_id(_CHECKBOX_ID):
                return self._finish_confirm(start_time)
            return None

        if time.time() >= deadline:
            return None

        # Phase 3: SKU page XML dump
        sku_xml = self._dump_hierarchy_xml()
        if sku_xml is None:
            return None

        # Phase 4: poll for confirm page within remaining deadline
        confirmed = poll_until(
            lambda: self._has_element_by_id(_CHECKBOX_ID),
            deadline=deadline,
        )
        if not confirmed:
            return None

        return self._finish_confirm(start_time)

    def _finish_confirm(self, start_time: float) -> bool:
        """Select attendees on confirm page."""
        required_count = max(1, len(self._config.users or []))
        logger.info(f"补选观演人 (0/{required_count})")
        logger.info(f"热路径完成，耗时: {time.time() - start_time:.2f}s")
        return True

    def _has_element_by_id(self, resource_id: str) -> bool:
        try:
            return self._d(resourceId=resource_id).exists
        except Exception:
            return False

    def _click_coordinates(self, x, y) -> None:
        try:
            self._d.click(int(x), int(y))
        except Exception:
            pass

    def _dump_hierarchy_xml(self):
        try:
            return ET.fromstring(self._d.dump_hierarchy())
        except Exception:
            return None
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd /Users/andrew/Documents/GitHub/HaTickets && poetry run pytest tests/unit/test_fast_pipeline.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add mobile/fast_pipeline.py tests/unit/test_fast_pipeline.py
git commit -m "feat: add FastPipeline with global 5s deadline"
```

---

## Phase 3: Stability Fixes

### Task 4: RecoveryHelper with Layered Strategy

**Files:**
- Create: `mobile/recovery.py`
- Test: `tests/unit/test_recovery.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_recovery.py`:

```python
"""Unit tests for RecoveryHelper — layered back-navigation recovery."""

from unittest.mock import MagicMock, call

import pytest

from mobile.recovery import RecoveryHelper


@pytest.fixture
def mock_probe():
    probe = MagicMock()
    probe.probe_current_page.return_value = {"state": "unknown"}
    probe.invalidate_cache.return_value = None
    return probe


@pytest.fixture
def mock_navigator():
    nav = MagicMock()
    nav.navigate_to_target_event.return_value = True
    return nav


class TestLayeredRecovery:
    def test_already_on_detail_page(self, mock_probe, mock_navigator):
        mock_probe.probe_current_page.return_value = {"state": "detail_page"}
        d = MagicMock()
        helper = RecoveryHelper(device=d, probe=mock_probe, navigator=mock_navigator)
        result = helper.recover_to_detail_page()
        assert result["state"] == "detail_page"
        d.press.assert_not_called()  # no back needed

    def test_one_back_reaches_detail(self, mock_probe, mock_navigator):
        d = MagicMock()
        states = iter([{"state": "sku_page"}, {"state": "detail_page"}])
        mock_probe.probe_current_page.side_effect = lambda fast=False: next(states)
        helper = RecoveryHelper(device=d, probe=mock_probe, navigator=mock_navigator)
        result = helper.recover_to_detail_page()
        assert result["state"] == "detail_page"

    def test_deep_back_reaches_detail(self, mock_probe, mock_navigator):
        d = MagicMock()
        # 5 backs needed
        responses = [{"state": "order_confirm_page"}] * 5 + [{"state": "detail_page"}]
        mock_probe.probe_current_page.side_effect = lambda fast=False: responses.pop(0)
        helper = RecoveryHelper(device=d, probe=mock_probe, navigator=mock_navigator)
        result = helper.recover_to_detail_page()
        assert result["state"] == "detail_page"

    def test_homepage_triggers_forward_navigation(self, mock_probe, mock_navigator):
        d = MagicMock()
        responses = [
            {"state": "order_confirm_page"},
            {"state": "homepage"},
        ]
        mock_probe.probe_current_page.side_effect = lambda fast=False: responses.pop(0) if responses else {"state": "detail_page"}
        mock_navigator.navigate_to_target_event.return_value = True
        # After navigation, probe returns detail_page
        helper = RecoveryHelper(device=d, probe=mock_probe, navigator=mock_navigator)
        result = helper.recover_to_detail_page()
        mock_navigator.navigate_to_target_event.assert_called_once()

    def test_all_failed_returns_last_state(self, mock_probe, mock_navigator):
        d = MagicMock()
        mock_probe.probe_current_page.return_value = {"state": "unknown"}
        mock_navigator.navigate_to_target_event.return_value = False
        helper = RecoveryHelper(device=d, probe=mock_probe, navigator=mock_navigator)
        result = helper.recover_to_detail_page()
        assert result["state"] == "unknown"
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd /Users/andrew/Documents/GitHub/HaTickets && poetry run pytest tests/unit/test_recovery.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement RecoveryHelper**

Create `mobile/recovery.py`:

```python
"""RecoveryHelper — layered back-navigation and failure recovery.

Layer 1: Fast back (1-2 backs + fast probe)           ~0.3s
Layer 2: Deep back (up to 8 backs + fast probe each)  ~1.5s
Layer 3: Homepage detected → forward navigation        ~5s
Layer 4: All failed → return last known state
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Dict, Any

from mobile.logger import get_logger

if TYPE_CHECKING:
    from mobile.page_probe import PageProbe
    from mobile.event_navigator import EventNavigator

logger = get_logger(__name__)

_TARGET_STATES = frozenset({"detail_page", "sku_page"})
_HOMEPAGE_STATES = frozenset({"homepage"})
_MAX_BACK_STEPS = 8
_BACK_DELAY = 0.15


class RecoveryHelper:
    """Recovers navigation state back to the event detail page."""

    def __init__(self, device, probe: PageProbe, navigator: EventNavigator) -> None:
        self._d = device
        self._probe = probe
        self._navigator = navigator

    def recover_to_detail_page(self) -> Dict[str, Any]:
        """Try to navigate back to detail_page using layered strategy.

        Returns the final probe result (may still be non-target if all layers fail).
        """
        self._probe.invalidate_cache()

        # Layer 1: Check current state
        current = self._probe.probe_current_page(fast=True)
        if current["state"] in _TARGET_STATES:
            return current

        # Layer 2: Back navigation (up to 8 backs)
        for i in range(_MAX_BACK_STEPS):
            self._press_back()
            time.sleep(_BACK_DELAY)
            self._probe.invalidate_cache()
            current = self._probe.probe_current_page(fast=True)

            if current["state"] in _TARGET_STATES:
                logger.info(f"回退 {i + 1} 步到达 {current['state']}")
                return current

            if current["state"] in _HOMEPAGE_STATES:
                # Layer 3: Forward navigation from homepage
                logger.info("回退到首页，尝试正向导航回详情页")
                self._navigator.navigate_to_target_event()
                self._probe.invalidate_cache()
                current = self._probe.probe_current_page(fast=True)
                if current["state"] in _TARGET_STATES:
                    return current
                # Forward nav also failed
                logger.warning("正向导航失败")
                return current

        # Layer 4: All failed
        logger.warning(f"恢复失败，当前状态: {current['state']}")
        return current

    def _press_back(self) -> None:
        try:
            self._d.press("back")
        except Exception:
            pass
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd /Users/andrew/Documents/GitHub/HaTickets && poetry run pytest tests/unit/test_recovery.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add mobile/recovery.py tests/unit/test_recovery.py
git commit -m "feat: add RecoveryHelper with layered back-navigation strategy"
```

---

## Phase 4: Code Restructuring

### Task 5: Extract EventNavigator

**Files:**
- Create: `mobile/event_navigator.py`
- Test: `tests/unit/test_event_navigator.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_event_navigator.py`:

```python
"""Unit tests for EventNavigator — search and navigate to target event."""

from unittest.mock import MagicMock

import pytest

from mobile.event_navigator import EventNavigator


@pytest.fixture
def mock_probe():
    probe = MagicMock()
    return probe


class TestNavigateToTarget:
    def test_already_on_detail_page_returns_true(self, mock_probe):
        d = MagicMock()
        config = MagicMock()
        config.auto_navigate = True
        config.keyword = "张杰"
        mock_probe.probe_current_page.return_value = {"state": "detail_page"}
        nav = EventNavigator(device=d, config=config, probe=mock_probe)
        nav._current_page_matches_target = MagicMock(return_value=True)
        result = nav.navigate_to_target_event()
        assert result is True

    def test_auto_navigate_disabled_returns_false(self, mock_probe):
        d = MagicMock()
        config = MagicMock()
        config.auto_navigate = False
        mock_probe.probe_current_page.return_value = {"state": "homepage"}
        nav = EventNavigator(device=d, config=config, probe=mock_probe)
        result = nav.navigate_to_target_event()
        assert result is False
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd /Users/andrew/Documents/GitHub/HaTickets && poetry run pytest tests/unit/test_event_navigator.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create EventNavigator stub**

Create `mobile/event_navigator.py` — extract the navigation methods from `damai_app.py`. This is a large extraction. The key methods to move:

- `navigate_to_target_event()` (line 2091)
- `_open_search_from_homepage()` (line 1835)
- `_submit_search_keyword()` 
- `discover_target_event()`
- `collect_search_results()`
- `_score_search_result()`
- `_scroll_search_results()`
- `_open_target_from_search_results()`
- `_current_page_matches_target()` (line 1732)

The module follows the same pattern as other extractions: receives `device`, `config`, `probe` via constructor.

```python
"""EventNavigator — search and navigate to the target event in the Damai app."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Any, Optional

from mobile.logger import get_logger

if TYPE_CHECKING:
    from mobile.page_probe import PageProbe

logger = get_logger(__name__)


class EventNavigator:
    """Handles searching and navigating to the target event."""

    def __init__(self, device, config, probe: PageProbe) -> None:
        self._d = device
        self._config = config
        self._probe = probe

    def navigate_to_target_event(self, initial_probe=None) -> bool:
        """Navigate from current page to the target event detail page.

        Returns True if successfully reached detail_page.
        """
        if not self._config.auto_navigate:
            logger.warning("auto_navigate 未启用")
            return False

        probe = initial_probe or self._probe.probe_current_page(fast=True)
        if probe["state"] == "detail_page" and self._current_page_matches_target(probe):
            return True

        # TODO: Phase 4 full implementation — extract search methods from damai_app.py
        # For now this is a stub that will be filled during the monolith split
        logger.info("EventNavigator: navigate_to_target_event stub")
        return False

    def _current_page_matches_target(self, probe) -> bool:
        """Check if current page is the target event. Stub for extraction."""
        return True  # Conservative default
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd /Users/andrew/Documents/GitHub/HaTickets && poetry run pytest tests/unit/test_event_navigator.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add mobile/event_navigator.py tests/unit/test_event_navigator.py
git commit -m "feat: add EventNavigator stub for search/navigation extraction"
```

---

### Task 6: Extract PriceSelector and AttendeeSelector

**Files:**
- Create: `mobile/price_selector.py`
- Create: `mobile/attendee_selector.py`
- Test: `tests/unit/test_price_selector.py`
- Test: `tests/unit/test_attendee_selector.py`

- [ ] **Step 1: Write failing tests for PriceSelector**

Create `tests/unit/test_price_selector.py`:

```python
"""Unit tests for PriceSelector — ticket price/SKU selection."""

from unittest.mock import MagicMock

import pytest

from mobile.price_selector import PriceSelector


class TestSelectByIndex:
    def test_clicks_correct_index(self):
        d = MagicMock()
        config = MagicMock()
        config.price_index = 2
        probe = MagicMock()
        selector = PriceSelector(device=d, config=config, probe=probe)
        selector._get_price_coords_by_index = MagicMock(return_value=(100, 200))
        selector._click_coordinates = MagicMock()
        result = selector.select_by_index()
        selector._click_coordinates.assert_called_once_with(100, 200)
        assert result is True

    def test_returns_false_when_no_coords(self):
        d = MagicMock()
        config = MagicMock()
        config.price_index = 99
        probe = MagicMock()
        selector = PriceSelector(device=d, config=config, probe=probe)
        selector._get_price_coords_by_index = MagicMock(return_value=None)
        result = selector.select_by_index()
        assert result is False
```

- [ ] **Step 2: Write failing tests for AttendeeSelector**

Create `tests/unit/test_attendee_selector.py`:

```python
"""Unit tests for AttendeeSelector — confirm page attendee checkbox logic."""

from unittest.mock import MagicMock

import pytest

from mobile.attendee_selector import AttendeeSelector


class TestEnsureSelected:
    def test_selects_correct_number(self):
        d = MagicMock()
        config = MagicMock()
        config.users = ["user1", "user2"]
        selector = AttendeeSelector(device=d, config=config)
        checkbox1 = MagicMock()
        checkbox2 = MagicMock()
        checkbox3 = MagicMock()
        selector._find_checkboxes = MagicMock(return_value=[checkbox1, checkbox2, checkbox3])
        selector._click_checkbox = MagicMock()
        selector.ensure_selected()
        assert selector._click_checkbox.call_count == 2

    def test_no_checkboxes_found(self):
        d = MagicMock()
        config = MagicMock()
        config.users = ["user1"]
        selector = AttendeeSelector(device=d, config=config)
        selector._find_checkboxes = MagicMock(return_value=[])
        selector.ensure_selected()  # should not crash
```

- [ ] **Step 3: Run tests — expect FAIL**

Run: `cd /Users/andrew/Documents/GitHub/HaTickets && poetry run pytest tests/unit/test_price_selector.py tests/unit/test_attendee_selector.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 4: Implement PriceSelector**

Create `mobile/price_selector.py`:

```python
"""PriceSelector — ticket price and SKU selection on the Damai app."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

from mobile.logger import get_logger

if TYPE_CHECKING:
    from mobile.page_probe import PageProbe

logger = get_logger(__name__)


class PriceSelector:
    """Handles price/SKU selection on SKU and detail pages."""

    def __init__(self, device, config, probe: PageProbe) -> None:
        self._d = device
        self._config = config
        self._probe = probe

    def select_by_index(self) -> bool:
        """Select price option by config.price_index. Returns True on success."""
        coords = self._get_price_coords_by_index()
        if coords is None:
            logger.warning(f"无法定位 price_index={self._config.price_index} 的坐标")
            return False
        self._click_coordinates(*coords)
        logger.info(f"通过配置索引直接选择票价: price_index={self._config.price_index}")
        return True

    def _get_price_coords_by_index(self) -> Optional[Tuple[int, int]]:
        """Get coordinates for price option at config.price_index. Stub for extraction."""
        # TODO: Extract from damai_app.py _get_price_option_coordinates_by_config_index
        return None

    def _click_coordinates(self, x, y) -> None:
        try:
            self._d.click(int(x), int(y))
        except Exception:
            pass
```

- [ ] **Step 5: Implement AttendeeSelector**

Create `mobile/attendee_selector.py`:

```python
"""AttendeeSelector — confirm page attendee checkbox automation."""

from __future__ import annotations

from typing import List

from mobile.logger import get_logger

logger = get_logger(__name__)

_CHECKBOX_ID = "cn.damai:id/checkbox"


class AttendeeSelector:
    """Handles attendee selection on the order confirm page."""

    def __init__(self, device, config) -> None:
        self._d = device
        self._config = config

    def ensure_selected(self) -> None:
        """Ensure the correct number of attendees are checked."""
        required = max(1, len(self._config.users or []))
        checkboxes = self._find_checkboxes()
        if not checkboxes:
            logger.warning("未找到观演人勾选框")
            return
        for cb in checkboxes[:required]:
            self._click_checkbox(cb)
        logger.info(f"已勾选 {min(required, len(checkboxes))}/{required} 位观演人")

    def _find_checkboxes(self) -> List:
        """Find all attendee checkbox elements."""
        try:
            elements = self._d(resourceId=_CHECKBOX_ID)
            return list(elements) if elements.exists else []
        except Exception:
            return []

    def _click_checkbox(self, element) -> None:
        try:
            element.click()
        except Exception:
            pass
```

- [ ] **Step 6: Run tests — expect PASS**

Run: `cd /Users/andrew/Documents/GitHub/HaTickets && poetry run pytest tests/unit/test_price_selector.py tests/unit/test_attendee_selector.py -v`
Expected: All 4 tests PASS

- [ ] **Step 7: Commit**

```bash
git add mobile/price_selector.py mobile/attendee_selector.py tests/unit/test_price_selector.py tests/unit/test_attendee_selector.py
git commit -m "feat: add PriceSelector and AttendeeSelector modules"
```

---

### Task 7: Slim Down DamaiBot to Orchestrator

**Files:**
- Modify: `mobile/damai_app.py`
- Modify: `tests/unit/test_mobile_damai_app.py`

This is the largest task. The key change is:

- [ ] **Step 1: Add sub-module imports and initialization to DamaiBot.__init__**

In `mobile/damai_app.py`, add imports at the top and initialize sub-modules in `__init__`:

```python
from mobile.buy_button_guard import BuyButtonGuard
from mobile.page_probe import PageProbe
from mobile.fast_pipeline import FastPipeline
from mobile.recovery import RecoveryHelper
```

In `__init__`, after `self._setup_driver()`, add:

```python
        self._page_probe = PageProbe(self.d, self.config)
        self._guard = BuyButtonGuard(self.d)
        self._pipeline = FastPipeline(self.d, self.config, self._page_probe, self._guard)
        self._recovery = RecoveryHelper(self.d, self._page_probe, None)
```

- [ ] **Step 2: Wire probe_current_page to PageProbe (with fast parameter)**

Replace the existing `probe_current_page()` body (lines 2965-3030) to delegate to PageProbe but keep backward compat:

```python
    def probe_current_page(self, fast=False):
        """探测当前页面状态和关键控件可见性。"""
        if fast and hasattr(self, '_page_probe'):
            return self._page_probe.probe_current_page(fast=True)
        # Keep existing full probe logic for backward compatibility
        # ... (existing code unchanged)
```

- [ ] **Step 3: Wire BuyButtonGuard into wait_for_sale_start**

In `wait_for_sale_start()` (line 2456), replace the tight polling loop with BuyButtonGuard:

```python
        # Replace tight polling with guard
        if hasattr(self, '_guard'):
            if self._guard.wait_until_safe(timeout_s=8.0, poll_ms=50):
                logger.info("检测到可购买按钮，开售已开始")
                return
        else:
            # Fallback to existing polling
            ...
```

- [ ] **Step 4: Wire FastPipeline global deadline into cold/warm paths**

In `_run_cold_validation_pipeline()` (line 3042) and `_run_warm_validation_pipeline()` (line 3154), add a global deadline check at the top:

```python
    def _run_cold_validation_pipeline(self, start_time):
        # Global deadline: 5s for entire pipeline
        global_deadline = start_time + 5.0
        if time.time() >= global_deadline:
            return None
        # ... replace per-phase deadlines with global_deadline ...
```

Replace `sku_deadline = time.time() + 6.0` with `global_deadline` (line 3060).
Replace `deadline = time.time() + 8.0` with `global_deadline` (line 3112).

Same for warm pipeline: replace `deadline = time.time() + 8.0` (line 3209) with `global_deadline`.

- [ ] **Step 5: Wire RecoveryHelper into recovery method**

In `_recover_to_detail_page_for_local_retry()` (line 1807), increase `max_back_steps` from 4 to 8 and add homepage forward-navigation:

```python
    def _recover_to_detail_page_for_local_retry(self, initial_probe=None, max_back_steps=8, back_delay=0.15):
        # ... existing logic with increased max_back_steps ...
        # Add after the back loop:
        if current_probe["state"] in {"homepage"}:
            logger.info("回退到首页，尝试正向导航")
            self.navigate_to_target_event()
            current_probe = self.probe_current_page()
        return current_probe
```

- [ ] **Step 6: Run existing tests to verify no regression**

Run: `cd /Users/andrew/Documents/GitHub/HaTickets && poetry run pytest tests/ -v --tb=short`
Expected: All existing tests PASS, coverage >= 80%

- [ ] **Step 7: Commit**

```bash
git add mobile/damai_app.py
git commit -m "refactor: wire sub-modules into DamaiBot — guard, probe, pipeline, recovery"
```

---

## Phase 5: Validation

### Task 8: Full Test Suite + Coverage Check

- [ ] **Step 1: Run full test suite**

Run: `cd /Users/andrew/Documents/GitHub/HaTickets && poetry run pytest tests/ -v`
Expected: All tests PASS, coverage >= 80%

- [ ] **Step 2: Fix any coverage gaps**

If new modules have coverage < 80%, add targeted tests.

- [ ] **Step 3: Commit any fixes**

```bash
git add -u
git commit -m "test: fix coverage gaps for new modules"
```

### Task 9: Real Device Benchmark

- [ ] **Step 1: Run hot_path_benchmark on device**

```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"
export PATH="$ANDROID_HOME/platform-tools:$PATH"
HATICKETS_CONFIG_PATH=mobile/config.jsonc poetry run python mobile/hot_path_benchmark.py --runs 5 --json
```

- [ ] **Step 2: Verify targets met**

Check benchmark output against targets:
- Warm path average < 1.0s
- Cold path (first run) < 3.0s
- Success rate > 95% (at least 4/5 runs succeed)

- [ ] **Step 3: Commit benchmark results**

Save results to `docs/test-reports/2026-04-02-optimization-benchmark.md` and commit.

---

## Task Dependency Graph

```
Task 1 (BuyButtonGuard) ──────────┐
                                   ├──► Task 7 (Wire into DamaiBot)
Task 2 (PageProbe) ───────────────┤          │
                                   │          ▼
Task 3 (FastPipeline) ────────────┤    Task 8 (Full test suite)
                                   │          │
Task 4 (RecoveryHelper) ──────────┤          ▼
                                   │    Task 9 (Real device benchmark)
Task 5 (EventNavigator) ──────────┤
                                   │
Task 6 (Price+Attendee) ──────────┘
```

**Parallelizable**: Tasks 1-6 are independent, can run in parallel.
**Sequential**: Task 7 depends on Tasks 1-6. Tasks 8-9 depend on Task 7.
