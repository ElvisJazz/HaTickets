"""Unit tests for web/damai.py"""
import json
from unittest.mock import Mock, patch, mock_open

import pytest

from damai import check_config_file, load_config, grab


class TestCheckConfigFile:

    def test_missing_file_exits(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            check_config_file()

    def test_valid_config(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        config = {
            "index_url": "https://www.damai.cn/",
            "login_url": "https://passport.damai.cn/login",
            "target_url": "https://detail.damai.cn/item.htm?id=1",
            "users": ["A", "B"],
            "if_listen": True,
            "if_commit_order": True,
        }
        (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
        check_config_file()  # should not raise
        out = capsys.readouterr().out
        assert "加载成功" in out

    def test_missing_fields_exits(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.json").write_text('{"index_url": "x"}', encoding="utf-8")
        with pytest.raises(SystemExit):
            check_config_file()

    def test_empty_users_exits(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = {
            "index_url": "x", "login_url": "x", "target_url": "x",
            "users": [],
        }
        (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
        with pytest.raises(SystemExit):
            check_config_file()

    def test_invalid_json_exits(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.json").write_text("{bad json", encoding="utf-8")
        with pytest.raises(SystemExit):
            check_config_file()


class TestLoadConfig:

    def test_returns_config_object(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = {
            "index_url": "https://www.damai.cn/",
            "login_url": "https://passport.damai.cn/login",
            "target_url": "https://detail.damai.cn/item.htm?id=1",
            "users": ["A"],
            "city": "上海",
            "dates": ["2026-05-01"],
            "prices": ["580"],
            "if_listen": True,
            "if_commit_order": False,
            "max_retries": 50,
        }
        (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
        cfg = load_config()
        assert cfg.target_url == "https://detail.damai.cn/item.htm?id=1"
        assert cfg.users == ["A"]
        assert cfg.city == "上海"
        assert cfg.max_retries == 50

    def test_default_values(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = {
            "index_url": "x", "login_url": "x", "target_url": "x",
            "users": ["A"], "if_listen": True, "if_commit_order": True,
        }
        (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
        cfg = load_config()
        assert cfg.max_retries == 1000
        assert cfg.fast_mode is True
        assert cfg.page_load_delay == 2


class TestGrab:

    @patch("damai.time.sleep")
    @patch("damai.Concert")
    @patch("damai.load_config")
    @patch("damai.check_config_file")
    def test_full_flow(self, mock_check, mock_load, mock_concert_cls, mock_sleep):
        mock_config = Mock()
        mock_load.return_value = mock_config
        mock_con = Mock()
        mock_concert_cls.return_value = mock_con

        grab()

        mock_check.assert_called_once()
        mock_load.assert_called_once()
        mock_concert_cls.assert_called_once_with(mock_config)
        mock_con.enter_concert.assert_called_once()
        mock_con.choose_ticket.assert_called_once()

    @patch("damai.time.sleep")
    @patch("damai.Concert")
    @patch("damai.load_config")
    @patch("damai.check_config_file")
    def test_keyboard_interrupt(self, mock_check, mock_load, mock_concert_cls, mock_sleep):
        mock_con = Mock()
        mock_concert_cls.return_value = mock_con
        mock_con.enter_concert.side_effect = KeyboardInterrupt

        grab()  # should not raise

        mock_con.finish.assert_called_once()

    @patch("damai.time.sleep")
    @patch("damai.Concert")
    @patch("damai.load_config")
    @patch("damai.check_config_file")
    def test_generic_exception(self, mock_check, mock_load, mock_concert_cls, mock_sleep):
        mock_con = Mock()
        mock_concert_cls.return_value = mock_con
        mock_con.enter_concert.side_effect = RuntimeError("boom")

        grab()  # should not raise

        mock_con.finish.assert_called_once()
