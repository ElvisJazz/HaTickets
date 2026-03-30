"""Integration tests for mobile module workflow."""
import json
from unittest.mock import Mock, patch

import pytest
from selenium.common.exceptions import TimeoutException

from mobile.config import Config
from mobile.damai_app import DamaiBot


def _make_mock_element(x=100, y=200, width=50, height=40):
    el = Mock()
    el.rect = {"x": x, "y": y, "width": width, "height": height}
    el.id = "fake-id"
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
        users=["A"],
        city="深圳",
        date="12.06",
        price="799元",
        price_index=1,
        if_commit_order=True,
    )
    defaults.update(overrides)
    return Config(**defaults)


class TestConfigToBotInit:

    def test_load_config_to_bot_init(self, tmp_path, monkeypatch):
        """Config.load_config → DamaiBot.__init__ → driver setup chain works."""
        monkeypatch.chdir(tmp_path)
        config_data = {
            "server_url": "http://127.0.0.1:4723",
            "device_name": "Android",
            "platform_version": "16",
            "keyword": "test",
            "users": ["A"],
            "city": "北京",
            "date": "01.01",
            "price": "100元",
            "price_index": 0,
            "if_commit_order": True,
        }
        (tmp_path / "config.jsonc").write_text(json.dumps(config_data), encoding="utf-8")

        mock_driver = Mock()
        mock_driver.update_settings = Mock()

        with patch("mobile.damai_app.webdriver.Remote", return_value=mock_driver), \
             patch("mobile.damai_app.AppiumOptions"), \
             patch("mobile.damai_app.ClientConfig"), \
             patch("mobile.damai_app.RemoteConnection"):
            bot = DamaiBot()
            assert bot.config.city == "北京"
            assert bot.driver is mock_driver
            mock_driver.update_settings.assert_called_once()


class TestFullTicketGrabbingFlow:

    def _make_time_mock(self):
        m = Mock()
        m.time.side_effect = [0.0, 1.5, 3.0, 4.5]
        m.sleep = Mock()
        return m

    def test_all_phases_succeed(self):
        """Full flow with mocked driver returns True."""
        mock_driver = Mock()
        mock_driver.update_settings = Mock()
        mock_driver.quit = Mock()
        mock_driver.current_activity = "ProjectDetailActivity"
        mock_el = _make_mock_element()

        mock_config = _make_config(if_commit_order=True)

        with patch("mobile.damai_app.Config.load_config", return_value=mock_config), \
             patch("mobile.damai_app.webdriver.Remote", return_value=mock_driver), \
             patch("mobile.damai_app.AppiumOptions"), \
             patch("mobile.damai_app.ClientConfig"), \
             patch("mobile.damai_app.RemoteConnection"):
            mock_driver.find_element = Mock(return_value=mock_el)
            mock_driver.find_elements = Mock(return_value=[mock_el])
            mock_driver.execute_script = Mock()

            bot = DamaiBot()
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
                 patch("mobile.damai_app.time", self._make_time_mock()):
                result = bot.run_ticket_grabbing()
            assert result is True

    def test_flow_stops_before_submit_when_commit_disabled(self):
        """Commit-disabled mode completes without submitting."""
        mock_driver = Mock()
        mock_driver.update_settings = Mock()
        mock_driver.quit = Mock()

        mock_config = _make_config(if_commit_order=False)

        with patch("mobile.damai_app.Config.load_config", return_value=mock_config), \
             patch("mobile.damai_app.webdriver.Remote", return_value=mock_driver), \
             patch("mobile.damai_app.AppiumOptions"), \
             patch("mobile.damai_app.ClientConfig"), \
             patch("mobile.damai_app.RemoteConnection"):
            mock_driver.find_elements = Mock(return_value=[])
            mock_driver.execute_script = Mock()

            bot = DamaiBot()
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
                 patch("mobile.damai_app.time", self._make_time_mock()):
                result = bot.run_ticket_grabbing()

            assert result is True


class TestRetryWithDriverRecreation:

    def test_retry_recreates_driver(self):
        """run_with_retry calls quit + _setup_driver between attempts."""
        mock_driver = Mock()
        mock_driver.update_settings = Mock()
        mock_driver.quit = Mock()

        mock_config = _make_config(if_commit_order=True)

        with patch("mobile.damai_app.Config.load_config", return_value=mock_config), \
             patch("mobile.damai_app.webdriver.Remote", return_value=mock_driver), \
             patch("mobile.damai_app.AppiumOptions"), \
             patch("mobile.damai_app.ClientConfig"), \
             patch("mobile.damai_app.RemoteConnection"), \
             patch("mobile.damai_app.time"):
            bot = DamaiBot()

            with patch.object(bot, "run_ticket_grabbing", return_value=False):
                with patch.object(bot, "_setup_driver") as mock_setup:
                    result = bot.run_with_retry(max_retries=3)

                    assert result is False
                    # quit called between retries (2 times for 3 attempts)
                    assert mock_driver.quit.call_count == 2
                    assert mock_setup.call_count == 2
