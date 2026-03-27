"""Unit tests for web/config.py"""
from config import Config


class TestWebConfig:

    def test_config_init_stores_all_attributes(self):
        cfg = Config(
            index_url="https://www.damai.cn/",
            login_url="https://passport.damai.cn/login",
            target_url="https://detail.damai.cn/item.htm?id=1",
            users=["Alice", "Bob"],
            city="上海",
            dates=["2026-05-01"],
            prices=["580"],
            if_listen=True,
            if_commit_order=False,
            max_retries=500,
            fast_mode=False,
            page_load_delay=3,
        )
        assert cfg.index_url == "https://www.damai.cn/"
        assert cfg.login_url == "https://passport.damai.cn/login"
        assert cfg.target_url == "https://detail.damai.cn/item.htm?id=1"
        assert cfg.users == ["Alice", "Bob"]
        assert cfg.city == "上海"
        assert cfg.dates == ["2026-05-01"]
        assert cfg.prices == ["580"]
        assert cfg.if_listen is True
        assert cfg.if_commit_order is False
        assert cfg.max_retries == 500
        assert cfg.fast_mode is False
        assert cfg.page_load_delay == 3

    def test_config_init_default_values(self):
        cfg = Config(
            index_url="u", login_url="l", target_url="t",
            users=[], city=None, dates=None, prices=None,
            if_listen=False, if_commit_order=False,
        )
        assert cfg.max_retries == 1000
        assert cfg.fast_mode is True
        assert cfg.page_load_delay == 2

    def test_config_init_custom_overrides_defaults(self):
        cfg = Config(
            index_url="u", login_url="l", target_url="t",
            users=[], city=None, dates=None, prices=None,
            if_listen=False, if_commit_order=False,
            max_retries=1, fast_mode=False, page_load_delay=0.5,
        )
        assert cfg.max_retries == 1
        assert cfg.fast_mode is False
        assert cfg.page_load_delay == 0.5
