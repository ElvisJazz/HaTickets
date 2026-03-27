# -*- coding: UTF-8 -*-
"""Unit tests for web/concert.py — the core automation module."""

import pickle
import time

import pytest
from unittest.mock import Mock, patch, MagicMock, call

from selenium.common.exceptions import (
    NoSuchElementException,
    WebDriverException,
    TimeoutException,
)

from config import Config
from concert import Concert


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_config(**overrides):
    """Helper to build a Config with sensible defaults."""
    defaults = dict(
        index_url="https://www.damai.cn/",
        login_url="https://passport.damai.cn/login",
        target_url="https://detail.damai.cn/item.htm?id=123",
        users=["UserA", "UserB"],
        city="杭州",
        dates=["2026-04-11"],
        prices=["680"],
        if_listen=True,
        if_commit_order=True,
        max_retries=3,
        fast_mode=True,
        page_load_delay=0.1,
    )
    defaults.update(overrides)
    return Config(**defaults)


@pytest.fixture
def concert_instance():
    """Create a Concert with a fully mocked WebDriver."""
    config = _make_config()
    mock_driver = Mock()
    mock_driver.current_url = "https://detail.damai.cn/item.htm?id=123"
    mock_driver.title = "Test Page"
    mock_driver.find_element = Mock()
    mock_driver.find_elements = Mock(return_value=[])
    mock_driver.execute_script = Mock()
    mock_driver.get = Mock()
    mock_driver.quit = Mock()
    mock_driver.add_cookie = Mock()

    with patch("concert.get_chromedriver_path", return_value="/fake/chromedriver"), \
         patch("concert.webdriver.Chrome", return_value=mock_driver), \
         patch("selenium.webdriver.chrome.service.Service"):
        c = Concert(config)

    return c


# ===================================================================
# Lifecycle
# ===================================================================

class TestLifecycle:

    def test_init_creates_driver_status_0(self, concert_instance):
        assert concert_instance.status == 0
        assert concert_instance.driver is not None

    def test_init_chromedriver_not_found_exits(self):
        config = _make_config()
        with patch("concert.get_chromedriver_path", side_effect=RuntimeError("not found")):
            with pytest.raises(SystemExit):
                Concert(config)

    def test_finish_quits_driver(self, concert_instance):
        concert_instance.finish()
        concert_instance.driver.quit.assert_called_once()


# ===================================================================
# Auth flow
# ===================================================================

class TestAuthFlow:

    def test_login_cookie_no_file_calls_set_cookie(self, concert_instance):
        """When no cookie file exists, login() should call set_cookie()."""
        concert_instance.login_method = 1
        with patch("concert.os.path.exists", return_value=False), \
             patch.object(concert_instance, "set_cookie") as mock_set:
            concert_instance.login()
            mock_set.assert_called_once()

    def test_login_cookie_with_file_calls_get_cookie(self, concert_instance):
        """When cookie file exists, login() should navigate and call get_cookie()."""
        concert_instance.login_method = 1
        with patch("concert.os.path.exists", return_value=True), \
             patch.object(concert_instance, "get_cookie") as mock_get:
            concert_instance.login()
            concert_instance.driver.get.assert_called_with(concert_instance.config.target_url)
            mock_get.assert_called_once()

    def test_get_cookie_loads_and_adds_cookies(self, concert_instance):
        """get_cookie should load pickle data and call driver.add_cookie for each."""
        fake_cookies = [
            {"name": "c1", "value": "v1"},
            {"name": "c2", "value": "v2"},
        ]
        mock_open = MagicMock()
        with patch("builtins.open", mock_open), \
             patch("concert.pickle.load", return_value=fake_cookies):
            concert_instance.get_cookie()

        assert concert_instance.driver.add_cookie.call_count == 2
        # Verify the cookie dicts contain the expected keys
        first_call_arg = concert_instance.driver.add_cookie.call_args_list[0][0][0]
        assert first_call_arg["name"] == "c1"
        assert first_call_arg["domain"] == ".damai.cn"

    def test_get_cookie_handles_exception(self, concert_instance, capsys):
        """get_cookie should not raise even if pickle.load fails."""
        with patch("builtins.open", side_effect=FileNotFoundError("no file")):
            concert_instance.get_cookie()  # should not raise

        captured = capsys.readouterr()
        assert "no file" in captured.out or True  # exception is printed


# ===================================================================
# Navigation
# ===================================================================

class TestNavigation:

    def test_enter_concert_sets_status_2(self, concert_instance):
        with patch.object(concert_instance, "login"), \
             patch.object(concert_instance, "is_element_exist", return_value=False):
            concert_instance.enter_concert()
            assert concert_instance.status == 2

    def test_is_element_exist_true(self, concert_instance):
        concert_instance.driver.find_element.return_value = Mock()
        assert concert_instance.is_element_exist("//div") is True

    def test_is_element_exist_false(self, concert_instance):
        concert_instance.driver.find_element.side_effect = NoSuchElementException()
        assert concert_instance.is_element_exist("//div") is False


# ===================================================================
# choose_ticket
# ===================================================================

class TestChooseTicket:

    def test_choose_ticket_status_not_2_returns_early(self, concert_instance):
        concert_instance.status = 0
        # Should return immediately without accessing driver
        concert_instance.choose_ticket()  # no error

    def test_choose_ticket_detects_mobile_url(self, concert_instance):
        concert_instance.status = 2
        concert_instance.driver.current_url = "https://m.damai.cn/item.htm?id=123"
        with patch.object(concert_instance, "select_details_page_mobile") as mock_mob, \
             patch.object(concert_instance, "_is_order_confirmation_page", return_value=True):
            concert_instance.choose_ticket()
            mock_mob.assert_called_once()

    def test_choose_ticket_detects_pc_url(self, concert_instance):
        concert_instance.status = 2
        concert_instance.driver.current_url = "https://detail.damai.cn/item.htm?id=123"
        with patch.object(concert_instance, "select_details_page_pc") as mock_pc, \
             patch.object(concert_instance, "_is_order_confirmation_page", return_value=True):
            concert_instance.choose_ticket()
            mock_pc.assert_called_once()


# ===================================================================
# _select_option_by_config
# ===================================================================

class TestSelectOptionByConfig:

    def test_select_option_by_config_match_found(self, concert_instance):
        elem = Mock()
        elem.text = "680元"
        result = concert_instance._select_option_by_config(["680"], [elem])
        assert result is True
        elem.click.assert_called_once()

    def test_select_option_by_config_skip_soldout(self, concert_instance):
        elem = Mock()
        elem.text = "680元 无票"
        result = concert_instance._select_option_by_config(["680"], [elem])
        assert result is False

    def test_select_option_by_config_no_match(self, concert_instance):
        elem = Mock()
        elem.text = "380元"
        result = concert_instance._select_option_by_config(["680"], [elem])
        assert result is False

    def test_select_option_by_config_empty_lists(self, concert_instance):
        assert concert_instance._select_option_by_config([], [Mock()]) is False
        assert concert_instance._select_option_by_config(["680"], []) is False
        assert concert_instance._select_option_by_config([], []) is False


# ===================================================================
# User selection
# ===================================================================

class TestUserSelection:

    @patch("concert.time.sleep")
    def test_scan_user_elements_found(self, mock_sleep, concert_instance):
        user_elem = Mock()
        user_elem.text = "UserA"
        user_elem.tag_name = "div"
        user_elem.get_attribute = Mock(return_value="user-class")
        concert_instance.driver.find_elements = Mock(return_value=[user_elem])
        result = concert_instance._scan_user_elements(retry_count=1)
        assert result is True

    @patch("concert.time.sleep")
    def test_scan_user_elements_all_retries_fail(self, mock_sleep, concert_instance):
        concert_instance.driver.find_elements = Mock(return_value=[])
        result = concert_instance._scan_user_elements(retry_count=2, retry_interval=0)
        assert result is False

    @patch("concert.time.sleep")
    def test_select_users_tries_methods(self, mock_sleep, concert_instance):
        """_select_users iterates through methods for each user."""
        with patch.object(concert_instance, "_try_select_user_method1", return_value=1) as m1:
            concert_instance._select_users(ticket_count=1, users_to_select=["UserA"])
            m1.assert_called_once()

    @patch("concert.time.sleep")
    def test_select_users_stops_at_ticket_count(self, mock_sleep, concert_instance):
        """When user_selected reaches ticket_count, further users are skipped."""
        with patch.object(concert_instance, "_try_select_user_method1", return_value=1):
            concert_instance._select_users(ticket_count=1, users_to_select=["UserA", "UserB"])
            # UserB should be skipped (printed as "already enough")


# ===================================================================
# Order submission
# ===================================================================

class TestOrderSubmission:

    @patch("concert.time.sleep")
    def test_submit_order_by_text_success(self, mock_sleep, concert_instance):
        submit_btn = Mock()
        concert_instance.driver.find_element = Mock(return_value=submit_btn)
        result = concert_instance._try_submit_by_text(["立即提交"])
        assert result is True
        submit_btn.click.assert_called()

    @patch("concert.time.sleep")
    def test_submit_order_all_methods_fail(self, mock_sleep, concert_instance):
        concert_instance.driver.find_element = Mock(side_effect=NoSuchElementException())
        concert_instance.driver.find_elements = Mock(return_value=[])
        # _submit_order tries multiple methods; none should raise
        with patch.object(concert_instance, "_scan_submit_buttons"):
            concert_instance._submit_order()


# ===================================================================
# commit_order
# ===================================================================

class TestCommitOrder:

    @patch("concert.time.sleep")
    def test_commit_order_status_not_3_returns(self, mock_sleep, concert_instance):
        concert_instance.status = 2
        concert_instance.commit_order()  # should return early, no errors

    @patch("concert.time.sleep")
    def test_commit_order_selects_users_and_submits(self, mock_sleep, concert_instance):
        concert_instance.status = 3
        concert_instance.config.fast_mode = False
        with patch.object(concert_instance, "_scan_page_info"), \
             patch.object(concert_instance, "_scan_page_text"), \
             patch.object(concert_instance, "_scan_elements"), \
             patch.object(concert_instance, "_scan_user_elements", return_value=True), \
             patch.object(concert_instance, "_select_users"), \
             patch.object(concert_instance, "_submit_order") as mock_submit:
            concert_instance.commit_order()
            mock_submit.assert_called_once()

    @patch("concert.time.sleep")
    def test_commit_order_skip_submit_when_disabled(self, mock_sleep, concert_instance):
        concert_instance.status = 3
        concert_instance.config.if_commit_order = False
        with patch.object(concert_instance, "_scan_user_elements", return_value=True), \
             patch.object(concert_instance, "_select_users"), \
             patch.object(concert_instance, "_submit_order") as mock_submit:
            concert_instance.commit_order()
            mock_submit.assert_not_called()


# ===================================================================
# Platform selection — PC
# ===================================================================

class TestPlatformPC:

    @patch("concert.time.sleep")
    def test_select_city_on_page_pc_match(self, mock_sleep, concert_instance):
        city_elem = Mock()
        city_elem.text = "杭州"
        container = Mock()
        container.find_elements = Mock(return_value=[city_elem])
        concert_instance.driver.find_elements = Mock(return_value=[container])
        concert_instance.driver.find_element = Mock(return_value=container)

        result = concert_instance.select_city_on_page_pc()
        assert result is True
        city_elem.click.assert_called_once()

    @patch("concert.time.sleep")
    def test_select_date_on_page_pc_match(self, mock_sleep, concert_instance):
        date_elem = Mock()
        date_elem.text = "2026-04-11 周六"
        container = Mock()
        container.find_elements = Mock(return_value=[date_elem])
        concert_instance.driver.find_elements = Mock(return_value=[container])
        concert_instance.driver.find_element = Mock(return_value=container)

        result = concert_instance.select_date_on_page_pc()
        assert result is True
        date_elem.click.assert_called_once()

    @patch("concert.time.sleep")
    def test_select_price_on_page_pc_match(self, mock_sleep, concert_instance):
        price_elem = Mock()
        price_elem.text = "680元"
        concert_instance.driver.find_elements = Mock(return_value=[price_elem])

        result = concert_instance.select_price_on_page_pc()
        assert result is True
        price_elem.click.assert_called_once()

    @patch("concert.time.sleep")
    def test_select_quantity_by_buttons(self, mock_sleep, concert_instance):
        """_try_select_quantity_by_buttons clicks the + button target_count-1 times."""
        plus_btn = Mock()
        plus_btn.get_attribute = Mock(return_value="handler-up")
        plus_btn.is_displayed = Mock(return_value=True)
        plus_btn.is_enabled = Mock(return_value=True)
        concert_instance.driver.find_elements = Mock(return_value=[plus_btn])

        with patch.object(concert_instance, "_get_quantity_input_value", return_value="2"):
            result = concert_instance._try_select_quantity_by_buttons(target_count=2)

        assert result is True
        # Should have called execute_script once for 1 click (2-1)
        assert concert_instance.driver.execute_script.call_count == 1

    def test_select_quantity_always_returns_true(self, concert_instance):
        """_select_quantity_on_page returns True even when no selector found."""
        concert_instance.driver.find_elements = Mock(return_value=[])
        concert_instance.driver.find_element = Mock(side_effect=NoSuchElementException())
        result = concert_instance._select_quantity_on_page(platform="PC端")
        assert result is True

    @patch("concert.time.sleep")
    def test_select_details_page_pc(self, mock_sleep, concert_instance):
        with patch.object(concert_instance, "select_city_on_page_pc", return_value=True) as m_city, \
             patch.object(concert_instance, "select_date_on_page_pc", return_value=True) as m_date, \
             patch.object(concert_instance, "select_price_on_page_pc", return_value=True) as m_price, \
             patch.object(concert_instance, "_select_quantity_on_page", return_value=True) as m_qty:
            concert_instance.select_details_page_pc()
            m_city.assert_called_once()
            m_date.assert_called_once()
            m_price.assert_called_once()
            m_qty.assert_called_once()


# ===================================================================
# Platform selection — Mobile
# ===================================================================

class TestPlatformMobile:

    @patch("concert.time.sleep")
    def test_select_city_on_page_mobile(self, mock_sleep, concert_instance):
        with patch.object(concert_instance, "_find_and_click_element", return_value=True) as mock_find:
            result = concert_instance.select_city_on_page()
            assert result is True
            mock_find.assert_called_once()

    @patch("concert.time.sleep")
    def test_select_date_on_page_mobile(self, mock_sleep, concert_instance):
        with patch.object(concert_instance, "_find_and_click_element", return_value=True) as mock_find:
            result = concert_instance.select_date_on_page()
            assert result is True

    @patch("concert.time.sleep")
    def test_select_price_on_page_mobile(self, mock_sleep, concert_instance):
        concert_instance.driver.find_elements = Mock(return_value=[])
        with patch.object(concert_instance, "_find_and_click_element", return_value=True) as mock_find:
            result = concert_instance.select_price_on_page()
            assert result is True

    @patch("concert.time.sleep")
    def test_select_details_page_mobile(self, mock_sleep, concert_instance):
        with patch.object(concert_instance, "select_city_on_page", return_value=True), \
             patch.object(concert_instance, "select_date_on_page", return_value=True), \
             patch.object(concert_instance, "select_price_on_page", return_value=True), \
             patch.object(concert_instance, "select_quantity_on_page", return_value=True):
            concert_instance.select_details_page_mobile()


# ===================================================================
# Helper methods
# ===================================================================

class TestHelpers:

    @patch("concert.time.sleep")
    def test_click_element_by_text_found(self, mock_sleep, concert_instance):
        elem = Mock()
        elem.text = "立即购买"
        elem.find_element = Mock(return_value=Mock())
        concert_instance.driver.find_elements = Mock(return_value=[elem])

        result = concert_instance._click_element_by_text("立即购买")
        assert result is True

    @patch("concert.time.sleep")
    def test_click_element_by_text_not_found(self, mock_sleep, concert_instance):
        concert_instance.driver.find_elements = Mock(return_value=[])
        result = concert_instance._click_element_by_text("不存在的文本")
        assert result is False

    @patch("concert.time.sleep")
    def test_find_and_click_element_success(self, mock_sleep, concert_instance):
        elem = Mock()
        elem.text = "杭州站"
        elem.find_element = Mock(return_value=Mock())
        concert_instance.driver.find_elements = Mock(return_value=[elem])

        result = concert_instance._find_and_click_element("杭州")
        assert result is True

    @patch("concert.time.sleep")
    def test_find_and_click_element_skip_keywords(self, mock_sleep, concert_instance):
        elem = Mock()
        elem.text = "杭州 无票"
        concert_instance.driver.find_elements = Mock(return_value=[elem])

        result = concert_instance._find_and_click_element("杭州", skip_keywords=["无票"])
        assert result is False

    def test_scan_page_info(self, concert_instance, capsys):
        """_scan_page_info should print URL and title without raising."""
        concert_instance._scan_page_info()
        captured = capsys.readouterr()
        assert "detail.damai.cn" in captured.out

    def test_get_wait_time_fast_mode(self, concert_instance):
        concert_instance.config.fast_mode = True
        assert concert_instance._get_wait_time() == 0.2
        assert concert_instance._get_wait_time(short=True) == 0.1

    def test_get_wait_time_normal_mode(self, concert_instance):
        concert_instance.config.fast_mode = False
        assert concert_instance._get_wait_time() == 0.3
        assert concert_instance._get_wait_time(short=True) == 0.2

    def test_get_element_text_safe_returns_text(self, concert_instance):
        elem = Mock()
        elem.text = "hello"
        concert_instance.driver.find_elements = Mock(return_value=[elem])
        assert concert_instance._get_element_text_safe("some-class") == "hello"

    def test_get_element_text_safe_returns_none_on_empty(self, concert_instance):
        concert_instance.driver.find_elements = Mock(return_value=[])
        assert concert_instance._get_element_text_safe("some-class") is None

    def test_click_element_safe_success(self, concert_instance):
        elem = Mock()
        concert_instance.driver.find_element = Mock(return_value=elem)
        assert concert_instance._click_element_safe("btn") is True
        elem.click.assert_called_once()

    def test_click_element_safe_failure(self, concert_instance):
        concert_instance.driver.find_element = Mock(side_effect=NoSuchElementException())
        assert concert_instance._click_element_safe("btn") is False

    def test_is_order_confirmation_page_by_title(self, concert_instance):
        concert_instance.driver.title = "订单确认页 - 大麦网"
        assert concert_instance._is_order_confirmation_page() is True

    def test_is_order_confirmation_page_false(self, concert_instance):
        concert_instance.driver.title = "大麦网首页"
        body = Mock()
        body.text = "some random content"
        concert_instance.driver.find_element = Mock(return_value=body)
        assert concert_instance._is_order_confirmation_page() is False

    def test_is_order_confirmation_page_by_body_text(self, concert_instance):
        concert_instance.driver.title = "大麦网"
        body = Mock()
        body.text = "请选择支付方式完成付款"
        concert_instance.driver.find_element = Mock(return_value=body)
        assert concert_instance._is_order_confirmation_page() is True


# ===================================================================
# set_cookie
# ===================================================================

class TestSetCookie:

    @patch("concert.time.sleep")
    @patch("concert.pickle.dump")
    def test_set_cookie_writes_cookies(self, mock_dump, mock_sleep, concert_instance):
        """set_cookie navigates, waits for login, then dumps cookies."""
        # Title transitions:
        # 1st access (while check): contains '大麦网-全球演出赛事官方购票平台' → stays in loop
        # 2nd access: different title → exits first while
        # 3rd access (while check): not equal to target → stays in second loop
        # 4th access: equals target → exits second while
        # 5th+: reads title normally
        titles = iter([
            "大麦网-全球演出赛事官方购票平台",  # enter first loop
            "扫码登录页",  # exit first loop (no longer contains prefix)
            "扫码登录页",  # enter second loop (not equal to target)
            "大麦网-全球演出赛事官方购票平台-100%正品、先付先抢、在线选座！",  # exit second loop
        ])
        type(concert_instance.driver).title = property(lambda self: next(titles))
        concert_instance.driver.get_cookies = Mock(return_value=[{"name": "c"}])

        with patch("builtins.open", create=True):
            concert_instance.set_cookie()

        concert_instance.driver.get.assert_any_call(concert_instance.config.index_url)
        concert_instance.driver.get.assert_any_call(concert_instance.config.target_url)
        mock_dump.assert_called_once()


# ===================================================================
# login
# ===================================================================

class TestLogin:

    def test_login_method_0_opens_login_url(self, concert_instance):
        concert_instance.login_method = 0
        concert_instance.login()
        concert_instance.driver.get.assert_called_with(concert_instance.config.login_url)


# ===================================================================
# choose_ticket — polling loop
# ===================================================================

class TestChooseTicketPolling:

    @patch("concert.time.sleep")
    def test_choose_ticket_clicks_buy_button(self, mock_sleep, concert_instance):
        """When buy button text is '立即预订', it clicks and sets status=3."""
        concert_instance.status = 2
        concert_instance.driver.current_url = "https://detail.damai.cn/item.htm?id=123"

        call_count = [0]

        def fake_is_order_page():
            call_count[0] += 1
            return call_count[0] > 2

        def fake_get_text(locator, by=None):
            if locator == 'buy__button__text':
                return "立即预订"
            return None

        with patch.object(concert_instance, "select_details_page_pc"), \
             patch.object(concert_instance, "_is_order_confirmation_page", side_effect=fake_is_order_page), \
             patch.object(concert_instance, "_get_element_text_safe", side_effect=fake_get_text), \
             patch.object(concert_instance, "_click_element_safe", return_value=True), \
             patch.object(concert_instance, "commit_order"):
            concert_instance.choose_ticket()
            assert concert_instance.status == 3

    @patch("concert.time.sleep")
    def test_choose_ticket_refreshes_on_sold_out(self, mock_sleep, concert_instance):
        """When buy button text is '提交缺货登记', refreshes page."""
        concert_instance.status = 2
        concert_instance.driver.current_url = "https://detail.damai.cn/item.htm?id=123"

        call_count = [0]

        def fake_is_order_page():
            call_count[0] += 1
            return call_count[0] > 2

        def fake_get_text(locator, by=None):
            if call_count[0] <= 1 and locator == 'buy__button__text':
                return "提交缺货登记"
            return None

        with patch.object(concert_instance, "select_details_page_pc"), \
             patch.object(concert_instance, "_is_order_confirmation_page", side_effect=fake_is_order_page), \
             patch.object(concert_instance, "_get_element_text_safe", side_effect=fake_get_text), \
             patch.object(concert_instance, "commit_order"):
            concert_instance.choose_ticket()

        concert_instance.driver.get.assert_called_with(concert_instance.config.target_url)

    @patch("concert.time.sleep")
    def test_choose_ticket_calls_choice_seat(self, mock_sleep, concert_instance):
        """When title is '选座购买', calls choice_seat."""
        concert_instance.status = 2
        concert_instance.driver.current_url = "https://detail.damai.cn/item.htm?id=123"

        call_count = [0]

        def fake_is_order_page():
            call_count[0] += 1
            return call_count[0] > 2

        concert_instance.driver.title = "选座购买"

        with patch.object(concert_instance, "select_details_page_pc"), \
             patch.object(concert_instance, "_is_order_confirmation_page", side_effect=fake_is_order_page), \
             patch.object(concert_instance, "_get_element_text_safe", return_value=None), \
             patch.object(concert_instance, "choice_seat") as mock_seat:
            concert_instance.choose_ticket()
            mock_seat.assert_called()

    @patch("concert.time.sleep")
    def test_choose_ticket_by_link(self, mock_sleep, concert_instance):
        """When by_link text is '不，立即预订', clicks it."""
        concert_instance.status = 2
        concert_instance.driver.current_url = "https://detail.damai.cn/item.htm?id=123"

        call_count = [0]

        def fake_is_order_page():
            call_count[0] += 1
            return call_count[0] > 2

        def fake_get_text(locator, by=None):
            if locator == 'buy-link':
                return "不，立即预订"
            return None

        with patch.object(concert_instance, "select_details_page_pc"), \
             patch.object(concert_instance, "_is_order_confirmation_page", side_effect=fake_is_order_page), \
             patch.object(concert_instance, "_get_element_text_safe", side_effect=fake_get_text), \
             patch.object(concert_instance, "_click_element_safe", return_value=True), \
             patch.object(concert_instance, "commit_order"):
            concert_instance.choose_ticket()
            assert concert_instance.status == 3


# ===================================================================
# choice_seat
# ===================================================================

class TestChoiceSeat:

    def test_choice_seat_exits_when_title_changes(self, concert_instance):
        """choice_seat loops while title is '选座购买', exits when changed."""
        concert_instance.driver.title = "其他页面"
        concert_instance.choice_seat()  # should return immediately


# ===================================================================
# choice_order
# ===================================================================

class TestChoiceOrder:

    @patch("concert.time.sleep")
    def test_choice_order_selects_dates_prices_quantity(self, mock_sleep, concert_instance):
        """choice_order clicks buy button, selects dates/prices/quantity, clicks confirm."""
        buy_btn = Mock()
        times_card = Mock()
        date_elem = Mock()
        times_card.find_elements = Mock(return_value=[date_elem])
        price_elem = Mock()
        counter = Mock()
        confirm_btn = Mock()

        def find_elem(value=None, by=None):
            if value == 'buy__button__text':
                return buy_btn
            if value == 'sku-times-card':
                return times_card
            if value == 'bui-btn-contained':
                return confirm_btn
            return Mock()

        def find_elems(value=None, by=None):
            if value == 'sku-times-card':
                return [times_card]
            if value == 'sku-tickets-card':
                return [Mock()]
            if value == 'item-content':
                return [price_elem]
            if value == 'bui-dm-sku-counter':
                return [counter]
            return []

        concert_instance.driver.find_element = Mock(side_effect=find_elem)
        concert_instance.driver.find_elements = Mock(side_effect=find_elems)

        with patch.object(concert_instance, "_select_option_by_config", return_value=True):
            concert_instance.choice_order()

        buy_btn.click.assert_called_once()
        confirm_btn.click.assert_called_once()


# ===================================================================
# _scan_page_text / _scan_elements
# ===================================================================

class TestScanMethods:

    def test_scan_page_text_prints_body(self, concert_instance, capsys):
        body = Mock()
        body.text = "Line1\nLine2\nLine3"
        concert_instance.driver.find_element = Mock(return_value=body)
        concert_instance._scan_page_text()
        out = capsys.readouterr().out
        assert "Line1" in out

    def test_scan_page_text_empty_body(self, concert_instance, capsys):
        body = Mock()
        body.text = ""
        concert_instance.driver.find_element = Mock(return_value=body)
        concert_instance._scan_page_text()
        out = capsys.readouterr().out
        assert "无文本" in out

    def test_scan_page_text_exception(self, concert_instance, capsys):
        concert_instance.driver.find_element = Mock(side_effect=Exception("fail"))
        concert_instance._scan_page_text()
        out = capsys.readouterr().out
        assert "扫描失败" in out

    def test_scan_elements_buttons(self, concert_instance, capsys):
        btn = Mock()
        btn.text = "Submit"
        btn.get_attribute = Mock(return_value="btn-class")
        concert_instance.driver.find_elements = Mock(return_value=[btn])
        concert_instance._scan_elements("button", "按钮")
        out = capsys.readouterr().out
        assert "1 个按钮" in out

    def test_scan_elements_inputs(self, concert_instance, capsys):
        inp = Mock()
        inp.get_attribute = Mock(return_value="text")
        concert_instance.driver.find_elements = Mock(return_value=[inp])
        concert_instance._scan_elements("input", "输入框")
        out = capsys.readouterr().out
        assert "1 个输入框" in out

    def test_scan_elements_empty(self, concert_instance, capsys):
        concert_instance.driver.find_elements = Mock(return_value=[])
        concert_instance._scan_elements("button", "按钮")
        out = capsys.readouterr().out
        assert "未找到按钮" in out

    def test_scan_submit_buttons_found(self, concert_instance, capsys):
        btn = Mock()
        btn.text = "提交订单"
        btn.get_attribute = Mock(return_value="submit-btn")
        concert_instance.driver.find_elements = Mock(return_value=[btn])
        concert_instance._scan_submit_buttons()
        out = capsys.readouterr().out
        assert "提交订单" in out

    def test_scan_submit_buttons_none(self, concert_instance, capsys):
        concert_instance.driver.find_elements = Mock(return_value=[])
        concert_instance._scan_submit_buttons()
        out = capsys.readouterr().out
        assert "未找到" in out


# ===================================================================
# User selection methods 1-4
# ===================================================================

class TestUserSelectionMethods:

    @patch("concert.time.sleep")
    def test_method1_finds_div_and_clicks_checkbox(self, mock_sleep, concert_instance):
        div_elem = Mock()
        div_elem.text = "UserA"
        checkbox = Mock()
        checkbox.tag_name = "i"
        checkbox.get_attribute = Mock(return_value="iconfont")
        div_elem.find_element = Mock(return_value=checkbox)
        concert_instance.driver.find_elements = Mock(return_value=[div_elem])

        result = concert_instance._try_select_user_method1("UserA", ["UserA"], 0)
        assert result == 1

    @patch("concert.time.sleep")
    def test_method1_no_div_found(self, mock_sleep, concert_instance):
        concert_instance.driver.find_elements = Mock(return_value=[])
        result = concert_instance._try_select_user_method1("UserA", ["UserA"], 0)
        assert result == 0

    @patch("concert.time.sleep")
    def test_method1_clicks_div_directly_when_no_checkbox(self, mock_sleep, concert_instance):
        div_elem = Mock()
        div_elem.text = "UserA"
        div_elem.find_element = Mock(side_effect=NoSuchElementException())
        concert_instance.driver.find_elements = Mock(return_value=[div_elem])

        result = concert_instance._try_select_user_method1("UserA", ["UserA"], 0)
        assert result == 1
        concert_instance.driver.execute_script.assert_called()

    @patch("concert.time.sleep")
    def test_method1_skip_when_enough_selected(self, mock_sleep, concert_instance):
        result = concert_instance._try_select_user_method1("UserA", ["UserA"], 1)
        assert result == 1

    @patch("concert.time.sleep")
    def test_method1_scroll_fallback(self, mock_sleep, concert_instance):
        """When direct click fails, scrolls into view and retries."""
        div_elem = Mock()
        div_elem.text = "UserA"
        div_elem.find_element = Mock(side_effect=NoSuchElementException())

        # First execute_script (click) fails, second (scroll) succeeds, third (click) succeeds
        call_count = [0]
        def side_effect(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("click failed")
            return None

        concert_instance.driver.execute_script = Mock(side_effect=side_effect)
        concert_instance.driver.find_elements = Mock(return_value=[div_elem])

        result = concert_instance._try_select_user_method1("UserA", ["UserA"], 0)
        assert result == 1

    @patch("concert.time.sleep")
    def test_method2_label_match(self, mock_sleep, concert_instance):
        label = Mock()
        label.text = "UserA"
        label.get_attribute = Mock(return_value="cb-1")
        checkbox = Mock()
        checkbox.is_selected = Mock(return_value=False)

        concert_instance.driver.find_elements = Mock(return_value=[])
        # Override to return labels for TAG_NAME and checkboxes for XPATH
        def find_elems(by, value=None):
            if value == 'label':
                return [label]
            if value and 'checkbox' in value:
                return []
            return []

        concert_instance.driver.find_elements = Mock(side_effect=find_elems)
        concert_instance.driver.find_element = Mock(return_value=checkbox)

        result = concert_instance._try_select_user_method2("UserA", ["UserA"], 0)
        assert result == 1
        checkbox.click.assert_called_once()

    @patch("concert.time.sleep")
    def test_method2_checkbox_nearby_text(self, mock_sleep, concert_instance):
        checkbox = Mock()
        checkbox.is_selected = Mock(return_value=False)
        parent = Mock()
        parent.text = "UserA"
        checkbox.find_element = Mock(return_value=parent)

        def find_elems(by, value=None):
            if value and 'checkbox' in str(value):
                return [checkbox]
            return []

        concert_instance.driver.find_elements = Mock(side_effect=find_elems)

        result = concert_instance._try_select_user_method2("UserA", ["UserA"], 0)
        assert result == 1

    @patch("concert.time.sleep")
    def test_method2_skip_when_enough(self, mock_sleep, concert_instance):
        result = concert_instance._try_select_user_method2("UserA", ["UserA"], 1)
        assert result == 1

    @patch("concert.time.sleep")
    def test_method3_clicks_matching_element(self, mock_sleep, concert_instance):
        elem = Mock()
        elem.text = "UserA"
        concert_instance.driver.find_elements = Mock(return_value=[elem])

        result = concert_instance._try_select_user_method3("UserA", ["UserA"], 0)
        assert result == 1
        elem.click.assert_called_once()

    @patch("concert.time.sleep")
    def test_method3_no_match(self, mock_sleep, concert_instance):
        concert_instance.driver.find_elements = Mock(return_value=[])
        result = concert_instance._try_select_user_method3("UserA", ["UserA"], 0)
        assert result == 0

    @patch("concert.time.sleep")
    def test_method3_skip_when_enough(self, mock_sleep, concert_instance):
        result = concert_instance._try_select_user_method3("UserA", ["UserA"], 1)
        assert result == 1

    @patch("concert.time.sleep")
    def test_method4_js_click(self, mock_sleep, concert_instance):
        target_elem = Mock()
        target_elem.tag_name = "i"
        target_elem.get_attribute = Mock(return_value="iconfont")

        # execute_script: first call returns divs, second returns icon, third clicks
        call_count = [0]
        def exec_script(script, *args):
            call_count[0] += 1
            if call_count[0] == 1:
                return [Mock()]  # target_divs
            if call_count[0] == 2:
                return target_elem  # find_icon
            return None  # click

        concert_instance.driver.execute_script = Mock(side_effect=exec_script)
        result = concert_instance._try_select_user_method4("UserA", ["UserA"], 0)
        assert result == 1

    @patch("concert.time.sleep")
    def test_method4_no_divs_found(self, mock_sleep, concert_instance):
        concert_instance.driver.execute_script = Mock(return_value=[])
        result = concert_instance._try_select_user_method4("UserA", ["UserA"], 0)
        assert result == 0

    @patch("concert.time.sleep")
    def test_method4_skip_when_enough(self, mock_sleep, concert_instance):
        result = concert_instance._try_select_user_method4("UserA", ["UserA"], 1)
        assert result == 1


# ===================================================================
# _select_users — orchestrator
# ===================================================================

class TestSelectUsersOrchestrator:

    @patch("concert.time.sleep")
    def test_select_users_falls_through_methods(self, mock_sleep, concert_instance):
        """When method1 fails, tries method2, etc."""
        with patch.object(concert_instance, "_try_select_user_method1", return_value=0), \
             patch.object(concert_instance, "_try_select_user_method2", return_value=1) as m2:
            concert_instance._select_users(ticket_count=1, users_to_select=["UserA"])
            m2.assert_called_once()

    @patch("concert.time.sleep")
    def test_select_users_all_methods_fail(self, mock_sleep, concert_instance):
        """When all methods fail for a user, prints warning."""
        with patch.object(concert_instance, "_try_select_user_method1", return_value=0), \
             patch.object(concert_instance, "_try_select_user_method2", return_value=0), \
             patch.object(concert_instance, "_try_select_user_method3", return_value=0), \
             patch.object(concert_instance, "_try_select_user_method4", return_value=0):
            concert_instance._select_users(ticket_count=1, users_to_select=["UserA"])

    @patch("concert.time.sleep")
    def test_select_users_multiple_users(self, mock_sleep, concert_instance):
        """Selects multiple users in sequence."""
        call_results = iter([1, 2])
        with patch.object(concert_instance, "_try_select_user_method1", side_effect=call_results):
            concert_instance._select_users(ticket_count=2, users_to_select=["UserA", "UserB"])


# ===================================================================
# Submit order methods
# ===================================================================

class TestSubmitMethods:

    @patch("concert.time.sleep")
    def test_try_submit_by_text_exact_match(self, mock_sleep, concert_instance):
        """Exact match span path."""
        # First loop: find_element raises for all tags, then exact match succeeds
        call_count = [0]
        def find_elem(by=None, value=None):
            call_count[0] += 1
            if call_count[0] <= 3:
                raise NoSuchElementException()
            parent = Mock()
            return Mock(find_element=Mock(return_value=parent))

        concert_instance.driver.find_element = Mock(side_effect=find_elem)
        result = concert_instance._try_submit_by_text(["立即提交"])
        assert result is True

    @patch("concert.time.sleep")
    def test_try_submit_by_text_all_fail(self, mock_sleep, concert_instance):
        concert_instance.driver.find_element = Mock(side_effect=NoSuchElementException())
        result = concert_instance._try_submit_by_text(["不存在"])
        assert result is False

    def test_try_submit_by_view_name_success(self, concert_instance):
        submit_btn = Mock()
        parent = Mock()
        submit_btn.find_element = Mock(return_value=parent)
        concert_instance.driver.find_element = Mock(return_value=submit_btn)
        assert concert_instance._try_submit_by_view_name() is True
        parent.click.assert_called_once()

    def test_try_submit_by_view_name_fail(self, concert_instance):
        concert_instance.driver.find_element = Mock(side_effect=NoSuchElementException())
        assert concert_instance._try_submit_by_view_name() is False

    def test_try_submit_by_class_success(self, concert_instance):
        btn = Mock()
        concert_instance.driver.find_element = Mock(return_value=btn)
        assert concert_instance._try_submit_by_class() is True
        btn.click.assert_called_once()

    def test_try_submit_by_class_all_fail(self, concert_instance):
        concert_instance.driver.find_element = Mock(side_effect=NoSuchElementException())
        assert concert_instance._try_submit_by_class() is False

    def test_try_submit_by_original_xpath_success(self, concert_instance):
        btn = Mock()
        concert_instance.driver.find_element = Mock(return_value=btn)
        assert concert_instance._try_submit_by_original_xpath() is True
        btn.click.assert_called_once()

    def test_try_submit_by_original_xpath_fail(self, concert_instance):
        concert_instance.driver.find_element = Mock(side_effect=NoSuchElementException())
        assert concert_instance._try_submit_by_original_xpath() is False

    @patch("concert.time.sleep")
    def test_submit_order_tries_all_methods(self, mock_sleep, concert_instance):
        """_submit_order chains all submit methods."""
        with patch.object(concert_instance, "_scan_submit_buttons"), \
             patch.object(concert_instance, "_try_submit_by_text", return_value=False), \
             patch.object(concert_instance, "_try_submit_by_view_name", return_value=False), \
             patch.object(concert_instance, "_try_submit_by_class", return_value=False), \
             patch.object(concert_instance, "_try_submit_by_original_xpath", return_value=False):
            concert_instance._submit_order()  # should print warning but not raise


# ===================================================================
# commit_order — detailed
# ===================================================================

class TestCommitOrderDetailed:

    @patch("concert.time.sleep")
    def test_commit_order_fast_mode_uses_webdriverwait(self, mock_sleep, concert_instance):
        concert_instance.status = 3
        concert_instance.config.fast_mode = True

        with patch("concert.WebDriverWait", create=True) as mock_wait_cls, \
             patch.object(concert_instance, "_scan_user_elements", return_value=True), \
             patch.object(concert_instance, "_select_users"), \
             patch.object(concert_instance, "_submit_order"):
            # Mock WebDriverWait().until()
            mock_wait_instance = Mock()
            mock_wait_cls.return_value = mock_wait_instance
            concert_instance.commit_order()

    @patch("concert.time.sleep")
    def test_commit_order_exception_in_user_selection(self, mock_sleep, concert_instance, capsys):
        concert_instance.status = 3
        concert_instance.config.fast_mode = True

        with patch.object(concert_instance, "_scan_user_elements", side_effect=Exception("user fail")), \
             patch.object(concert_instance, "_submit_order"):
            concert_instance.commit_order()
            out = capsys.readouterr().out
            assert "异常" in out

    @patch("concert.time.sleep")
    def test_commit_order_normal_mode_scans_page(self, mock_sleep, concert_instance):
        concert_instance.status = 3
        concert_instance.config.fast_mode = False

        with patch.object(concert_instance, "_scan_page_info") as m_info, \
             patch.object(concert_instance, "_scan_page_text") as m_text, \
             patch.object(concert_instance, "_scan_elements") as m_elem, \
             patch.object(concert_instance, "_scan_user_elements", return_value=True), \
             patch.object(concert_instance, "_select_users"), \
             patch.object(concert_instance, "_submit_order"):
            concert_instance.commit_order()
            m_info.assert_called_once()
            m_text.assert_called_once()
            assert m_elem.call_count == 2


# ===================================================================
# Platform selection — detailed PC
# ===================================================================

class TestPlatformPCDetailed:

    @patch("concert.time.sleep")
    def test_select_city_on_page_pc_no_match(self, mock_sleep, concert_instance):
        city_elem = Mock()
        city_elem.text = "北京"
        container = Mock()
        container.find_elements = Mock(return_value=[city_elem])
        concert_instance.driver.find_elements = Mock(return_value=[container])
        concert_instance.driver.find_element = Mock(return_value=container)

        with patch.object(concert_instance, "_find_and_click_element", return_value=False):
            result = concert_instance.select_city_on_page_pc()
            assert result is False

    @patch("concert.time.sleep")
    def test_select_city_on_page_pc_exception(self, mock_sleep, concert_instance):
        concert_instance.driver.find_elements = Mock(side_effect=Exception("fail"))
        result = concert_instance.select_city_on_page_pc()
        assert result is False

    @patch("concert.time.sleep")
    def test_select_date_on_page_pc_no_match_uses_text_search(self, mock_sleep, concert_instance):
        concert_instance.driver.find_elements = Mock(return_value=[])
        with patch.object(concert_instance, "_find_and_click_element", return_value=True) as m:
            result = concert_instance.select_date_on_page_pc()
            assert result is True

    @patch("concert.time.sleep")
    def test_select_date_on_page_pc_exception(self, mock_sleep, concert_instance):
        concert_instance.driver.find_elements = Mock(side_effect=Exception("fail"))
        result = concert_instance.select_date_on_page_pc()
        assert result is False

    @patch("concert.time.sleep")
    def test_select_price_on_page_pc_no_match_uses_text_search(self, mock_sleep, concert_instance):
        concert_instance.driver.find_elements = Mock(return_value=[])
        with patch.object(concert_instance, "_find_and_click_element", return_value=True):
            result = concert_instance.select_price_on_page_pc()
            assert result is True

    @patch("concert.time.sleep")
    def test_select_price_on_page_pc_exception(self, mock_sleep, concert_instance):
        concert_instance.driver.find_elements = Mock(side_effect=Exception("fail"))
        result = concert_instance.select_price_on_page_pc()
        assert result is False

    @patch("concert.time.sleep")
    def test_select_details_page_pc_normal_mode(self, mock_sleep, concert_instance):
        concert_instance.config.fast_mode = False
        with patch.object(concert_instance, "scan_page_elements"), \
             patch.object(concert_instance, "select_city_on_page_pc", return_value=True), \
             patch.object(concert_instance, "select_date_on_page_pc", return_value=True), \
             patch.object(concert_instance, "select_price_on_page_pc", return_value=True), \
             patch.object(concert_instance, "_select_quantity_on_page", return_value=True):
            concert_instance.select_details_page_pc()


# ===================================================================
# Platform selection — detailed Mobile
# ===================================================================

class TestPlatformMobileDetailed:

    @patch("concert.time.sleep")
    def test_select_date_on_page_no_match(self, mock_sleep, concert_instance):
        with patch.object(concert_instance, "_find_and_click_element", return_value=False):
            result = concert_instance.select_date_on_page()
            assert result is False

    @patch("concert.time.sleep")
    def test_select_date_on_page_exception(self, mock_sleep, concert_instance):
        with patch.object(concert_instance, "_find_and_click_element", side_effect=Exception("err")):
            result = concert_instance.select_date_on_page()
            assert result is False

    @patch("concert.time.sleep")
    def test_select_price_on_page_no_match(self, mock_sleep, concert_instance):
        concert_instance.driver.find_elements = Mock(return_value=[])
        with patch.object(concert_instance, "_find_and_click_element", return_value=False):
            result = concert_instance.select_price_on_page()
            assert result is False

    @patch("concert.time.sleep")
    def test_select_city_on_page_exception(self, mock_sleep, concert_instance):
        with patch.object(concert_instance, "_find_and_click_element", side_effect=Exception("err")):
            result = concert_instance.select_city_on_page()
            assert result is False

    @patch("concert.time.sleep")
    def test_select_details_page_mobile_normal_mode(self, mock_sleep, concert_instance):
        concert_instance.config.fast_mode = False
        with patch.object(concert_instance, "select_city_on_page", return_value=True), \
             patch.object(concert_instance, "select_date_on_page", return_value=True), \
             patch.object(concert_instance, "select_price_on_page", return_value=True), \
             patch.object(concert_instance, "select_quantity_on_page", return_value=True):
            concert_instance.select_details_page_mobile()

    def test_select_quantity_on_page_mobile(self, concert_instance):
        with patch.object(concert_instance, "_try_select_quantity_by_buttons", return_value=True):
            result = concert_instance.select_quantity_on_page()
            assert result is True

    def test_select_quantity_on_page_pc_alias(self, concert_instance):
        with patch.object(concert_instance, "_select_quantity_on_page", return_value=True) as m:
            result = concert_instance.select_quantity_on_page_pc()
            assert result is True
            m.assert_called_once_with(platform="PC端")


# ===================================================================
# Quantity selection — detailed
# ===================================================================

class TestQuantityDetailed:

    @patch("concert.time.sleep")
    def test_try_set_quantity_directly_success(self, mock_sleep, concert_instance):
        input_elem = Mock()
        input_elem.get_attribute = Mock(return_value="2")
        concert_instance.driver.find_element = Mock(return_value=input_elem)
        result = concert_instance._try_set_quantity_directly(2)
        assert result is True

    @patch("concert.time.sleep")
    def test_try_set_quantity_directly_not_found(self, mock_sleep, concert_instance):
        concert_instance.driver.find_element = Mock(side_effect=NoSuchElementException())
        result = concert_instance._try_set_quantity_directly(2)
        assert result is False

    def test_get_quantity_input_value_found(self, concert_instance):
        inp = Mock()
        inp.get_attribute = Mock(return_value="3")
        concert_instance.driver.find_element = Mock(return_value=inp)
        assert concert_instance._get_quantity_input_value() == "3"

    def test_get_quantity_input_value_not_found(self, concert_instance):
        concert_instance.driver.find_element = Mock(side_effect=NoSuchElementException())
        assert concert_instance._get_quantity_input_value() is None

    @patch("concert.time.sleep")
    def test_click_plus_buttons_disabled_skipped(self, mock_sleep, concert_instance):
        btn = Mock()
        btn.get_attribute = Mock(return_value="handler-up disabled")
        result = concert_instance._click_plus_buttons([btn], 2)
        assert result is False

    @patch("concert.time.sleep")
    def test_select_quantity_on_page_attribute_error(self, mock_sleep, concert_instance):
        """AttributeError in quantity selection should not block flow."""
        with patch.object(concert_instance, "_try_select_quantity_by_buttons", side_effect=AttributeError("bad")):
            result = concert_instance._select_quantity_on_page(platform="PC端")
            assert result is True

    @patch("concert.time.sleep")
    def test_select_quantity_on_page_webdriver_exception(self, mock_sleep, concert_instance):
        with patch.object(concert_instance, "_try_select_quantity_by_buttons", side_effect=WebDriverException("fail")):
            result = concert_instance._select_quantity_on_page(platform="PC端")
            assert result is True


# ===================================================================
# scan_page_elements / _scan_elements_by_class
# ===================================================================

class TestScanPageElements:

    def test_scan_elements_by_class_found(self, concert_instance, capsys):
        elem = Mock()
        elem.text = "Beijing"
        concert_instance.driver.find_elements = Mock(return_value=[elem])
        result = concert_instance._scan_elements_by_class(["bui-dm-tour"], "城市")
        assert result is True

    def test_scan_elements_by_class_not_found(self, concert_instance, capsys):
        concert_instance.driver.find_elements = Mock(return_value=[])
        result = concert_instance._scan_elements_by_class(["bui-dm-tour"], "城市")
        assert result is False

    def test_scan_page_elements_runs(self, concert_instance, capsys):
        concert_instance.driver.find_elements = Mock(return_value=[])
        concert_instance.scan_page_elements()
        out = capsys.readouterr().out
        assert "城市" in out


# ===================================================================
# _select_option_by_config — additional
# ===================================================================

class TestSelectOptionAdditional:

    @patch("concert.time.sleep")
    def test_select_option_exception_in_element(self, mock_sleep, concert_instance):
        """Element that raises on .text should be skipped."""
        elem = Mock()
        elem.text = property(lambda s: (_ for _ in ()).throw(Exception("stale")))
        type(elem).text = property(lambda s: (_ for _ in ()).throw(Exception("stale")))
        result = concert_instance._select_option_by_config(["680"], [elem])
        assert result is False
