# -*- coding: UTF-8 -*-
"""Unit tests for web/session_manager.py"""

import json
import os
import time
from unittest.mock import Mock, mock_open, patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session_manager(driver=None, config=None):
    from session_manager import SessionManager
    if driver is None:
        driver = Mock()
    if config is None:
        config = Mock()
        config.index_url = "https://www.damai.cn/"
        config.login_url = "https://passport.damai.cn/login"
        config.target_url = "https://detail.damai.cn/item.htm?id=123"
    return SessionManager(driver, config)


# ---------------------------------------------------------------------------
# get_cookie
# ---------------------------------------------------------------------------

class TestGetCookie:

    def test_loads_valid_cookies(self, tmp_path, monkeypatch):
        """Valid, non-expired cookie file is loaded into the driver."""
        from session_manager import COOKIE_FILE
        cookie_data = {
            "cookies": [{"name": "tk", "value": "abc123"}],
            "saved_at": time.time(),
        }
        cookie_file = tmp_path / COOKIE_FILE
        cookie_file.write_text(json.dumps(cookie_data), encoding="utf-8")

        driver = Mock()
        sm = _make_session_manager(driver=driver)

        monkeypatch.chdir(tmp_path)
        sm.get_cookie()

        driver.add_cookie.assert_called_once()
        call_args = driver.add_cookie.call_args[0][0]
        assert call_args["name"] == "tk"
        assert call_args["value"] == "abc123"
        assert call_args["domain"] == ".damai.cn"

    def test_expired_cookie_file_is_deleted(self, tmp_path, monkeypatch):
        """Cookie file older than 24h is removed and nothing is loaded."""
        from session_manager import COOKIE_FILE, COOKIE_MAX_AGE
        cookie_data = {
            "cookies": [{"name": "tk", "value": "abc123"}],
            "saved_at": time.time() - COOKIE_MAX_AGE - 1,
        }
        cookie_file = tmp_path / COOKIE_FILE
        cookie_file.write_text(json.dumps(cookie_data), encoding="utf-8")

        driver = Mock()
        sm = _make_session_manager(driver=driver)

        monkeypatch.chdir(tmp_path)
        sm.get_cookie()

        driver.add_cookie.assert_not_called()
        assert not cookie_file.exists()

    def test_missing_file_is_handled_gracefully(self, tmp_path, monkeypatch):
        """FileNotFoundError is caught; driver is not called."""
        driver = Mock()
        sm = _make_session_manager(driver=driver)

        monkeypatch.chdir(tmp_path)
        sm.get_cookie()  # should not raise

        driver.add_cookie.assert_not_called()

    def test_invalid_json_is_handled_and_deleted(self, tmp_path, monkeypatch):
        """Corrupt JSON file is deleted and no exception propagates."""
        from session_manager import COOKIE_FILE
        cookie_file = tmp_path / COOKIE_FILE
        cookie_file.write_text("not valid json", encoding="utf-8")

        driver = Mock()
        sm = _make_session_manager(driver=driver)

        monkeypatch.chdir(tmp_path)
        sm.get_cookie()  # should not raise

        driver.add_cookie.assert_not_called()
        assert not cookie_file.exists()

    def test_multiple_cookies_all_loaded(self, tmp_path, monkeypatch):
        """All cookies in the file are injected into the driver."""
        from session_manager import COOKIE_FILE
        cookie_data = {
            "cookies": [
                {"name": "tk", "value": "abc"},
                {"name": "sid", "value": "def"},
            ],
            "saved_at": time.time(),
        }
        cookie_file = tmp_path / COOKIE_FILE
        cookie_file.write_text(json.dumps(cookie_data), encoding="utf-8")

        driver = Mock()
        sm = _make_session_manager(driver=driver)

        monkeypatch.chdir(tmp_path)
        sm.get_cookie()

        assert driver.add_cookie.call_count == 2


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------

class TestLogin:

    def test_login_method_0_navigates_to_login_url(self):
        driver = Mock()
        sm = _make_session_manager(driver=driver)
        sm.login(0)
        driver.get.assert_called_once_with(sm.config.login_url)

    def test_login_method_1_calls_set_cookie_when_no_file(self, tmp_path, monkeypatch):
        """When no cookie file exists, login(1) should call set_cookie."""
        from session_manager import COOKIE_FILE
        monkeypatch.chdir(tmp_path)  # ensure no existing cookie file

        driver = Mock()
        sm = _make_session_manager(driver=driver)

        with patch.object(sm, "set_cookie") as mock_set_cookie:
            sm.login(1)
            mock_set_cookie.assert_called_once()

    def test_login_method_1_loads_existing_cookie_file(self, tmp_path, monkeypatch):
        """When cookie file exists, login(1) navigates to target_url then loads cookies."""
        from session_manager import COOKIE_FILE
        cookie_data = {
            "cookies": [{"name": "tk", "value": "val"}],
            "saved_at": time.time(),
        }
        (tmp_path / COOKIE_FILE).write_text(json.dumps(cookie_data), encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        driver = Mock()
        sm = _make_session_manager(driver=driver)

        with patch.object(sm, "get_cookie") as mock_get_cookie:
            sm.login(1)
            driver.get.assert_called_once_with(sm.config.target_url)
            mock_get_cookie.assert_called_once()

    def test_login_unknown_method_does_nothing(self, tmp_path, monkeypatch):
        """Unknown login_method doesn't navigate or raise."""
        monkeypatch.chdir(tmp_path)
        driver = Mock()
        sm = _make_session_manager(driver=driver)
        sm.login(2)  # neither 0 nor 1
        driver.get.assert_not_called()


# ---------------------------------------------------------------------------
# get_cookie — OSError handler
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# set_cookie
# ---------------------------------------------------------------------------

class TestSetCookie:

    def test_set_cookie_loops_until_login_complete(self, tmp_path, monkeypatch):
        """set_cookie: while-loop bodies (sleep calls) are executed when title transitions."""
        from session_manager import COOKIE_FILE
        from unittest.mock import PropertyMock

        PRE_LOGIN = "大麦网-全球演出赛事官方购票平台"
        OTHER = "其他页面"
        LOGGED_IN = "大麦网-全球演出赛事官方购票平台-100%正品、先付先抢、在线选座！"

        driver = Mock()
        # Sequence: in first while → sleep → exit first while
        #           in second while → sleep → exit second while
        titles = iter([PRE_LOGIN, OTHER, OTHER, LOGGED_IN])
        type(driver).title = PropertyMock(side_effect=lambda: next(titles))
        driver.get_cookies.return_value = []

        sm = _make_session_manager(driver=driver)
        monkeypatch.chdir(tmp_path)

        with patch("session_manager.sleep") as mock_sleep:
            sm.set_cookie()

        assert mock_sleep.call_count == 2  # once per while body

    def test_set_cookie_saves_file_and_navigates_to_target(self, tmp_path, monkeypatch):
        """set_cookie persists cookies to file and navigates to target_url."""
        from session_manager import COOKIE_FILE
        from unittest.mock import PropertyMock

        LOGGED_IN_TITLE = "大麦网-全球演出赛事官方购票平台-100%正品、先付先抢、在线选座！"

        driver = Mock()
        # First title query: doesn't contain the waiting string → first while exits immediately
        # Second title query: equals the logged-in title → second while exits immediately
        titles = iter(["其他页面", LOGGED_IN_TITLE])
        type(driver).title = PropertyMock(side_effect=lambda: next(titles))
        driver.get_cookies.return_value = [{"name": "tk", "value": "abc123"}]

        sm = _make_session_manager(driver=driver)
        monkeypatch.chdir(tmp_path)

        with patch("session_manager.sleep"):
            sm.set_cookie()

        cookie_file = tmp_path / COOKIE_FILE
        assert cookie_file.exists()
        import json as _json
        data = _json.loads(cookie_file.read_text())
        assert len(data["cookies"]) == 1
        assert "saved_at" in data
        driver.get.assert_called_with(sm.config.target_url)


class TestGetCookieOSError:

    def test_os_remove_failure_is_silenced(self, tmp_path, monkeypatch):
        """If os.remove raises OSError after JSON decode error, it's swallowed."""
        from session_manager import COOKIE_FILE
        cookie_file = tmp_path / COOKIE_FILE
        cookie_file.write_text("not valid json", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        driver = Mock()
        sm = _make_session_manager(driver=driver)

        with patch("session_manager.os.remove", side_effect=OSError("locked")):
            sm.get_cookie()  # should not raise

        driver.add_cookie.assert_not_called()
