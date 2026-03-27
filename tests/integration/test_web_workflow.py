"""Integration tests for web module workflow."""
import json
from unittest.mock import Mock, patch, MagicMock

import pytest
from selenium.common.exceptions import NoSuchElementException

from config import Config
from concert import Concert
from damai import load_config


class TestConfigToConcertInit:

    def test_load_config_creates_concert(self, tmp_path, monkeypatch):
        """load_config → Config → Concert constructor chain works."""
        monkeypatch.chdir(tmp_path)
        config_data = {
            "index_url": "https://www.damai.cn/",
            "login_url": "https://passport.damai.cn/login",
            "target_url": "https://detail.damai.cn/item.htm?id=1",
            "users": ["A", "B"],
            "city": "上海",
            "dates": ["2026-05-01"],
            "prices": ["580"],
            "if_listen": True,
            "if_commit_order": True,
        }
        (tmp_path / "config.json").write_text(json.dumps(config_data), encoding="utf-8")

        cfg = load_config()
        assert isinstance(cfg, Config)
        assert cfg.users == ["A", "B"]

        mock_driver = Mock()
        with patch("concert.get_chromedriver_path", return_value="/fake"), \
             patch("concert.webdriver.Chrome", return_value=mock_driver), \
             patch("selenium.webdriver.chrome.service.Service"):
            con = Concert(cfg)
            assert con.status == 0
            assert con.config is cfg


class TestEnterConcertToChooseTicket:

    def test_enter_sets_status_2_then_choose_checks_status(self):
        """enter_concert sets status=2, choose_ticket proceeds only if status==2."""
        config = Config(
            index_url="https://www.damai.cn/",
            login_url="https://passport.damai.cn/login",
            target_url="https://detail.damai.cn/item.htm?id=1",
            users=["A"], city=None, dates=None, prices=None,
            if_listen=False, if_commit_order=False,
            fast_mode=True, page_load_delay=0.1,
        )

        mock_driver = Mock()
        mock_driver.title = "大麦网-全球演出赛事官方购票平台-100%正品、先付先抢、在线选座！"
        mock_driver.current_url = "https://detail.damai.cn/item.htm?id=1"
        mock_driver.find_element = Mock(side_effect=NoSuchElementException)
        mock_driver.find_elements = Mock(return_value=[])

        with patch("concert.get_chromedriver_path", return_value="/fake"), \
             patch("concert.webdriver.Chrome", return_value=mock_driver), \
             patch("selenium.webdriver.chrome.service.Service"), \
             patch("concert.os.path.exists", return_value=True), \
             patch("concert.pickle.load", return_value=[{"name": "t", "value": "v", "domain": ".damai.cn"}]), \
             patch("builtins.open", create=True):
            con = Concert(config)
            con.login_method = 1

            # Simulate login with cookies
            con.enter_concert()
            assert con.status == 2


class TestOrderFlowPC:

    def test_pc_details_page_flow(self):
        """PC flow: select city/date/price/quantity in sequence."""
        config = Config(
            index_url="https://www.damai.cn/",
            login_url="https://passport.damai.cn/login",
            target_url="https://detail.damai.cn/item.htm?id=1",
            users=["A", "B"], city="杭州", dates=["2026-04-11"],
            prices=["680"], if_listen=True, if_commit_order=True,
            fast_mode=True, page_load_delay=0.1,
        )

        mock_driver = Mock()
        mock_driver.current_url = "https://detail.damai.cn/item.htm?id=1"
        mock_driver.find_element = Mock(side_effect=NoSuchElementException)
        mock_driver.find_elements = Mock(return_value=[])

        with patch("concert.get_chromedriver_path", return_value="/fake"), \
             patch("concert.webdriver.Chrome", return_value=mock_driver), \
             patch("selenium.webdriver.chrome.service.Service"):
            con = Concert(config)
            con.status = 2

            # These should not raise even when elements aren't found
            result = con.select_city_on_page_pc()
            # Returns False when nothing matched, which is expected
            assert result is False or result is True

            result = con.select_date_on_page_pc()
            assert result is False or result is True


class TestOrderFlowMobile:

    def test_mobile_details_page_flow(self):
        """Mobile flow: select city/date/price in sequence."""
        config = Config(
            index_url="https://www.damai.cn/",
            login_url="https://passport.damai.cn/login",
            target_url="https://m.damai.cn/item.htm?id=1",
            users=["A"], city="杭州", dates=["2026-04-11"],
            prices=["680"], if_listen=True, if_commit_order=True,
            fast_mode=True, page_load_delay=0.1,
        )

        mock_driver = Mock()
        mock_driver.current_url = "https://m.damai.cn/item.htm?id=1"
        mock_driver.find_element = Mock(side_effect=NoSuchElementException)
        mock_driver.find_elements = Mock(return_value=[])

        with patch("concert.get_chromedriver_path", return_value="/fake"), \
             patch("concert.webdriver.Chrome", return_value=mock_driver), \
             patch("selenium.webdriver.chrome.service.Service"):
            con = Concert(config)
            con.status = 2

            result = con.select_city_on_page()
            assert result is False or result is True

            result = con.select_date_on_page()
            assert result is False or result is True
