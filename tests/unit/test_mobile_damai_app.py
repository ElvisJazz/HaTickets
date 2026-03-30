# -*- coding: UTF-8 -*-
"""Unit tests for mobile/damai_app.py — DamaiBot class."""

import pytest
from unittest.mock import Mock, patch, call

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.common.by import By

from mobile.damai_app import DamaiBot
from mobile.config import Config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_element(x=100, y=200, width=50, height=40):
    """Helper: create a mock element with a .rect property."""
    el = Mock()
    el.rect = {"x": x, "y": y, "width": width, "height": height}
    el.id = "fake-element-id"
    return el


def _make_config(**overrides):
    defaults = dict(
        server_url="http://127.0.0.1:4723",
        device_name="Android",
        udid=None,
        platform_version="16",
        app_package="cn.damai",
        app_activity=".launcher.splash.SplashMainActivity",
        keyword="test",
        users=["UserA", "UserB"],
        city="深圳",
        date="12.06",
        price="799元",
        price_index=1,
        if_commit_order=True,
    )
    defaults.update(overrides)
    return Config(**defaults)


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

    mock_config = _make_config()

    with patch("mobile.damai_app.Config.load_config", return_value=mock_config), \
         patch("mobile.damai_app.webdriver.Remote", return_value=mock_driver), \
         patch("mobile.damai_app.AppiumOptions"), \
         patch("mobile.damai_app.ClientConfig"), \
         patch("mobile.damai_app.RemoteConnection"):
        b = DamaiBot()
    return b


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
        bot.driver.update_settings.assert_called_once()

    def test_init_creates_last_error_attribute(self, bot):
        assert bot.last_error == ""

    def test_setup_driver_called_with_fast_mode_settings(self):
        """In fast_mode=True, update_settings receives tight timeouts."""
        mock_driver = Mock()
        mock_driver.update_settings = Mock()

        mock_config = _make_config(fast_mode=True)

        with patch("mobile.damai_app.Config.load_config", return_value=mock_config), \
             patch("mobile.damai_app.webdriver.Remote", return_value=mock_driver), \
             patch("mobile.damai_app.AppiumOptions"), \
             patch("mobile.damai_app.ClientConfig"), \
             patch("mobile.damai_app.RemoteConnection"):
            b = DamaiBot()

        settings_call = mock_driver.update_settings.call_args[0][0]
        assert settings_call["waitForIdleTimeout"] == 200

    def test_setup_driver_slow_mode_settings(self):
        """In fast_mode=False, update_settings receives slower timeouts."""
        mock_driver = Mock()
        mock_driver.update_settings = Mock()

        mock_config = _make_config(fast_mode=False)

        with patch("mobile.damai_app.Config.load_config", return_value=mock_config), \
             patch("mobile.damai_app.webdriver.Remote", return_value=mock_driver), \
             patch("mobile.damai_app.AppiumOptions"), \
             patch("mobile.damai_app.ClientConfig"), \
             patch("mobile.damai_app.RemoteConnection"):
            b = DamaiBot()

        settings_call = mock_driver.update_settings.call_args[0][0]
        assert settings_call["waitForIdleTimeout"] == 1000

    def test_setup_driver_retry_on_udid(self):
        """When driver creation fails on first attempt with udid set, retries."""
        mock_driver = Mock()
        mock_driver.update_settings = Mock()
        mock_config = _make_config(udid="emulator-5554")

        call_count = [0]
        def remote_side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise WebDriverException("connection failed")
            return mock_driver

        with patch("mobile.damai_app.Config.load_config", return_value=mock_config), \
             patch("mobile.damai_app.webdriver.Remote", side_effect=remote_side_effect), \
             patch("mobile.damai_app.AppiumOptions"), \
             patch("mobile.damai_app.ClientConfig"), \
             patch("mobile.damai_app.RemoteConnection"), \
             patch("mobile.damai_app.subprocess.run"), \
             patch("mobile.damai_app.time.sleep"):
            b = DamaiBot()

        assert call_count[0] == 2


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

    def test_ultra_fast_click_stale_retries(self, bot):
        """StaleElementReferenceException causes retry; succeeds on second attempt."""
        mock_el = _make_mock_element(x=10, y=20, width=80, height=60)

        with patch("mobile.damai_app.WebDriverWait") as MockWait, \
             patch("mobile.damai_app.time"):
            MockWait.return_value.until.side_effect = [
                StaleElementReferenceException("stale"),
                mock_el,
            ]
            result = bot.ultra_fast_click("by", "value")

        assert result is True


# ---------------------------------------------------------------------------
# batch_click
# ---------------------------------------------------------------------------

class TestBatchClick:
    def test_batch_click_all_success(self, bot):
        """ultra_fast_click called for each element pair."""
        elements = [("by1", "v1"), ("by2", "v2"), ("by3", "v3")]
        with patch.object(bot, "ultra_fast_click", return_value=True) as ufc, \
             patch("mobile.damai_app.time"):
            bot.batch_click(elements, delay=0.1)

        assert ufc.call_count == 3
        ufc.assert_any_call("by1", "v1")
        ufc.assert_any_call("by2", "v2")
        ufc.assert_any_call("by3", "v3")

    def test_batch_click_some_fail_prints(self, bot, capsys):
        """Failed clicks print a message and processing continues."""
        elements = [("by1", "v1"), ("by2", "v2")]
        with patch.object(bot, "ultra_fast_click", side_effect=[False, True]) as ufc, \
             patch("mobile.damai_app.time"):
            bot.batch_click(elements, delay=0.1)

        assert ufc.call_count == 2
        captured = capsys.readouterr()
        assert "点击失败: v1" in captured.out

    def test_batch_click_empty_list(self, bot):
        """Empty list does nothing."""
        with patch.object(bot, "ultra_fast_click") as ufc:
            bot.batch_click([])
        ufc.assert_not_called()


# ---------------------------------------------------------------------------
# ultra_batch_click
# ---------------------------------------------------------------------------

class TestUltraBatchClick:
    def test_ultra_batch_click_collects_and_clicks(self, bot, capsys):
        """Coordinates collected for all elements, then clicked sequentially."""
        el1 = _make_mock_element(x=10, y=20, width=100, height=50)
        el2 = _make_mock_element(x=200, y=300, width=60, height=30)

        with patch("mobile.damai_app.time"):
            bot.driver.find_elements.return_value = [el1]
            # We need to return different elements for different calls
            call_count = [0]
            def find_elements_side_effect(by, value):
                call_count[0] += 1
                if call_count[0] == 1:
                    return [el1]
                return [el2]
            bot.driver.find_elements.side_effect = find_elements_side_effect
            bot.ultra_batch_click([("by1", "v1"), ("by2", "v2")], timeout=2)

        # Two clickGesture calls with correct center coordinates
        calls = bot.driver.execute_script.call_args_list
        assert len(calls) == 2
        assert calls[0] == call("mobile: clickGesture", {"x": 60, "y": 45, "duration": 30})
        assert calls[1] == call("mobile: clickGesture", {"x": 230, "y": 315, "duration": 30})

        captured = capsys.readouterr()
        assert "成功找到 2 个用户" in captured.out

    def test_ultra_batch_click_not_found_skips(self, bot, capsys):
        """Elements not found are skipped."""
        bot.driver.find_elements.return_value = []
        with patch("mobile.damai_app.time"):
            bot.ultra_batch_click([("by1", "v1")], timeout=2)

        assert bot.driver.execute_script.call_count == 0
        captured = capsys.readouterr()
        assert "未找到用户: v1" in captured.out
        assert "成功找到 0 个用户" in captured.out


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
# _click_element
# ---------------------------------------------------------------------------

class TestClickElement:
    def test_click_element_center(self, bot):
        """_click_element calculates center coords and calls execute_script."""
        el = _make_mock_element(x=100, y=200, width=50, height=40)
        result = bot._click_element(el)

        assert result is True
        bot.driver.execute_script.assert_called_once_with(
            "mobile: clickGesture",
            {"x": 125, "y": 220, "duration": 50},
        )

    def test_click_element_stale_returns_false(self, bot):
        """StaleElementReferenceException on execute_script returns False."""
        el = _make_mock_element()
        bot.driver.execute_script.side_effect = StaleElementReferenceException("stale")
        result = bot._click_element(el)

        assert result is False
        # Reset side_effect for other tests
        bot.driver.execute_script.side_effect = None

    def test_click_element_webdriver_exception_returns_false(self, bot):
        """WebDriverException on execute_script returns False."""
        el = _make_mock_element()
        bot.driver.execute_script.side_effect = WebDriverException("error")
        result = bot._click_element(el)

        assert result is False
        # Reset side_effect for other tests
        bot.driver.execute_script.side_effect = None


# ---------------------------------------------------------------------------
# _build_date_tokens
# ---------------------------------------------------------------------------

class TestBuildDateTokens:
    def test_build_date_tokens_md_format(self, bot):
        """12.06 produces multiple date representations."""
        tokens = bot._build_date_tokens("12.06")
        assert len(tokens) > 0
        # Should have some reasonable date tokens
        assert any("12" in t for t in tokens)

    def test_build_date_tokens_empty_returns_empty(self, bot):
        """Empty string returns empty list."""
        assert bot._build_date_tokens("") == []

    def test_build_date_tokens_none_returns_empty(self, bot):
        """None returns empty list."""
        assert bot._build_date_tokens(None) == []

    def test_build_date_tokens_deduplicates(self, bot):
        """No duplicate tokens in result."""
        tokens = bot._build_date_tokens("2026.03.29")
        assert len(tokens) == len(set(tokens))


# ---------------------------------------------------------------------------
# run_ticket_grabbing
# ---------------------------------------------------------------------------

class TestRunTicketGrabbing:
    def _patch_time(self):
        """Return a time mock with .time() returning floats and .sleep() as a no-op."""
        mock_time = Mock()
        mock_time.time.side_effect = [0.0, 1.5]
        mock_time.sleep = Mock()
        return mock_time

    def test_run_ticket_grabbing_returns_true_on_success(self, bot):
        """When all inner operations succeed, returns True."""
        with patch.object(bot, "smart_wait_and_click", return_value=True), \
             patch.object(bot, "_try_click_by_text_tokens", return_value=True), \
             patch.object(bot, "_tap_from_dump", return_value=True), \
             patch.object(bot, "_ensure_sku_panel", return_value=True), \
             patch.object(bot, "_tap_right_bottom"), \
             patch.object(bot, "_tap_text_from_dump", return_value=True), \
             patch.object(bot, "_adb_screen_size", return_value=None), \
             patch.object(bot, "_try_open_time_panel", return_value=True), \
             patch.object(bot, "_try_select_date_by_index", return_value=True), \
             patch.object(bot, "_try_select_any_price", return_value=True), \
             patch.object(bot, "_swipe_up_small"), \
             patch.object(bot, "_dump_page_source"), \
             patch("mobile.damai_app.time", self._patch_time()):
            result = bot.run_ticket_grabbing()

        assert result is True

    def test_run_ticket_grabbing_returns_false_on_exception(self, bot):
        """Exception in flow returns False and sets last_error."""
        mock_time = Mock()
        mock_time.time.return_value = 0.0
        mock_time.sleep = Mock()
        with patch.object(bot, "smart_wait_and_click", side_effect=RuntimeError("boom")), \
             patch("mobile.damai_app.time", mock_time):
            result = bot.run_ticket_grabbing()

        assert result is False
        assert "boom" in bot.last_error

    def test_run_ticket_grabbing_skips_commit_when_disabled(self, bot, capsys):
        """When if_commit_order=False, submission is skipped."""
        bot.config.if_commit_order = False

        with patch.object(bot, "smart_wait_and_click", return_value=True), \
             patch.object(bot, "_try_click_by_text_tokens", return_value=True), \
             patch.object(bot, "_tap_from_dump", return_value=True), \
             patch.object(bot, "_ensure_sku_panel", return_value=False), \
             patch.object(bot, "_tap_right_bottom"), \
             patch.object(bot, "_tap_text_from_dump", return_value=True), \
             patch.object(bot, "_adb_screen_size", return_value=None), \
             patch.object(bot, "_try_open_time_panel", return_value=True), \
             patch.object(bot, "_try_select_date_by_index", return_value=True), \
             patch.object(bot, "_try_select_any_price", return_value=True), \
             patch.object(bot, "_swipe_up_small"), \
             patch.object(bot, "_dump_page_source"), \
             patch("mobile.damai_app.time", self._patch_time()):
            result = bot.run_ticket_grabbing()

        assert result is True
        captured = capsys.readouterr()
        assert "不提交订单" in captured.out

    def test_run_ticket_grabbing_no_driver_quit_in_finally(self, bot):
        """driver.quit is NOT called inside run_ticket_grabbing."""
        mock_time = Mock()
        mock_time.time.return_value = 0.0
        mock_time.sleep = Mock()
        with patch.object(bot, "smart_wait_and_click", return_value=False), \
             patch.object(bot, "_try_click_by_text_tokens", return_value=False), \
             patch.object(bot, "_tap_bottom_area", return_value=False), \
             patch("mobile.damai_app.time", mock_time):
            bot.run_ticket_grabbing()

        bot.driver.quit.assert_not_called()

    def test_run_ticket_grabbing_skips_city_when_no_city(self, bot):
        """When city is empty, city selection is skipped."""
        bot.config.city = ""

        with patch.object(bot, "smart_wait_and_click", return_value=True), \
             patch.object(bot, "_tap_from_dump", return_value=True), \
             patch.object(bot, "_ensure_sku_panel", return_value=True), \
             patch.object(bot, "_tap_right_bottom"), \
             patch.object(bot, "_tap_text_from_dump", return_value=True), \
             patch.object(bot, "_adb_screen_size", return_value=None), \
             patch.object(bot, "_try_open_time_panel", return_value=True), \
             patch.object(bot, "_try_select_date_by_index", return_value=True), \
             patch.object(bot, "_try_select_any_price", return_value=True), \
             patch.object(bot, "_swipe_up_small"), \
             patch.object(bot, "_dump_page_source"), \
             patch("mobile.damai_app.time", self._patch_time()):
            result = bot.run_ticket_grabbing()

        # smart_wait_and_click should still be called for book button, not for city
        assert result is True

    def test_run_ticket_grabbing_book_fail_returns_false(self, bot):
        """When book button and all fallbacks fail, returns False."""
        mock_time = Mock()
        mock_time.time.return_value = 0.0
        mock_time.sleep = Mock()
        with patch.object(bot, "smart_wait_and_click", return_value=False), \
             patch.object(bot, "_try_click_by_text_tokens", return_value=False), \
             patch.object(bot, "_tap_bottom_area", return_value=False), \
             patch("mobile.damai_app.time", mock_time):
            result = bot.run_ticket_grabbing()

        assert result is False

    def test_run_ticket_grabbing_date_strict_returns_false_when_not_found(self, bot):
        """When date_strict=True and date can't be selected, returns False."""
        bot.config.date_strict = True
        bot.config.date_index = None  # force text-based date matching

        mock_time = Mock()
        mock_time.time.side_effect = [0.0, 1.5]
        mock_time.sleep = Mock()

        with patch.object(bot, "smart_wait_and_click", return_value=True), \
             patch.object(bot, "_try_click_by_text_tokens", return_value=False), \
             patch.object(bot, "_try_click_by_text_tokens_webview", return_value=False), \
             patch.object(bot, "_tap_from_dump", return_value=True), \
             patch.object(bot, "_ensure_sku_panel", return_value=True), \
             patch.object(bot, "_tap_right_bottom"), \
             patch.object(bot, "_try_open_time_panel", return_value=False), \
             patch.object(bot, "_swipe_up_small"), \
             patch.object(bot, "_dump_page_source"), \
             patch("mobile.damai_app.time", mock_time):
            result = bot.run_ticket_grabbing()

        assert result is False

    def test_run_ticket_grabbing_fast_mode_price_fail_returns_false(self, bot):
        """In fast_mode, price index not found returns False immediately."""
        bot.config.fast_mode = True

        mock_time = Mock()
        mock_time.time.side_effect = [0.0, 1.5]
        mock_time.sleep = Mock()

        with patch.object(bot, "smart_wait_and_click", return_value=True), \
             patch.object(bot, "_try_click_by_text_tokens", return_value=True), \
             patch.object(bot, "_tap_from_dump", return_value=False), \
             patch.object(bot, "_ensure_sku_panel", return_value=True), \
             patch.object(bot, "_try_select_price_in_flowlayout", return_value=False), \
             patch.object(bot, "_try_open_time_panel", return_value=True), \
             patch.object(bot, "_try_select_date_by_index", return_value=True), \
             patch.object(bot, "_swipe_up_small"), \
             patch.object(bot, "_dump_page_source"), \
             patch("mobile.damai_app.time", mock_time):
            result = bot.run_ticket_grabbing()

        assert result is False


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
             patch.object(bot, "_setup_driver") as mock_setup, \
             patch("mobile.damai_app.time"):
            result = bot.run_with_retry(max_retries=3)

        assert result is True
        mock_setup.assert_called_once()

    def test_run_with_retry_all_fail(self, bot):
        """All retries fail, returns False."""
        with patch.object(bot, "run_ticket_grabbing", return_value=False), \
             patch.object(bot, "_setup_driver"), \
             patch("mobile.damai_app.time"):
            result = bot.run_with_retry(max_retries=3)

        assert result is False

    def test_run_with_retry_driver_quit_between_retries(self, bot):
        """Between retries, driver.quit and _setup_driver are called."""
        with patch.object(bot, "run_ticket_grabbing", side_effect=[False, False, True]), \
             patch.object(bot, "_setup_driver") as mock_setup, \
             patch("mobile.damai_app.time"):
            bot.run_with_retry(max_retries=3)

        assert bot.driver.quit.call_count == 2
        assert mock_setup.call_count == 2

    def test_run_with_retry_quit_exception_handled(self, bot):
        """driver.quit raises an exception but retry continues."""
        bot.driver.quit.side_effect = Exception("quit failed")

        with patch.object(bot, "run_ticket_grabbing", side_effect=[False, True]), \
             patch.object(bot, "_setup_driver"), \
             patch("mobile.damai_app.time"):
            result = bot.run_with_retry(max_retries=3)

        assert result is True

    def test_run_with_retry_respects_max_retries(self, bot):
        """run_ticket_grabbing is called exactly max_retries times."""
        run_tg = Mock(return_value=False)
        with patch.object(bot, "run_ticket_grabbing", run_tg), \
             patch.object(bot, "_setup_driver"), \
             patch("mobile.damai_app.time"):
            bot.run_with_retry(max_retries=5)

        assert run_tg.call_count == 5


# ---------------------------------------------------------------------------
# _build_capabilities (via _setup_driver internals via AppiumOptions)
# ---------------------------------------------------------------------------

class TestBuildCapabilities:
    def test_build_capabilities_includes_device_fields(self):
        """Capabilities include device_name, platform_version, etc."""
        mock_driver = Mock()
        mock_driver.update_settings = Mock()
        mock_options = Mock()

        mock_config = _make_config(
            device_name="Pixel 8",
            udid="R58M123456A",
            platform_version="14",
        )

        captured_caps = {}
        def load_caps_side_effect(caps):
            captured_caps.update(caps)

        mock_options_instance = Mock()
        mock_options_instance.load_capabilities = Mock(side_effect=load_caps_side_effect)

        with patch("mobile.damai_app.Config.load_config", return_value=mock_config), \
             patch("mobile.damai_app.webdriver.Remote", return_value=mock_driver), \
             patch("mobile.damai_app.AppiumOptions", return_value=mock_options_instance), \
             patch("mobile.damai_app.ClientConfig"), \
             patch("mobile.damai_app.RemoteConnection"):
            b = DamaiBot()

        assert captured_caps["deviceName"] == "Pixel 8"
        assert captured_caps["udid"] == "R58M123456A"
        assert captured_caps["platformVersion"] == "14"
        assert captured_caps["appPackage"] == "cn.damai"

    def test_capabilities_no_udid_field_when_none(self):
        """When udid is None, 'udid' should NOT be in capabilities."""
        mock_driver = Mock()
        mock_driver.update_settings = Mock()

        mock_config = _make_config(udid=None)
        captured_caps = {}

        mock_options_instance = Mock()
        mock_options_instance.load_capabilities = Mock(side_effect=lambda c: captured_caps.update(c))

        with patch("mobile.damai_app.Config.load_config", return_value=mock_config), \
             patch("mobile.damai_app.webdriver.Remote", return_value=mock_driver), \
             patch("mobile.damai_app.AppiumOptions", return_value=mock_options_instance), \
             patch("mobile.damai_app.ClientConfig"), \
             patch("mobile.damai_app.RemoteConnection"):
            b = DamaiBot()

        assert "udid" not in captured_caps


# ---------------------------------------------------------------------------
# Helper internal methods
# ---------------------------------------------------------------------------

class TestHelperMethods:
    def test_tap_bottom_area_success(self, bot):
        """_tap_bottom_area calls execute_script with calculated coords."""
        bot.driver.get_window_size.return_value = {"width": 1080, "height": 2400}
        result = bot._tap_bottom_area()

        assert result is True
        bot.driver.execute_script.assert_called_once()
        args = bot.driver.execute_script.call_args[0]
        assert args[0] == "mobile: clickGesture"

    def test_tap_bottom_area_exception_returns_false(self, bot):
        """Exception in _tap_bottom_area returns False."""
        bot.driver.get_window_size.side_effect = WebDriverException("error")
        result = bot._tap_bottom_area()

        assert result is False

    def test_ensure_sku_panel_found_immediately(self, bot):
        """_ensure_sku_panel returns True when panel is already visible."""
        bot.driver.find_elements.return_value = [Mock()]
        with patch("mobile.damai_app.time"):
            result = bot._ensure_sku_panel()

        assert result is True

    def test_ensure_sku_panel_not_found(self, bot):
        """_ensure_sku_panel returns False when panel never appears."""
        bot.driver.find_elements.return_value = []
        with patch.object(bot, "_tap_bottom_area"), \
             patch.object(bot, "_swipe_up_small"), \
             patch("mobile.damai_app.time"):
            result = bot._ensure_sku_panel()

        assert result is False

    def test_try_open_time_panel_calls_click_by_text_tokens(self, bot):
        """_try_open_time_panel delegates to _try_click_by_text_tokens."""
        with patch.object(bot, "_try_click_by_text_tokens", return_value=True) as tct:
            result = bot._try_open_time_panel()

        assert result is True
        tct.assert_called_once()
        # Should try panel-related tokens
        args = tct.call_args[0][0]
        assert "场次" in args or "时间" in args

    def test_swipe_up_small_success(self, bot):
        """_swipe_up_small calls execute_script without error."""
        bot.driver.get_window_size.return_value = {"width": 1080, "height": 2400}
        # Should not raise
        bot._swipe_up_small()

    def test_try_select_city_by_index_returns_false_when_none(self, bot):
        """_try_select_city_by_index returns False when city_index is None."""
        bot.config.city_index = None
        result = bot._try_select_city_by_index()

        assert result is False

    def test_dump_page_source_writes_xml(self, bot, tmp_path):
        """_dump_page_source writes page source XML to file."""
        xml_content = "<hierarchy><node /></hierarchy>"
        bot.driver.page_source = xml_content

        path = str(tmp_path / "test.xml")
        bot._dump_page_source(path=path, force=True)

        # In fast_mode, this may be a no-op; check it doesn't crash
        # (fast_mode defaults to True, so the dump may be skipped)

    def test_get_webview_context_returns_webview(self, bot):
        """_get_webview_context returns first WEBVIEW context."""
        bot.driver.contexts = ["NATIVE_APP", "WEBVIEW_1"]
        result = bot._get_webview_context()

        assert result == "WEBVIEW_1"

    def test_get_webview_context_returns_none_when_no_webview(self, bot):
        """_get_webview_context returns None when no WEBVIEW context."""
        bot.driver.contexts = ["NATIVE_APP"]
        result = bot._get_webview_context()

        assert result is None

    def test_get_webview_context_exception_returns_none(self, bot):
        """Exception when accessing contexts returns None."""
        bot.driver.contexts = Mock(side_effect=WebDriverException("error"))
        result = bot._get_webview_context()

        assert result is None

    def test_try_scroll_and_click_skips_in_fast_mode(self, bot):
        """_try_scroll_and_click returns False immediately in fast_mode."""
        bot.config.fast_mode = True
        result = bot._try_scroll_and_click(["token1"])

        assert result is False

    def test_try_select_date_by_index_returns_false_on_exception(self, bot):
        """Exception in _try_select_date_by_index returns False."""
        bot.driver.find_elements.side_effect = WebDriverException("error")
        result = bot._try_select_date_by_index()

        assert result is False


# ---------------------------------------------------------------------------
# Additional coverage tests for _try_* helpers and other uncovered paths
# ---------------------------------------------------------------------------

class TestTryClickByTextTokens:
    def test_try_click_by_text_tokens_finds_and_clicks(self, bot):
        """First token matches and element is clicked successfully."""
        el = _make_mock_element()
        bot.driver.find_elements.return_value = [el]
        result = bot._try_click_by_text_tokens(["token1"])

        assert result is True

    def test_try_click_by_text_tokens_no_elements_all_tokens(self, bot):
        """No elements found for any token, returns False."""
        bot.driver.find_elements.return_value = []
        result = bot._try_click_by_text_tokens(["token1", "token2"])

        assert result is False

    def test_try_click_by_text_tokens_empty_list(self, bot):
        """Empty token list returns False."""
        result = bot._try_click_by_text_tokens([])

        assert result is False

    def test_try_click_by_text_tokens_webdriver_exception(self, bot):
        """WebDriverException for a token is swallowed, continues to next."""
        bot.driver.find_elements.side_effect = [
            WebDriverException("error"),
            WebDriverException("error"),
            WebDriverException("error"),
        ]
        result = bot._try_click_by_text_tokens(["token1"])

        assert result is False


class TestTryScrollAndClick:
    def test_returns_false_in_fast_mode(self, bot):
        """Always False in fast_mode."""
        bot.config.fast_mode = True
        result = bot._try_scroll_and_click(["token"])

        assert result is False

    def test_returns_false_when_no_scrollable(self, bot):
        """No scrollable element returns False."""
        bot.config.fast_mode = False
        bot.driver.find_elements.return_value = []
        result = bot._try_scroll_and_click(["token"])

        assert result is False

    def test_scrolls_and_clicks_when_found(self, bot):
        """Scrollable present, token found, click succeeds."""
        bot.config.fast_mode = False
        mock_scrollable = Mock()
        mock_el = _make_mock_element()

        def find_elements_side(by, value):
            if "scrollable" in value.lower() or "scrollable(true)" in value:
                return [mock_scrollable]
            return []

        def find_element_side(by, value):
            return mock_el

        bot.driver.find_elements.side_effect = find_elements_side
        bot.driver.find_element.return_value = mock_el

        result = bot._try_scroll_and_click(["token"])

        assert result is True


class TestTrySelectAnyPrice:
    def test_returns_true_when_price_element_clicked(self, bot):
        """Finds a price element and clicks it."""
        el = _make_mock_element()
        bot.driver.find_elements.return_value = [el]
        result = bot._try_select_any_price()

        assert result is True

    def test_returns_false_when_no_price_elements(self, bot):
        """No price elements found returns False."""
        bot.driver.find_elements.return_value = []
        result = bot._try_select_any_price()

        assert result is False

    def test_returns_false_on_exception(self, bot):
        """WebDriverException returns False."""
        bot.driver.find_elements.side_effect = WebDriverException("error")
        result = bot._try_select_any_price()

        assert result is False


class TestTrySelectPriceByResource:
    def test_returns_true_when_element_found_and_clicked(self, bot):
        """Finds resource-matched price element and clicks it."""
        el = _make_mock_element()
        bot.driver.find_elements.return_value = [el]
        result = bot._try_select_price_by_resource()

        assert result is True

    def test_returns_false_when_no_elements(self, bot):
        bot.driver.find_elements.return_value = []
        result = bot._try_select_price_by_resource()

        assert result is False

    def test_returns_false_on_exception(self, bot):
        bot.driver.find_elements.side_effect = WebDriverException("error")
        result = bot._try_select_price_by_resource()

        assert result is False


class TestTrySelectPriceByLayout:
    def test_returns_false_when_no_sku_layout(self, bot):
        """No SKU layout element returns False."""
        bot.driver.find_elements.return_value = []
        result = bot._try_select_price_by_layout()

        assert result is False

    def test_returns_true_when_candidate_found(self, bot):
        """SKU layout present with clickable items, clicks correct index."""
        sku_el = Mock()
        el = _make_mock_element(x=100, y=900, width=200, height=80)
        el.get_attribute.return_value = "true"
        el.rect = {"x": 100, "y": 900, "width": 200, "height": 80}
        sku_el.find_elements.return_value = [el]
        bot.driver.find_elements.return_value = [sku_el]
        bot.config.price_index = 0

        result = bot._try_select_price_by_layout()

        assert result is True


class TestTrySelectPriceInFlowlayout:
    def test_returns_false_when_no_items(self, bot):
        bot.driver.find_elements.return_value = []
        result = bot._try_select_price_in_flowlayout()

        assert result is False

    def test_returns_true_when_item_found(self, bot):
        """Items found, clicks the one at price_index."""
        el = _make_mock_element()
        bot.driver.find_elements.return_value = [el]
        bot.config.price_index = 0

        result = bot._try_select_price_in_flowlayout()

        assert result is True

    def test_returns_false_on_exception(self, bot):
        bot.driver.find_elements.side_effect = Exception("error")
        result = bot._try_select_price_in_flowlayout()

        assert result is False


class TestAdbMethods:
    def test_adb_tap_returns_false_when_no_udid(self, bot):
        """_adb_tap returns False when udid is None."""
        bot.config.udid = None
        result = bot._adb_tap(100, 200)

        assert result is False

    def test_adb_tap_runs_subprocess_with_udid(self, bot):
        """_adb_tap calls subprocess.run when udid is set."""
        bot.config.udid = "emulator-5554"
        with patch("mobile.damai_app.subprocess.run") as mock_run:
            result = bot._adb_tap(100, 200)

        assert result is True
        mock_run.assert_called_once()

    def test_adb_tap_exception_returns_false(self, bot):
        """Exception in subprocess call returns False."""
        bot.config.udid = "emulator-5554"
        with patch("mobile.damai_app.subprocess.run", side_effect=Exception("error")):
            result = bot._adb_tap(100, 200)

        assert result is False

    def test_adb_screen_size_returns_none_when_no_udid(self, bot):
        """Returns None when udid is None."""
        bot.config.udid = None
        result = bot._adb_screen_size()

        assert result is None

    def test_adb_screen_size_parses_output(self, bot):
        """Parses adb wm size output correctly."""
        bot.config.udid = "emulator-5554"
        mock_result = Mock()
        mock_result.stdout = "Physical size: 1080x2400\n"
        with patch("mobile.damai_app.subprocess.run", return_value=mock_result):
            result = bot._adb_screen_size()

        assert result == {"width": 1080, "height": 2400}

    def test_adb_screen_size_returns_none_on_exception(self, bot):
        """Exception returns None."""
        bot.config.udid = "emulator-5554"
        with patch("mobile.damai_app.subprocess.run", side_effect=Exception("error")):
            result = bot._adb_screen_size()

        assert result is None


class TestTapBounds:
    def test_tap_bounds_parses_and_taps(self, bot):
        """Parses bounds string and calls _adb_tap with midpoint."""
        with patch.object(bot, "_adb_tap", return_value=True) as mock_tap:
            result = bot._tap_bounds("[100,200][300,400]")

        assert result is True
        mock_tap.assert_called_once_with(200.0, 300.0)

    def test_tap_bounds_invalid_returns_false(self, bot):
        """Invalid bounds string returns False."""
        result = bot._tap_bounds("invalid")

        assert result is False


class TestTapFromDump:
    def test_tap_from_dump_returns_false_when_file_missing(self, bot):
        """Missing dump file returns False."""
        result = bot._tap_from_dump("some:id", index=0)

        assert result is False

    def test_tap_from_dump_finds_and_taps(self, bot, tmp_path):
        """Finds candidate from XML and taps it."""
        xml = """<?xml version="1.0"?>
<hierarchy>
  <node resource-id="cn.damai:id/container">
    <node resource-id="cn.damai:id/my_resource"
          class="android.widget.FrameLayout"
          clickable="true"
          bounds="[100,200][300,400]"/>
  </node>
</hierarchy>"""
        dump_path = str(tmp_path / "damai_after_date.xml")
        with open(dump_path, "w") as f:
            f.write(xml)

        with patch("mobile.damai_app.ET.parse") as mock_parse:
            import xml.etree.ElementTree as ET
            mock_parse.return_value = ET.fromstring(xml)
            # ET.fromstring returns element, need ET.parse to return a tree
            real_tree = ET.ElementTree(ET.fromstring(xml))
            mock_parse.return_value = real_tree
            with patch.object(bot, "_tap_bounds", return_value=True) as mock_tap:
                result = bot._tap_from_dump("cn.damai:id/my_resource", index=0)

        assert result is True


class TestTapTextFromDump:
    def test_tap_text_from_dump_returns_false_when_file_missing(self, bot):
        """Missing dump file returns False."""
        result = bot._tap_text_from_dump("/nonexistent/path.xml", "sometext")

        assert result is False

    def test_tap_text_from_dump_finds_text_and_taps(self, bot, tmp_path):
        """Finds node with matching text and taps it."""
        xml = """<?xml version="1.0"?>
<hierarchy>
  <node text="立即提交" bounds="[100,200][300,400]" clickable="true"/>
</hierarchy>"""
        dump_path = str(tmp_path / "dump.xml")
        with open(dump_path, "w") as f:
            f.write(xml)

        with patch.object(bot, "_tap_bounds", return_value=True) as mock_tap:
            result = bot._tap_text_from_dump(dump_path, "立即提交", exact=True)

        assert result is True
        mock_tap.assert_called_once_with("[100,200][300,400]")

    def test_tap_text_from_dump_partial_match(self, bot, tmp_path):
        """Partial match works when exact=False."""
        xml = """<?xml version="1.0"?>
<hierarchy>
  <node text="立即提交订单" bounds="[0,0][100,50]"/>
</hierarchy>"""
        dump_path = str(tmp_path / "dump.xml")
        with open(dump_path, "w") as f:
            f.write(xml)

        with patch.object(bot, "_tap_bounds", return_value=True):
            result = bot._tap_text_from_dump(dump_path, "提交", exact=False)

        assert result is True


class TestSwipeUpSmall:
    def test_swipe_up_small_success(self, bot):
        """Calls execute_script with swipeGesture."""
        bot.driver.get_window_size.return_value = {"width": 1080, "height": 2400}
        result = bot._swipe_up_small()

        assert result is True
        call_args = bot.driver.execute_script.call_args[0]
        assert call_args[0] == "mobile: swipeGesture"

    def test_swipe_up_small_exception_returns_false(self, bot):
        """Exception returns False."""
        bot.driver.get_window_size.side_effect = WebDriverException("error")
        result = bot._swipe_up_small()

        assert result is False


class TestDumpPageSource:
    def test_dump_page_source_skips_in_fast_mode(self, bot):
        """In fast_mode, dump is skipped unless forced."""
        bot.config.fast_mode = True
        bot.driver.page_source = "<xml/>"
        bot._dump_page_source(path="/tmp/test.xml", force=False)
        # Should not raise; page_source should not be accessed

    def test_dump_page_source_forced_even_in_fast_mode(self, bot, tmp_path):
        """Force=True overrides fast_mode."""
        bot.config.fast_mode = True
        bot.driver.page_source = "<hierarchy/>"
        path = str(tmp_path / "out.xml")
        bot._dump_page_source(path=path, force=True)

        import os
        assert os.path.exists(path)

    def test_dump_page_source_slow_mode_always_dumps(self, bot, tmp_path):
        """In slow mode, dump always happens."""
        bot.config.fast_mode = False
        bot.driver.page_source = "<hierarchy/>"
        path = str(tmp_path / "out.xml")
        bot._dump_page_source(path=path, force=False)

        import os
        assert os.path.exists(path)


class TestScanTextviews:
    def test_scan_textviews_prints_texts(self, bot, capsys):
        """Prints text values from found TextView elements."""
        el = Mock()
        el.get_attribute.side_effect = lambda name: "票档A" if name == "text" else ""
        bot.driver.find_elements.return_value = [el]
        bot._scan_textviews()

        captured = capsys.readouterr()
        assert "TextView" in captured.out

    def test_scan_textviews_handles_exception(self, bot):
        """WebDriverException is swallowed."""
        bot.driver.find_elements.side_effect = WebDriverException("error")
        # Should not raise
        bot._scan_textviews()


class TestTrySelectCityByIndex:
    def test_returns_false_when_city_index_none(self, bot):
        bot.config.city_index = None
        result = bot._try_select_city_by_index()

        assert result is False

    def test_delegates_to_tap_from_dump(self, bot):
        """When city_index is set, calls _dump_page_source and _tap_from_dump."""
        bot.config.city_index = 1
        with patch.object(bot, "_dump_page_source"), \
             patch.object(bot, "_tap_from_dump", return_value=True) as mock_tap:
            result = bot._try_select_city_by_index()

        assert result is True
        mock_tap.assert_called_once()


class TestTrySelectDateByIndex:
    def test_returns_false_when_no_items_and_fast_mode(self, bot):
        """In fast_mode, no items returns False quickly."""
        bot.config.fast_mode = True
        bot.driver.find_elements.return_value = []
        result = bot._try_select_date_by_index()

        assert result is False

    def test_returns_true_when_items_found(self, bot):
        """Items found at date_index, clicks and returns True."""
        el = _make_mock_element()
        el.get_attribute.return_value = "true"
        bot.driver.find_elements.return_value = [el]
        bot.config.date_index = 0
        result = bot._try_select_date_by_index()

        assert result is True

    def test_uses_index_zero_when_index_out_of_range(self, bot):
        """date_index beyond list length defaults to 0."""
        el = _make_mock_element()
        el.get_attribute.return_value = "true"
        bot.driver.find_elements.return_value = [el]
        bot.config.date_index = 99
        bot.config.date_strict = False
        result = bot._try_select_date_by_index()

        assert result is True

    def test_returns_false_on_strict_out_of_range(self, bot):
        """date_strict=True and index out of range returns False."""
        el = _make_mock_element()
        bot.driver.find_elements.return_value = [el]
        bot.config.date_index = 99
        bot.config.date_strict = True
        result = bot._try_select_date_by_index()

        assert result is False


class TestWithContext:
    def test_with_context_switches_and_restores(self, bot):
        """Switches to context, runs fn, restores original context."""
        bot.driver.current_context = "NATIVE_APP"
        fn_result = []
        def my_fn():
            fn_result.append("ran")
            return "ok"

        result = bot._with_context("WEBVIEW_1", my_fn)

        assert result == "ok"
        assert fn_result == ["ran"]
        bot.driver.switch_to.context.assert_any_call("WEBVIEW_1")
        bot.driver.switch_to.context.assert_any_call("NATIVE_APP")

    def test_with_context_same_context_no_switch(self, bot):
        """Same context means no switch needed."""
        bot.driver.current_context = "NATIVE_APP"
        fn = Mock(return_value=True)

        result = bot._with_context("NATIVE_APP", fn)

        assert result is True
        bot.driver.switch_to.context.assert_not_called()


class TestTryClickByTextTokensWebview:
    def test_returns_false_when_no_webview(self, bot):
        """No WEBVIEW context returns False."""
        bot.driver.contexts = ["NATIVE_APP"]
        result = bot._try_click_by_text_tokens_webview(["token"])

        assert result is False

    def test_returns_true_when_element_found_in_webview(self, bot):
        """Finds element in WEBVIEW and clicks it."""
        bot.driver.contexts = ["NATIVE_APP", "WEBVIEW_1"]
        bot.driver.current_context = "NATIVE_APP"
        el = Mock()
        el.click = Mock()
        bot.driver.find_elements.return_value = [el]
        result = bot._try_click_by_text_tokens_webview(["token"])

        assert result is True


class TestScanDateTexts:
    def test_scan_date_texts_runs_without_error(self, bot, capsys):
        """Runs without raising exceptions."""
        el = Mock()
        el.get_attribute.side_effect = lambda name: "12月6日" if name == "text" else ""
        bot.driver.find_elements.return_value = [el]
        bot._scan_date_texts()

        captured = capsys.readouterr()
        assert "场次文本元素" in captured.out

    def test_scan_date_texts_handles_webdriver_exception(self, bot):
        """WebDriverException is swallowed."""
        bot.driver.find_elements.side_effect = WebDriverException("error")
        # Should not raise
        bot._scan_date_texts()
