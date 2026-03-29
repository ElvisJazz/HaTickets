# -*- coding: UTF-8 -*-
"""Unit tests for mobile/damai_app.py — DamaiBot class."""

import time as _time_module
from datetime import datetime, timezone, timedelta

import pytest
from unittest.mock import Mock, patch, call, PropertyMock

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By

from mobile.damai_app import DamaiBot, logger as damai_logger
from mobile.config import Config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_mock_element(x=100, y=200, width=50, height=40):
    """Helper: create a mock element with a .rect property."""
    el = Mock()
    el.rect = {"x": x, "y": y, "width": width, "height": height}
    el.id = "fake-element-id"
    return el


@pytest.fixture(autouse=True)
def _enable_logger_propagation():
    """Enable propagation on the damai_app logger so caplog can capture messages."""
    damai_logger.propagate = True
    yield
    damai_logger.propagate = False


@pytest.fixture
def bot():
    """Create a DamaiBot with fully mocked Appium driver and config."""
    mock_driver = Mock()
    mock_driver.update_settings = Mock()
    mock_driver.execute_script = Mock()
    mock_driver.find_element = Mock()
    mock_driver.find_elements = Mock(return_value=[])
    mock_driver.quit = Mock()
    mock_driver.current_activity = "ProjectDetailActivity"

    mock_config = Config(
        server_url="http://127.0.0.1:4723",
        device_name="Android",
        udid=None,
        platform_version=None,
        app_package="cn.damai",
        app_activity=".launcher.splash.SplashMainActivity",
        keyword="test",
        users=["UserA", "UserB"],
        city="深圳",
        date="12.06",
        price="799元",
        price_index=1,
        if_commit_order=True,
        probe_only=False,
    )

    with patch("mobile.damai_app.Config.load_config", return_value=mock_config), \
         patch("mobile.damai_app.webdriver.Remote", return_value=mock_driver), \
         patch("mobile.damai_app.AppiumOptions"):
        bot = DamaiBot()
    return bot


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInitialization:
    def test_init_loads_config_and_driver(self, bot):
        """Config is loaded and driver is created during __init__."""
        assert bot.config is not None
        assert bot.config.city == "深圳"
        assert bot.config.users == ["UserA", "UserB"]
        assert bot.driver is not None

    def test_setup_driver_sets_wait(self, bot):
        """_setup_driver sets self.wait (WebDriverWait instance)."""
        assert bot.wait is not None
        # update_settings was called during setup
        bot.driver.update_settings.assert_called_once()

    def test_build_capabilities_uses_real_device_config(self):
        mock_driver = Mock()
        mock_driver.update_settings = Mock()

        mock_config = Config(
            server_url="http://127.0.0.1:4723",
            device_name="Pixel 8",
            udid="R58M123456A",
            platform_version="14",
            app_package="cn.damai",
            app_activity=".launcher.splash.SplashMainActivity",
            keyword="test",
            users=["UserA"],
            city="深圳",
            date="12.06",
            price="799元",
            price_index=1,
            if_commit_order=True,
            probe_only=False,
        )

        with patch("mobile.damai_app.Config.load_config", return_value=mock_config), \
             patch("mobile.damai_app.webdriver.Remote", return_value=mock_driver), \
             patch("mobile.damai_app.AppiumOptions"):
            bot = DamaiBot()

        capabilities = bot._build_capabilities()
        assert capabilities["deviceName"] == "Pixel 8"
        assert capabilities["udid"] == "R58M123456A"
        assert capabilities["platformVersion"] == "14"
        assert capabilities["appPackage"] == "cn.damai"
        assert capabilities["appActivity"] == ".launcher.splash.SplashMainActivity"


# ---------------------------------------------------------------------------
# ultra_fast_click
# ---------------------------------------------------------------------------

class TestUltraFastClick:
    def test_ultra_fast_click_success(self, bot):
        """Element found, gesture click executed with center coords, returns True."""
        mock_el = _make_mock_element(x=100, y=200, width=50, height=40)

        with patch("mobile.damai_app.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_el
            result = bot.ultra_fast_click("by", "value")

        assert result is True
        bot.driver.execute_script.assert_called_once_with(
            "mobile: clickGesture",
            {"x": 125, "y": 220, "duration": 50},
        )

    def test_ultra_fast_click_timeout(self, bot):
        """WebDriverWait raises TimeoutException, returns False."""
        with patch("mobile.damai_app.WebDriverWait") as MockWait:
            MockWait.return_value.until.side_effect = TimeoutException("timeout")
            result = bot.ultra_fast_click("by", "value")

        assert result is False


# ---------------------------------------------------------------------------
# batch_click
# ---------------------------------------------------------------------------

class TestBatchClick:
    def test_batch_click_all_success(self, bot):
        """ultra_fast_click called for each element pair."""
        elements = [("by1", "v1"), ("by2", "v2"), ("by3", "v3")]
        with patch.object(bot, "ultra_fast_click", return_value=True) as ufc, \
             patch("mobile.damai_app.time") as mock_time:
            bot.batch_click(elements, delay=0.1)

        assert ufc.call_count == 3
        ufc.assert_any_call("by1", "v1")
        ufc.assert_any_call("by2", "v2")
        ufc.assert_any_call("by3", "v3")

    def test_batch_click_some_fail(self, bot, caplog):
        """Failed clicks log a warning but processing continues."""
        elements = [("by1", "v1"), ("by2", "v2")]
        with caplog.at_level("WARNING", logger="mobile.damai_app"), \
             patch.object(bot, "ultra_fast_click", side_effect=[False, True]) as ufc, \
             patch("mobile.damai_app.time"):
            bot.batch_click(elements, delay=0.1)

        assert ufc.call_count == 2
        assert "点击失败: v1" in caplog.text


# ---------------------------------------------------------------------------
# ultra_batch_click
# ---------------------------------------------------------------------------

class TestUltraBatchClick:
    def test_ultra_batch_click_collects_and_clicks(self, bot, caplog):
        """Coordinates collected for all elements, then clicked sequentially."""
        el1 = _make_mock_element(x=10, y=20, width=100, height=50)
        el2 = _make_mock_element(x=200, y=300, width=60, height=30)

        with caplog.at_level("DEBUG", logger="mobile.damai_app"), \
             patch("mobile.damai_app.WebDriverWait") as MockWait, \
             patch("mobile.damai_app.time"):
            MockWait.return_value.until.side_effect = [el1, el2]
            bot.ultra_batch_click([("by1", "v1"), ("by2", "v2")], timeout=2)

        # Two clickGesture calls with correct center coordinates
        calls = bot.driver.execute_script.call_args_list
        assert len(calls) == 2
        assert calls[0] == call("mobile: clickGesture", {"x": 60, "y": 45, "duration": 30})
        assert calls[1] == call("mobile: clickGesture", {"x": 230, "y": 315, "duration": 30})

        assert "成功找到 2 个用户" in caplog.text

    def test_ultra_batch_click_timeout_skips(self, bot, caplog):
        """Timed-out elements are skipped; found ones are still clicked."""
        el1 = _make_mock_element(x=10, y=20, width=100, height=50)

        with caplog.at_level("DEBUG", logger="mobile.damai_app"), \
             patch("mobile.damai_app.WebDriverWait") as MockWait, \
             patch("mobile.damai_app.time"):
            MockWait.return_value.until.side_effect = [
                el1,
                TimeoutException("timeout"),
            ]
            bot.ultra_batch_click([("by1", "v1"), ("by2", "v2")], timeout=2)

        # Only 1 click executed (the successful one)
        assert bot.driver.execute_script.call_count == 1
        assert "超时未找到用户: v2" in caplog.text
        assert "成功找到 1 个用户" in caplog.text


# ---------------------------------------------------------------------------
# smart_wait_and_click
# ---------------------------------------------------------------------------

class TestSmartWaitAndClick:
    def test_smart_wait_and_click_primary_success(self, bot):
        """Primary selector works on first try, returns True."""
        mock_el = _make_mock_element()
        with patch("mobile.damai_app.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_el
            result = bot.smart_wait_and_click("by", "value")

        assert result is True
        bot.driver.execute_script.assert_called_once()

    def test_smart_wait_and_click_backup_success(self, bot):
        """Primary fails (TimeoutException), backup selector works."""
        mock_el = _make_mock_element()
        with patch("mobile.damai_app.WebDriverWait") as MockWait:
            MockWait.return_value.until.side_effect = [
                TimeoutException("primary failed"),
                mock_el,
            ]
            result = bot.smart_wait_and_click(
                "by", "value",
                backup_selectors=[("by2", "backup_value")],
            )

        assert result is True

    def test_smart_wait_and_click_all_fail(self, bot):
        """All selectors (primary + backups) fail, returns False."""
        with patch("mobile.damai_app.WebDriverWait") as MockWait:
            MockWait.return_value.until.side_effect = TimeoutException("fail")
            result = bot.smart_wait_and_click(
                "by", "value",
                backup_selectors=[("by2", "v2"), ("by3", "v3")],
            )

        assert result is False

    def test_smart_wait_and_click_no_backups(self, bot):
        """Only primary selector, fails, returns False."""
        with patch("mobile.damai_app.WebDriverWait") as MockWait:
            MockWait.return_value.until.side_effect = TimeoutException("fail")
            result = bot.smart_wait_and_click("by", "value")

        assert result is False


# ---------------------------------------------------------------------------
# run_ticket_grabbing
# ---------------------------------------------------------------------------

class TestRunTicketGrabbing:
    def test_run_ticket_grabbing_returns_false_when_not_detail_page(self, bot):
        """Homepage or other non-detail states fail fast with a clear result."""
        with patch.object(bot, "dismiss_startup_popups"), \
             patch.object(bot, "probe_current_page", return_value={
                 "state": "homepage",
                 "purchase_button": False,
                 "price_container": False,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch.object(bot, "smart_wait_and_click") as smart_click, \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.return_value = 0.0
            result = bot.run_ticket_grabbing()

        assert result is False
        smart_click.assert_not_called()

    def test_run_ticket_grabbing_probe_only_returns_true_when_detail_ready(self, bot):
        """probe_only stops before purchase when detail-page essentials are present."""
        bot.config.probe_only = True

        with patch.object(bot, "dismiss_startup_popups"), \
             patch.object(bot, "probe_current_page", return_value={
                 "state": "detail_page",
                 "purchase_button": True,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch.object(bot, "smart_wait_and_click") as smart_click, \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.side_effect = [0.0, 0.1]
            result = bot.run_ticket_grabbing()

        assert result is True
        smart_click.assert_not_called()

    def test_run_ticket_grabbing_probe_only_returns_false_when_detail_incomplete(self, bot):
        """probe_only reports failure when detail-page essentials are missing."""
        bot.config.probe_only = True

        with patch.object(bot, "dismiss_startup_popups"), \
             patch.object(bot, "probe_current_page", return_value={
                 "state": "detail_page",
                 "purchase_button": False,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.return_value = 0.0
            result = bot.run_ticket_grabbing()

        assert result is False

    def test_run_ticket_grabbing_probe_only_returns_true_when_sku_page_ready(self, bot):
        """probe_only succeeds when the ticket sku page is already open."""
        bot.config.probe_only = True

        with patch.object(bot, "dismiss_startup_popups"), \
             patch.object(bot, "probe_current_page", return_value={
                 "state": "sku_page",
                 "purchase_button": False,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch.object(bot, "smart_wait_and_click") as smart_click, \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.side_effect = [0.0, 0.1]
            result = bot.run_ticket_grabbing()

        assert result is True
        smart_click.assert_not_called()

    def test_run_ticket_grabbing_success(self, bot):
        """All phases succeed, returns True."""
        with patch.object(bot, "dismiss_startup_popups"), \
             patch.object(bot, "probe_current_page", return_value={
                 "state": "detail_page",
                 "purchase_button": True,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch.object(bot, "wait_for_sale_start"), \
             patch.object(bot, "wait_for_page_state", return_value={
                 "state": "order_confirm_page",
                 "purchase_button": False,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": True,
             }), \
             patch.object(bot, "smart_wait_and_click", return_value=True), \
             patch.object(bot, "ultra_fast_click", return_value=True), \
             patch.object(bot, "ultra_batch_click"), \
             patch.object(bot, "verify_order_result", return_value="success"), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.side_effect = [0.0, 1.5]
            # Mock find_element for price container + target_price
            mock_price_container = Mock()
            mock_target = _make_mock_element()
            mock_price_container.find_element.return_value = mock_target
            bot.driver.find_element.return_value = mock_price_container
            bot.driver.find_elements.return_value = []  # no quantity layout

            result = bot.run_ticket_grabbing()

        assert result is True

    def test_run_ticket_grabbing_stops_before_submit_when_commit_disabled(self, bot):
        """if_commit_order=False waits for confirm page but never clicks submit."""
        bot.config.if_commit_order = False

        with patch.object(bot, "dismiss_startup_popups"), \
             patch.object(bot, "probe_current_page", return_value={
                 "state": "detail_page",
                 "purchase_button": True,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch.object(bot, "wait_for_sale_start"), \
             patch.object(bot, "wait_for_page_state", return_value={
                 "state": "order_confirm_page",
                 "purchase_button": False,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": True,
             }), \
             patch.object(bot, "smart_wait_and_click", return_value=True) as smart_click, \
             patch.object(bot, "smart_wait_for_element", return_value=True) as wait_for_element, \
             patch.object(bot, "ultra_fast_click", return_value=True), \
             patch.object(bot, "ultra_batch_click"), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.side_effect = [0.0, 1.2]
            mock_price_container = Mock()
            mock_target = _make_mock_element()
            mock_price_container.find_element.return_value = mock_target
            bot.driver.find_element.return_value = mock_price_container
            bot.driver.find_elements.return_value = []

            result = bot.run_ticket_grabbing()

        assert result is True
        assert smart_click.call_count == 2
        wait_for_element.assert_called_once()

    def test_run_ticket_grabbing_continues_from_sku_page_when_commit_disabled(self, bot):
        """sku_page can continue directly to confirm page without returning to detail."""
        bot.config.if_commit_order = False

        with patch.object(bot, "dismiss_startup_popups"), \
             patch.object(bot, "probe_current_page", return_value={
                 "state": "sku_page",
                 "purchase_button": False,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch.object(bot, "wait_for_sale_start"), \
             patch.object(bot, "wait_for_page_state", return_value={
                 "state": "order_confirm_page",
                 "purchase_button": False,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": True,
             }), \
             patch.object(bot, "smart_wait_and_click") as smart_click, \
             patch.object(bot, "smart_wait_for_element", return_value=True) as wait_for_element, \
             patch.object(bot, "ultra_fast_click", return_value=True), \
             patch.object(bot, "ultra_batch_click"), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.side_effect = [0.0, 0.8]
            mock_price_container = Mock()
            mock_target = _make_mock_element()
            mock_price_container.find_element.return_value = mock_target
            bot.driver.find_element.return_value = mock_price_container
            bot.driver.find_elements.return_value = []

            result = bot.run_ticket_grabbing()

        assert result is True
        smart_click.assert_not_called()
        wait_for_element.assert_called_once()

    def test_run_ticket_grabbing_returns_false_when_confirm_page_not_ready_and_commit_disabled(self, bot, caplog):
        """Commit-disabled mode fails safely if the confirm page never becomes ready."""
        bot.config.if_commit_order = False

        with caplog.at_level("WARNING", logger="mobile.damai_app"), \
             patch.object(bot, "dismiss_startup_popups"), \
             patch.object(bot, "probe_current_page", return_value={
                 "state": "detail_page",
                 "purchase_button": True,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch.object(bot, "wait_for_sale_start"), \
             patch.object(bot, "wait_for_page_state", return_value={
                 "state": "sku_page",
                 "purchase_button": False,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch.object(bot, "smart_wait_and_click", return_value=True), \
             patch.object(bot, "smart_wait_for_element", return_value=False), \
             patch.object(bot, "ultra_fast_click", return_value=True), \
             patch.object(bot, "ultra_batch_click"), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.return_value = 0.0
            mock_price_container = Mock()
            mock_target = _make_mock_element()
            mock_price_container.find_element.return_value = mock_target
            bot.driver.find_element.return_value = mock_price_container
            bot.driver.find_elements.return_value = []

            result = bot.run_ticket_grabbing()

        assert result is False
        assert "未进入订单确认页" in caplog.text

    def test_run_ticket_grabbing_city_fail(self, bot):
        """City selection fails, returns False immediately."""
        with patch.object(bot, "dismiss_startup_popups"), \
             patch.object(bot, "probe_current_page", return_value={
                 "state": "detail_page",
                 "purchase_button": True,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch.object(bot, "wait_for_sale_start"), \
             patch.object(bot, "smart_wait_and_click", return_value=False), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.return_value = 0.0
            result = bot.run_ticket_grabbing()

        assert result is False

    def test_run_ticket_grabbing_book_fail(self, bot):
        """Booking button fails, returns False."""
        with patch.object(bot, "dismiss_startup_popups"), \
             patch.object(bot, "probe_current_page", return_value={
                 "state": "detail_page",
                 "purchase_button": True,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch.object(bot, "wait_for_sale_start"), \
             patch.object(bot, "smart_wait_and_click", side_effect=[True, False]), \
             patch.object(bot, "ultra_fast_click", return_value=True), \
             patch.object(bot, "ultra_batch_click"), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.return_value = 0.0
            # Mock price container
            mock_price_container = Mock()
            mock_target = _make_mock_element()
            mock_price_container.find_element.return_value = mock_target
            bot.driver.find_element.return_value = mock_price_container
            bot.driver.find_elements.return_value = []

            result = bot.run_ticket_grabbing()

        assert result is False

    def test_run_ticket_grabbing_price_exception_tries_backup(self, bot):
        """First price attempt raises, backup via wait.until succeeds."""
        mock_price_container = Mock()
        mock_target = _make_mock_element()
        mock_price_container.find_element.return_value = mock_target

        with patch.object(bot, "dismiss_startup_popups"), \
             patch.object(bot, "probe_current_page", return_value={
                 "state": "detail_page",
                 "purchase_button": True,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch.object(bot, "wait_for_sale_start"), \
             patch.object(bot, "wait_for_page_state", return_value={
                 "state": "order_confirm_page",
                 "purchase_button": False,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": True,
             }), \
             patch.object(bot, "smart_wait_and_click", return_value=True), \
             patch.object(bot, "ultra_fast_click", return_value=True), \
             patch.object(bot, "ultra_batch_click"), \
             patch.object(bot, "verify_order_result", return_value="success"), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.side_effect = [0.0, 2.0]
            # First find_element raises, triggering backup path
            bot.driver.find_element.side_effect = NoSuchElementException("not found")
            bot.wait.until = Mock(return_value=mock_price_container)
            bot.driver.find_elements.return_value = []

            result = bot.run_ticket_grabbing()

        assert result is True
        # Backup path used wait.until
        bot.wait.until.assert_called_once()

    def test_run_ticket_grabbing_exception_returns_false(self, bot):
        """Unexpected exception in flow returns False."""
        with patch.object(bot, "dismiss_startup_popups"), \
             patch.object(bot, "probe_current_page", return_value={
                 "state": "detail_page",
                 "purchase_button": True,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch.object(bot, "wait_for_sale_start"), \
             patch.object(bot, "smart_wait_and_click", side_effect=RuntimeError("boom")), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.return_value = 0.0
            result = bot.run_ticket_grabbing()

        assert result is False

    def test_run_ticket_grabbing_submit_warns_on_failure(self, bot, caplog):
        """Submit button fails but function still returns True (warning logged)."""
        call_count = [0]

        def smart_click_side_effect(*args, **kwargs):
            call_count[0] += 1
            # 1st call = city, 2nd = book button, 3rd = submit
            if call_count[0] == 3:
                return False  # submit fails
            return True

        with caplog.at_level("WARNING", logger="mobile.damai_app"), \
             patch.object(bot, "dismiss_startup_popups"), \
             patch.object(bot, "probe_current_page", return_value={
                 "state": "detail_page",
                 "purchase_button": True,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch.object(bot, "wait_for_sale_start"), \
             patch.object(bot, "wait_for_page_state", return_value={
                 "state": "order_confirm_page",
                 "purchase_button": False,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": True,
             }), \
             patch.object(bot, "smart_wait_and_click", side_effect=smart_click_side_effect), \
             patch.object(bot, "ultra_fast_click", return_value=True), \
             patch.object(bot, "ultra_batch_click"), \
             patch.object(bot, "verify_order_result", return_value="timeout"), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.side_effect = [0.0, 1.0]
            mock_price_container = Mock()
            mock_target = _make_mock_element()
            mock_price_container.find_element.return_value = mock_target
            bot.driver.find_element.return_value = mock_price_container
            bot.driver.find_elements.return_value = []

            result = bot.run_ticket_grabbing()

        assert result is True
        assert "提交订单按钮未找到" in caplog.text

    def test_run_ticket_grabbing_no_driver_quit_in_finally(self, bot):
        """Verify driver.quit is NOT called inside run_ticket_grabbing's finally block."""
        with patch.object(bot, "dismiss_startup_popups"), \
             patch.object(bot, "probe_current_page", return_value={
                 "state": "detail_page",
                 "purchase_button": True,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch.object(bot, "wait_for_sale_start"), \
             patch.object(bot, "smart_wait_and_click", return_value=False), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.return_value = 0.0
            bot.run_ticket_grabbing()

        bot.driver.quit.assert_not_called()

    def test_run_ticket_grabbing_skips_user_click_when_order_confirm_page_directly_opened(self, bot):
        """Direct jump to order confirm page should skip manual user selection."""
        bot.config.if_commit_order = False

        with patch.object(bot, "dismiss_startup_popups"), \
             patch.object(bot, "probe_current_page", return_value={
                 "state": "sku_page",
                 "purchase_button": False,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch.object(bot, "wait_for_sale_start"), \
             patch.object(bot, "wait_for_page_state", return_value={
                 "state": "order_confirm_page",
                 "purchase_button": False,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": True,
             }), \
             patch.object(bot, "smart_wait_for_element", return_value=True), \
             patch.object(bot, "ultra_fast_click", return_value=True), \
             patch.object(bot, "ultra_batch_click") as batch_click, \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.side_effect = [0.0, 0.8]
            mock_price_container = Mock()
            mock_target = _make_mock_element()
            mock_price_container.find_element.return_value = mock_target
            bot.driver.find_element.return_value = mock_price_container
            bot.driver.find_elements.return_value = []

            result = bot.run_ticket_grabbing()

        assert result is True
        batch_click.assert_not_called()


class TestPageStateHelpers:
    def test_probe_current_page_detects_homepage(self, bot):
        with patch.object(
            bot,
            "_has_element",
            side_effect=lambda by, value: (by, value) == (By.ID, "cn.damai:id/homepage_header_search"),
        ), patch.object(bot, "_get_current_activity", return_value=""):
            result = bot.probe_current_page()

            assert result["state"] == "homepage"
            assert result["purchase_button"] is False

    def test_probe_current_page_detects_search_activity(self, bot):
        with patch.object(bot, "_has_element", return_value=False), \
             patch.object(bot, "_get_current_activity", return_value="com.alibaba.pictures.bricks.search.v2.SearchActivity"):
            result = bot.probe_current_page()

            assert result["state"] == "search_page"
            assert result["purchase_button"] is False

    def test_probe_current_page_detects_detail_page_by_activity_and_summary_price(self, bot):
        present = {
            (By.ID, "cn.damai:id/project_detail_price_layout"),
        }

        with patch.object(bot, "_has_element", side_effect=lambda by, value: (by, value) in present), \
             patch.object(bot, "_get_current_activity", return_value=".trade.newtradeorder.ui.projectdetail.ui.activity.ProjectDetailActivity"):
            result = bot.probe_current_page()

            assert result["state"] == "detail_page"
            assert result["purchase_button"] is False
            assert result["price_container"] is True

    def test_probe_current_page_detects_sku_page(self, bot):
        present = {
            (By.ID, "cn.damai:id/project_detail_perform_price_flowlayout"),
            (By.ID, "cn.damai:id/layout_sku"),
        }

        with patch.object(bot, "_has_element", side_effect=lambda by, value: (by, value) in present), \
             patch.object(bot, "_get_current_activity", return_value=".commonbusiness.seatbiz.sku.qilin.ui.NcovSkuActivity"):
            result = bot.probe_current_page()

            assert result["state"] == "sku_page"
            assert result["price_container"] is True

    def test_probe_current_page_detects_detail_page_controls(self, bot):
        present = {
            (By.ID, "cn.damai:id/trade_project_detail_purchase_status_bar_container_fl"),
            (By.ID, "cn.damai:id/project_detail_perform_price_flowlayout"),
            (By.ID, "layout_num"),
            (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("立即提交")'),
        }

        with patch.object(bot, "_has_element", side_effect=lambda by, value: (by, value) in present), \
             patch.object(bot, "_get_current_activity", return_value=""):
            result = bot.probe_current_page()

            assert result["state"] == "order_confirm_page"
            assert result["purchase_button"] is True
            assert result["price_container"] is True
            assert result["quantity_picker"] is True
            assert result["submit_button"] is True

    def test_dismiss_startup_popups_clicks_known_popups(self, bot):
        present = {
            (By.ID, "android:id/ok"),
            (By.ID, "cn.damai:id/id_boot_action_agree"),
            (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Cancel")'),
        }

        with patch.object(bot, "_has_element", side_effect=lambda by, value: (by, value) in present), \
             patch.object(bot, "ultra_fast_click", return_value=True) as fast_click, \
             patch("mobile.damai_app.time.sleep"):
            result = bot.dismiss_startup_popups()

            assert result is True
            fast_click.assert_any_call(By.ID, "android:id/ok")
            fast_click.assert_any_call(By.ID, "cn.damai:id/id_boot_action_agree")
            fast_click.assert_any_call(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Cancel")')


# ---------------------------------------------------------------------------
# run_with_retry
# ---------------------------------------------------------------------------

class TestRunWithRetry:
    def test_run_with_retry_success_first_attempt(self, bot):
        """Succeeds on first attempt, returns True immediately."""
        with patch.object(bot, "run_ticket_grabbing", return_value=True), \
             patch("mobile.damai_app.time"):
            result = bot.run_with_retry(max_retries=3)

        assert result is True

    def test_run_with_retry_success_second_attempt(self, bot):
        """Fails once, sets up driver again, succeeds second time."""
        with patch.object(bot, "run_ticket_grabbing", side_effect=[False, True]), \
             patch.object(bot, "_fast_retry_from_current_state", return_value=False), \
             patch.object(bot, "_setup_driver") as mock_setup, \
             patch("mobile.damai_app.time"):
            result = bot.run_with_retry(max_retries=3)

        assert result is True
        mock_setup.assert_called_once()

    def test_run_with_retry_all_fail(self, bot):
        """All retries fail, returns False."""
        with patch.object(bot, "run_ticket_grabbing", return_value=False), \
             patch.object(bot, "_fast_retry_from_current_state", return_value=False), \
             patch.object(bot, "_setup_driver"), \
             patch("mobile.damai_app.time"):
            result = bot.run_with_retry(max_retries=3)

        assert result is False

    def test_run_with_retry_driver_quit_between_retries(self, bot):
        """Between retries, driver.quit and _setup_driver are called."""
        with patch.object(bot, "run_ticket_grabbing", side_effect=[False, False, True]), \
             patch.object(bot, "_fast_retry_from_current_state", return_value=False), \
             patch.object(bot, "_setup_driver") as mock_setup, \
             patch("mobile.damai_app.time"):
            bot.run_with_retry(max_retries=3)

        # quit called before each retry (2 failures, but last one succeeds so only 2 quit calls)
        assert bot.driver.quit.call_count == 2
        assert mock_setup.call_count == 2

    def test_run_with_retry_quit_exception_handled(self, bot):
        """driver.quit raises an exception, handled by except block."""
        bot.driver.quit.side_effect = Exception("quit failed")

        with patch.object(bot, "run_ticket_grabbing", side_effect=[False, True]), \
             patch.object(bot, "_setup_driver") as mock_setup, \
             patch.object(bot, "_fast_retry_from_current_state", return_value=False), \
             patch("mobile.damai_app.time"):
            result = bot.run_with_retry(max_retries=3)

        # Despite quit failure, retry continued and succeeded
        assert result is True

    def test_run_with_retry_uses_fast_retry(self, bot):
        """Verify fast retry is attempted before driver recreation."""
        with patch.object(bot, "run_ticket_grabbing", side_effect=[False, False]), \
             patch.object(bot, "_fast_retry_from_current_state", return_value=False) as fast_retry, \
             patch.object(bot, "_setup_driver"), \
             patch("mobile.damai_app.time"):
            bot.run_with_retry(max_retries=2)

        # fast_retry called fast_retry_count times per failed attempt
        assert fast_retry.call_count == bot.config.fast_retry_count * 2


# ---------------------------------------------------------------------------
# wait_for_sale_start
# ---------------------------------------------------------------------------

class TestWaitForSaleStart:
    def test_wait_for_sale_start_no_config(self, bot):
        """sell_start_time=None, returns immediately without sleeping."""
        bot.config.sell_start_time = None
        with patch("mobile.damai_app.time.sleep") as mock_sleep:
            bot.wait_for_sale_start()
        mock_sleep.assert_not_called()

    def test_wait_for_sale_start_already_passed(self, bot):
        """Time in past, returns immediately."""
        bot.config.sell_start_time = "2020-01-01T10:00:00+08:00"
        with patch("mobile.damai_app.time.sleep") as mock_sleep:
            bot.wait_for_sale_start()
        mock_sleep.assert_not_called()

    def test_wait_for_sale_start_waits_and_polls(self, bot):
        """Mock time so sale is in future, verify sleep called, then polling finds button."""
        _tz = timezone(timedelta(hours=8))
        # Sale starts 10 seconds from "now"
        future_time = datetime(2026, 6, 1, 20, 0, 10, tzinfo=_tz)
        bot.config.sell_start_time = future_time.isoformat()
        bot.config.countdown_lead_ms = 3000

        # Track datetime.now calls: first returns "now" (10s before sale),
        # then returns times during polling
        now_base = datetime(2026, 6, 1, 20, 0, 0, tzinfo=_tz)
        now_calls = [0]

        def mock_now(tz=None):
            now_calls[0] += 1
            if now_calls[0] <= 2:
                # Initial check + sleep calculation
                return now_base
            # During polling, return past the sale time
            return future_time + timedelta(seconds=1)

        with patch("mobile.damai_app.datetime") as mock_dt, \
             patch("mobile.damai_app.time.sleep") as mock_sleep, \
             patch.object(bot, "_has_element", return_value=True):
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.now = mock_now
            bot.wait_for_sale_start()

        # Should have slept for the wait period (10s - 3s lead = 7s)
        assert mock_sleep.call_count >= 1
        # First sleep should be ~7 seconds
        first_sleep_arg = mock_sleep.call_args_list[0][0][0]
        assert 6.5 < first_sleep_arg < 7.5


# ---------------------------------------------------------------------------
# _fast_retry_from_current_state
# ---------------------------------------------------------------------------

class TestFastRetry:
    def test_fast_retry_from_detail_page(self, bot):
        """probe returns detail_page, re-runs full flow."""
        with patch.object(bot, "probe_current_page", return_value={
                "state": "detail_page",
                "purchase_button": True,
                "price_container": True,
                "quantity_picker": False,
                "submit_button": False,
             }), \
             patch.object(bot, "run_ticket_grabbing", return_value=True) as run_tg:
            result = bot._fast_retry_from_current_state()

        assert result is True
        run_tg.assert_called_once()

    def test_fast_retry_from_order_confirm_page(self, bot):
        """probe returns order_confirm_page, re-attempts submit only."""
        with patch.object(bot, "probe_current_page", return_value={
                "state": "order_confirm_page",
                "purchase_button": False,
                "price_container": False,
                "quantity_picker": False,
                "submit_button": True,
             }), \
             patch.object(bot, "smart_wait_and_click", return_value=True) as smart_click:
            result = bot._fast_retry_from_current_state()

        assert result is True
        smart_click.assert_called_once()

    def test_fast_retry_from_unknown_presses_back(self, bot):
        """probe returns unknown, press_keycode(4) called, then re-runs flow."""
        with patch.object(bot, "probe_current_page", return_value={
                "state": "unknown",
                "purchase_button": False,
                "price_container": False,
                "quantity_picker": False,
                "submit_button": False,
             }), \
             patch.object(bot, "run_ticket_grabbing", return_value=False) as run_tg, \
             patch("mobile.damai_app.time.sleep"):
            result = bot._fast_retry_from_current_state()

        bot.driver.press_keycode.assert_called_once_with(4)
        run_tg.assert_called_once()
        assert result is False


# ---------------------------------------------------------------------------
# verify_order_result
# ---------------------------------------------------------------------------

class TestVerifyOrderResult:
    def test_verify_order_success_payment_activity(self, bot):
        """Activity contains 'Pay', returns 'success'."""
        with patch.object(bot, "_get_current_activity", return_value="com.alipay.android.app.PayActivity"), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.side_effect = [0.0, 0.1]
            result = bot.verify_order_result(timeout=5)

        assert result == "success"

    def test_verify_order_success_payment_text(self, bot):
        """Element contains '支付', returns 'success'."""
        def has_element_side_effect(by, value):
            return '支付' in value

        with patch.object(bot, "_get_current_activity", return_value="SomeActivity"), \
             patch.object(bot, "_has_element", side_effect=has_element_side_effect), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.side_effect = [0.0, 0.1]
            result = bot.verify_order_result(timeout=5)

        assert result == "success"

    def test_verify_order_sold_out(self, bot):
        """Element contains '已售罄', returns 'sold_out'."""
        def has_element_side_effect(by, value):
            return '已售罄' in value

        with patch.object(bot, "_get_current_activity", return_value="SomeActivity"), \
             patch.object(bot, "_has_element", side_effect=has_element_side_effect), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.side_effect = [0.0, 0.1]
            result = bot.verify_order_result(timeout=5)

        assert result == "sold_out"

    def test_verify_order_timeout(self, bot):
        """No indicators found, returns 'timeout'."""
        call_count = [0]

        def mock_time_func():
            call_count[0] += 1
            # Return increasing time so we exceed timeout quickly
            return call_count[0] * 3.0

        with patch.object(bot, "_get_current_activity", return_value="SomeActivity"), \
             patch.object(bot, "_has_element", return_value=False), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time = mock_time_func
            mock_time.sleep = Mock()
            result = bot.verify_order_result(timeout=5)

        assert result == "timeout"

    def test_verify_order_captcha(self, bot):
        """Element contains '验证', returns 'captcha'."""
        def has_element_side_effect(by, value):
            # Skip 支付 and 已售罄/库存不足/暂时无票, match 验证
            if '支付' in value:
                return False
            if '已售罄' in value or '库存不足' in value or '暂时无票' in value:
                return False
            if '验证' in value:
                return True
            return False

        with patch.object(bot, "_get_current_activity", return_value="SomeActivity"), \
             patch.object(bot, "_has_element", side_effect=has_element_side_effect), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.side_effect = [0.0, 0.1]
            result = bot.verify_order_result(timeout=5)

        assert result == "captcha"

    def test_verify_order_existing_order(self, bot):
        """Element contains '未支付', returns 'existing_order'."""
        def has_element_side_effect(by, value):
            if '支付' in value and '未' not in value:
                return False
            if '已售罄' in value or '库存不足' in value or '暂时无票' in value:
                return False
            if '滑块' in value or '验证' in value:
                return False
            if '未支付' in value:
                return True
            return False

        with patch.object(bot, "_get_current_activity", return_value="SomeActivity"), \
             patch.object(bot, "_has_element", side_effect=has_element_side_effect), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.side_effect = [0.0, 0.1]
            result = bot.verify_order_result(timeout=5)

        assert result == "existing_order"


# ---------------------------------------------------------------------------
# select_performance_date
# ---------------------------------------------------------------------------

class TestSelectPerformanceDate:
    def test_select_performance_date_found(self, bot, caplog):
        """Date text found and clicked successfully."""
        with caplog.at_level("INFO", logger="mobile.damai_app"), \
             patch.object(bot, "ultra_fast_click", return_value=True) as ufc:
            bot.select_performance_date()

        ufc.assert_called_once_with(
            AppiumBy.ANDROID_UIAUTOMATOR,
            'new UiSelector().textContains("12.06")',
            timeout=1.0,
        )
        assert "选择场次日期: 12.06" in caplog.text

    def test_select_performance_date_not_found(self, bot, caplog):
        """Date not found, continues gracefully without error."""
        with caplog.at_level("DEBUG", logger="mobile.damai_app"), \
             patch.object(bot, "ultra_fast_click", return_value=False) as ufc:
            bot.select_performance_date()

        ufc.assert_called_once()
        assert "未找到日期" in caplog.text

    def test_select_performance_date_no_date_configured(self, bot):
        """No date in config, returns immediately without clicking."""
        bot.config.date = ""
        with patch.object(bot, "ultra_fast_click") as ufc:
            bot.select_performance_date()

        ufc.assert_not_called()


# ---------------------------------------------------------------------------
# check_session_valid
# ---------------------------------------------------------------------------

class TestCheckSessionValid:
    def test_check_session_valid_logged_in(self, bot):
        """No login indicators, returns True."""
        with patch.object(bot, "_get_current_activity", return_value="ProjectDetailActivity"), \
             patch.object(bot, "_has_element", return_value=False):
            result = bot.check_session_valid()

        assert result is True

    def test_check_session_valid_login_activity(self, bot, caplog):
        """LoginActivity detected, returns False."""
        with caplog.at_level("ERROR", logger="mobile.damai_app"), \
             patch.object(bot, "_get_current_activity", return_value="com.taobao.login.LoginActivity"):
            result = bot.check_session_valid()

        assert result is False
        assert "登录已过期" in caplog.text

    def test_check_session_valid_sign_activity(self, bot, caplog):
        """SignActivity detected, returns False."""
        with caplog.at_level("ERROR", logger="mobile.damai_app"), \
             patch.object(bot, "_get_current_activity", return_value="com.taobao.SignActivity"):
            result = bot.check_session_valid()

        assert result is False
        assert "登录已过期" in caplog.text

    def test_check_session_valid_login_prompt(self, bot, caplog):
        """'请先登录' text detected on page, returns False."""
        def has_element_side_effect(by, value):
            return '请先登录' in value

        with caplog.at_level("ERROR", logger="mobile.damai_app"), \
             patch.object(bot, "_get_current_activity", return_value="SomeActivity"), \
             patch.object(bot, "_has_element", side_effect=has_element_side_effect):
            result = bot.check_session_valid()

        assert result is False
        assert "登录提示" in caplog.text

    def test_check_session_valid_register_prompt(self, bot, caplog):
        """'登录/注册' text detected on page, returns False."""
        def has_element_side_effect(by, value):
            return '登录/注册' in value

        with caplog.at_level("ERROR", logger="mobile.damai_app"), \
             patch.object(bot, "_get_current_activity", return_value="SomeActivity"), \
             patch.object(bot, "_has_element", side_effect=has_element_side_effect):
            result = bot.check_session_valid()

        assert result is False
        assert "登录提示" in caplog.text


# ---------------------------------------------------------------------------
# Price selection (text match + index fallback)
# ---------------------------------------------------------------------------

class TestPriceSelection:
    def test_price_selection_text_match_success(self, bot):
        """Text-based price match works, index fallback not used."""
        with patch.object(bot, "dismiss_startup_popups"), \
             patch.object(bot, "check_session_valid", return_value=True), \
             patch.object(bot, "probe_current_page", return_value={
                 "state": "detail_page",
                 "purchase_button": True,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch.object(bot, "wait_for_sale_start"), \
             patch.object(bot, "select_performance_date"), \
             patch.object(bot, "wait_for_page_state", return_value={
                 "state": "order_confirm_page",
                 "purchase_button": False,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": True,
             }), \
             patch.object(bot, "smart_wait_and_click", return_value=True), \
             patch.object(bot, "ultra_fast_click", return_value=True) as ufc, \
             patch.object(bot, "ultra_batch_click"), \
             patch.object(bot, "verify_order_result", return_value="success"), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.side_effect = [0.0, 1.5]
            bot.driver.find_elements.return_value = []

            result = bot.run_ticket_grabbing()

        assert result is True
        # ultra_fast_click should have been called with the price text selector
        price_call_found = any(
            'textContains("799元")' in str(c)
            for c in ufc.call_args_list
        )
        assert price_call_found, f"Expected price text selector call, got: {ufc.call_args_list}"

    def test_price_selection_falls_back_to_index(self, bot, caplog):
        """Text match fails, index-based fallback used."""
        call_count = [0]

        def ultra_fast_click_side_effect(by, value, timeout=1.5):
            call_count[0] += 1
            # First call with textContains (price) returns False to trigger fallback
            if 'textContains("799元")' in str(value):
                return False
            return True

        with caplog.at_level("INFO", logger="mobile.damai_app"), \
             patch.object(bot, "dismiss_startup_popups"), \
             patch.object(bot, "check_session_valid", return_value=True), \
             patch.object(bot, "probe_current_page", return_value={
                 "state": "detail_page",
                 "purchase_button": True,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": False,
             }), \
             patch.object(bot, "wait_for_sale_start"), \
             patch.object(bot, "select_performance_date"), \
             patch.object(bot, "wait_for_page_state", return_value={
                 "state": "order_confirm_page",
                 "purchase_button": False,
                 "price_container": True,
                 "quantity_picker": False,
                 "submit_button": True,
             }), \
             patch.object(bot, "smart_wait_and_click", return_value=True), \
             patch.object(bot, "ultra_fast_click", side_effect=ultra_fast_click_side_effect), \
             patch.object(bot, "ultra_batch_click"), \
             patch.object(bot, "verify_order_result", return_value="success"), \
             patch("mobile.damai_app.time") as mock_time:
            mock_time.time.side_effect = [0.0, 1.5]
            # Mock price container for index-based fallback
            mock_price_container = Mock()
            mock_target = _make_mock_element()
            mock_price_container.find_element.return_value = mock_target
            bot.driver.find_element.return_value = mock_price_container
            bot.driver.find_elements.return_value = []

            result = bot.run_ticket_grabbing()

        assert result is True
        assert "文本匹配失败，使用索引选择票价" in caplog.text
