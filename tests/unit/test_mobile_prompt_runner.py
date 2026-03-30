# -*- coding: UTF-8 -*-
"""Unit tests for mobile/prompt_runner.py"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from mobile.prompt_parser import parse_prompt
from mobile.prompt_runner import (
    _split_city_and_venue,
    _format_price_option,
    _format_summary,
    _prompt_yes_no,
    _prompt_choice,
    _resolve_confirmed_date,
    _resolve_confirmed_price,
    build_updated_config,
    parse_args,
    _repo_root,
    _config_path,
    MODE_FLAGS,
)


# ---------------------------------------------------------------------------
# _repo_root / _config_path
# ---------------------------------------------------------------------------

def test_repo_root_returns_path():
    root = _repo_root()
    assert root.is_dir()


def test_config_path_points_to_mobile_config():
    path = _config_path()
    assert path.name == "config.jsonc"
    assert path.parent.name == "mobile"


# ---------------------------------------------------------------------------
# _split_city_and_venue
# ---------------------------------------------------------------------------

class TestSplitCityAndVenue:

    def test_with_dot_separator(self):
        city, venue = _split_city_and_venue("北京市 · 国家体育场-鸟巢")
        assert city == "北京"
        assert venue == "国家体育场-鸟巢"

    def test_without_dot_returns_none_city(self):
        city, venue = _split_city_and_venue("国家体育场-鸟巢")
        assert city is None
        assert venue == "国家体育场-鸟巢"

    def test_none_input(self):
        city, venue = _split_city_and_venue(None)
        assert city is None
        assert venue == ""

    def test_empty_string(self):
        city, venue = _split_city_and_venue("")
        assert city is None
        assert venue == ""

    def test_nbsp_is_treated_as_space(self):
        city, venue = _split_city_and_venue("上海市\u00a0·\u00a0梅赛德斯奔驰文化中心")
        assert city == "上海"
        assert venue == "梅赛德斯奔驰文化中心"

    def test_city_without_shi_suffix(self):
        city, venue = _split_city_and_venue("深圳 · 深圳湾体育中心")
        assert city == "深圳"
        assert venue == "深圳湾体育中心"


# ---------------------------------------------------------------------------
# _format_price_option
# ---------------------------------------------------------------------------

class TestFormatPriceOption:

    def test_minimal_option(self):
        result = _format_price_option({"index": 0, "text": "380元"})
        assert result == "[0] 380元"

    def test_with_tag(self):
        result = _format_price_option({"index": 1, "text": "580元", "tag": "可预约"})
        assert result == "[1] 580元 [可预约]"

    def test_with_ocr_source(self):
        result = _format_price_option({"index": 2, "text": "780元", "source": "ocr"})
        assert result == "[2] 780元 (OCR)"

    def test_with_tag_and_ocr(self):
        result = _format_price_option({"index": 3, "text": "1280元", "tag": "内场", "source": "ocr"})
        assert result == "[3] 1280元 [内场] (OCR)"

    def test_no_text_shows_placeholder(self):
        result = _format_price_option({"index": 0})
        assert "(未识别)" in result

    def test_non_ocr_source_not_shown(self):
        result = _format_price_option({"index": 0, "text": "380元", "source": "ui"})
        assert "(OCR)" not in result


# ---------------------------------------------------------------------------
# _format_summary
# ---------------------------------------------------------------------------

class TestFormatSummary:

    def _make_intent(self, prompt="帮我抢张杰演唱会门票"):
        return parse_prompt(prompt)

    def test_basic_summary(self):
        intent = self._make_intent()
        discovery = {
            "used_keyword": "张杰",
            "search_results": [],
            "summary": {
                "title": "张杰演唱会",
                "venue": "北京体育馆",
                "state": "selling",
                "reservation_mode": False,
                "dates": ["04.06"],
                "price_options": [{"index": 0, "text": "380元"}],
            },
        }
        result = _format_summary(intent, discovery, None)
        assert "张杰演唱会" in result
        assert "推荐票档: 未能自动确定" in result

    def test_with_chosen_price(self):
        intent = self._make_intent()
        discovery = {
            "used_keyword": "张杰",
            "search_results": [],
            "summary": {
                "title": "张杰演唱会",
                "venue": "体育馆",
                "state": "selling",
                "reservation_mode": False,
                "dates": [],
                "price_options": [],
            },
        }
        chosen = {"index": 1, "text": "580元"}
        result = _format_summary(intent, discovery, chosen)
        assert "580元" in result
        assert "推荐票档" in result

    def test_no_price_options_shows_unrecognized(self):
        intent = self._make_intent()
        discovery = {
            "used_keyword": "张杰",
            "search_results": [],
            "summary": {
                "title": "张杰演唱会",
                "venue": None,
                "state": "sold_out",
                "reservation_mode": True,
                "dates": None,
                "price_options": [],
            },
        }
        result = _format_summary(intent, discovery, None)
        assert "未识别" in result

    def test_with_search_candidates(self):
        intent = self._make_intent()
        discovery = {
            "used_keyword": "张杰",
            "search_results": [
                {"score": 90, "title": "张杰演唱会", "city": "北京", "venue": "鸟巢", "time": "04.06"},
                {"score": 80, "title": "张杰巡演", "city": "上海", "venue": "梅奔", "time": "04.07"},
            ],
            "summary": {
                "title": "张杰演唱会",
                "venue": "体育馆",
                "state": "selling",
                "reservation_mode": False,
                "dates": [],
                "price_options": [],
            },
        }
        result = _format_summary(intent, discovery, None)
        assert "搜索候选" in result
        assert "张杰演唱会" in result

    def test_reservation_mode_displayed(self):
        intent = self._make_intent()
        discovery = {
            "used_keyword": "张杰",
            "search_results": [],
            "summary": {
                "title": None,
                "venue": None,
                "state": "presale",
                "reservation_mode": True,
                "dates": [],
                "price_options": [],
            },
        }
        result = _format_summary(intent, discovery, None)
        assert "预约流: 是" in result


# ---------------------------------------------------------------------------
# _prompt_yes_no
# ---------------------------------------------------------------------------

class TestPromptYesNo:

    def test_yes_reply(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        assert _prompt_yes_no("确认?") is True

    def test_yes_full_word(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "yes")
        assert _prompt_yes_no("确认?") is True

    def test_no_reply(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "n")
        assert _prompt_yes_no("确认?") is False

    def test_empty_reply_is_no(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert _prompt_yes_no("确认?") is False

    def test_uppercase_y(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "Y")
        assert _prompt_yes_no("确认?") is True


# ---------------------------------------------------------------------------
# _prompt_choice
# ---------------------------------------------------------------------------

class TestPromptChoice:

    def test_returns_input_string(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "1")
        result = _prompt_choice("选择:", ["[0] A", "[1] B"])
        assert result == "1"

    def test_empty_input_returns_none(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = _prompt_choice("选择:", ["[0] A"])
        assert result is None

    def test_options_printed(self, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda _: "0")
        _prompt_choice("请选择:", ["[0] 选项A", "[1] 选项B"])
        captured = capsys.readouterr()
        assert "选项A" in captured.out
        assert "选项B" in captured.out


# ---------------------------------------------------------------------------
# _resolve_confirmed_date
# ---------------------------------------------------------------------------

class TestResolveConfirmedDate:

    def _mock_intent(self, date=None):
        intent = Mock()
        intent.date = date
        return intent

    def test_intent_date_matches_visible(self):
        intent = self._mock_intent(date="04.06")
        result = _resolve_confirmed_date(intent, {"dates": ["04.06", "04.07"]}, False)
        assert result == "04.06"

    def test_intent_date_no_visible_dates(self):
        intent = self._mock_intent(date="04.06")
        result = _resolve_confirmed_date(intent, {"dates": []}, False)
        assert result == "04.06"

    def test_single_visible_date_returned(self):
        intent = self._mock_intent(date=None)
        result = _resolve_confirmed_date(intent, {"dates": ["04.06"]}, False)
        assert result == "04.06"

    def test_no_dates_returns_none(self):
        intent = self._mock_intent(date=None)
        result = _resolve_confirmed_date(intent, {"dates": []}, False)
        assert result is None

    def test_assume_yes_with_unresolvable_date_raises(self):
        intent = self._mock_intent(date="04.06")
        with pytest.raises(ValueError, match="--yes"):
            _resolve_confirmed_date(intent, {"dates": ["04.07", "04.08"]}, True)

    def test_interactive_choice(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "0")
        intent = self._mock_intent(date=None)
        result = _resolve_confirmed_date(intent, {"dates": ["04.06", "04.07"]}, False)
        assert result == "04.06"

    def test_interactive_cancel(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        intent = self._mock_intent(date=None)
        result = _resolve_confirmed_date(intent, {"dates": ["04.06", "04.07"]}, False)
        assert result is None

    def test_dates_key_missing_returns_none(self):
        intent = self._mock_intent(date=None)
        result = _resolve_confirmed_date(intent, {}, False)
        assert result is None


# ---------------------------------------------------------------------------
# _resolve_confirmed_price
# ---------------------------------------------------------------------------

class TestResolveConfirmedPrice:

    def _mock_intent(self):
        return Mock()

    def test_chosen_price_returned_directly(self):
        chosen = {"index": 0, "text": "380元"}
        result = _resolve_confirmed_price(self._mock_intent(), {}, chosen, False)
        assert result == chosen

    def test_single_available_option_auto_selected(self):
        intent = self._mock_intent()
        summary = {"price_options": [{"index": 0, "text": "380元"}]}
        result = _resolve_confirmed_price(intent, summary, None, False)
        assert result == {"index": 0, "text": "380元"}

    def test_no_available_options_returns_none(self):
        intent = self._mock_intent()
        summary = {"price_options": []}
        result = _resolve_confirmed_price(intent, summary, None, False)
        assert result is None

    def test_unavailable_tag_filtered_out(self):
        intent = self._mock_intent()
        summary = {"price_options": [{"index": 0, "text": "380元", "tag": "售罄"}]}
        result = _resolve_confirmed_price(intent, summary, None, False)
        assert result is None

    def test_assume_yes_raises_when_ambiguous(self):
        intent = self._mock_intent()
        summary = {
            "price_options": [
                {"index": 0, "text": "380元"},
                {"index": 1, "text": "580元"},
            ]
        }
        with pytest.raises(ValueError, match="--yes"):
            _resolve_confirmed_price(intent, summary, None, True)

    def test_interactive_choice(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "0")
        intent = self._mock_intent()
        options = [{"index": 0, "text": "380元"}, {"index": 1, "text": "580元"}]
        summary = {"price_options": options}
        result = _resolve_confirmed_price(intent, summary, None, False)
        assert result is not None
        assert result["index"] == 0

    def test_interactive_cancel(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        intent = self._mock_intent()
        summary = {
            "price_options": [
                {"index": 0, "text": "380元"},
                {"index": 1, "text": "580元"},
            ]
        }
        result = _resolve_confirmed_price(intent, summary, None, False)
        assert result is None

    def test_price_options_none_returns_none(self):
        intent = self._mock_intent()
        summary = {"price_options": None}
        result = _resolve_confirmed_price(intent, summary, None, False)
        assert result is None

    def test_invalid_index_raises(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "99")
        intent = self._mock_intent()
        # Need 2+ options so the interactive prompt is shown
        summary = {"price_options": [
            {"index": 0, "text": "380元"},
            {"index": 1, "text": "580元"},
        ]}
        with pytest.raises(ValueError, match="price_index"):
            _resolve_confirmed_price(intent, summary, None, False)


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------

class TestParseArgs:

    def test_default_mode_is_summary(self):
        args = parse_args(["帮我抢票"])
        assert args.mode == "summary"

    def test_prompt_is_captured(self):
        args = parse_args(["帮我抢张杰演唱会门票"])
        assert args.prompt == "帮我抢张杰演唱会门票"

    def test_mode_probe(self):
        args = parse_args(["帮我抢票", "--mode", "probe"])
        assert args.mode == "probe"

    def test_mode_apply(self):
        args = parse_args(["帮我抢票", "--mode", "apply"])
        assert args.mode == "apply"

    def test_mode_confirm(self):
        args = parse_args(["帮我抢票", "--mode", "confirm"])
        assert args.mode == "confirm"

    def test_yes_flag(self):
        args = parse_args(["帮我抢票", "-y"])
        assert args.yes is True

    def test_yes_long_flag(self):
        args = parse_args(["帮我抢票", "--yes"])
        assert args.yes is True

    def test_yes_default_false(self):
        args = parse_args(["帮我抢票"])
        assert args.yes is False


# ---------------------------------------------------------------------------
# build_updated_config — additional modes
# ---------------------------------------------------------------------------

class TestBuildUpdatedConfigModes:

    _BASE = {
        "server_url": "http://127.0.0.1:4723",
        "device_name": "Android",
        "udid": "ABC",
        "platform_version": "16",
        "app_package": "cn.damai",
        "app_activity": ".launcher.splash.SplashMainActivity",
        "item_url": None,
        "item_id": None,
        "keyword": "旧词",
        "users": ["张三"],
        "city": "北京",
        "date": "04.05",
        "price": "380元",
        "price_index": 0,
        "if_commit_order": True,
        "probe_only": False,
        "auto_navigate": False,
    }
    _DISCOVERY = {
        "used_keyword": "张杰 演唱会",
        "search_results": [],
        "summary": {
            "title": "张杰演唱会",
            "venue": "北京市 · 国家体育场",
        },
    }
    _PRICE = {"index": 1, "text": "580元"}

    def test_apply_mode_flags(self):
        intent = parse_prompt("帮我抢张杰演唱会门票")
        result = build_updated_config(self._BASE, intent, self._DISCOVERY, "04.06", self._PRICE, "apply")
        assert result["probe_only"] is True
        assert result["if_commit_order"] is False
        assert result["auto_navigate"] is True

    def test_confirm_mode_flags(self):
        intent = parse_prompt("帮我抢张杰演唱会门票")
        result = build_updated_config(self._BASE, intent, self._DISCOVERY, "04.06", self._PRICE, "confirm")
        assert result["probe_only"] is False
        assert result["if_commit_order"] is False

    def test_city_inferred_from_venue(self):
        intent = parse_prompt("帮我抢张杰演唱会门票")
        result = build_updated_config(self._BASE, intent, self._DISCOVERY, "04.06", self._PRICE, "probe")
        assert result["city"] == "北京"
        assert result["target_venue"] == "国家体育场"

    def test_city_from_intent_takes_precedence(self):
        intent = parse_prompt("帮我抢上海张杰演唱会门票")
        result = build_updated_config(self._BASE, intent, self._DISCOVERY, "04.06", self._PRICE, "probe")
        assert result["city"] == "上海"

    def test_fallback_to_search_candidate(self):
        discovery = {
            "used_keyword": "张杰",
            "search_results": [{"title": "张杰巡演", "city": "广州", "venue": "广州体育馆"}],
            "summary": {"title": None, "venue": None},
        }
        intent = parse_prompt("帮我抢张杰演唱会门票")
        result = build_updated_config(self._BASE, intent, discovery, "04.06", self._PRICE, "probe")
        assert result["city"] == "广州"
        assert result["target_venue"] == "广州体育馆"


# ---------------------------------------------------------------------------
# main() — mocked integration tests
# ---------------------------------------------------------------------------

def _make_fake_config(extra=None):
    """Return a minimal mock Config-like object."""
    base = {
        "server_url": "http://127.0.0.1:4723",
        "device_name": "Android",
        "udid": "",
        "platform_version": "14",
        "app_package": "cn.damai",
        "app_activity": ".SplashMainActivity",
        "item_url": None,
        "item_id": None,
        "keyword": "张杰",
        "users": ["User1"],
        "city": "北京",
        "date": "04.06",
        "price": "380元",
        "price_index": 0,
        "if_commit_order": False,
        "probe_only": True,
        "auto_navigate": False,
        "target_title": None,
        "target_venue": None,
    }
    if extra:
        base.update(extra)
    cfg = Mock()
    cfg.to_dict.return_value = base
    cfg.city = base["city"]
    cfg.date = base["date"]
    cfg.price = base["price"]
    cfg.price_index = base["price_index"]
    return cfg, base


def _make_mock_bot(discovery=None, summary=None):
    """Return a mock DamaiBot with reasonable defaults."""
    if discovery is None:
        discovery = {"used_keyword": "张杰", "search_results": [], "page_probe": None}
    if summary is None:
        summary = {
            "title": "张杰演唱会",
            "venue": "鸟巢",
            "state": "selling",
            "reservation_mode": False,
            "dates": ["04.06"],
            "price_options": [{"index": 0, "text": "380元"}],
        }
    bot = Mock()
    bot.driver = None
    bot.probe_current_page.return_value = None
    bot.discover_target_event.return_value = discovery
    bot.inspect_current_target_event.return_value = summary
    return bot


class TestMain:

    def _patch_main(self, monkeypatch, fake_config, base_dict, mock_bot, chosen_price=None):
        import mobile.prompt_runner as pr
        monkeypatch.setattr(pr, "load_config_dict", Mock(return_value=base_dict))
        monkeypatch.setattr(pr, "Config", Mock(
            load_config=Mock(return_value=fake_config),
            return_value=fake_config,
        ))
        monkeypatch.setattr(pr, "DamaiBot", Mock(return_value=mock_bot))
        monkeypatch.setattr(pr, "choose_price_option", Mock(return_value=chosen_price))

    def test_summary_mode_returns_0(self, monkeypatch):
        fake_config, base_dict = _make_fake_config()
        mock_bot = _make_mock_bot()
        self._patch_main(monkeypatch, fake_config, base_dict, mock_bot)

        import mobile.prompt_runner as pr
        result = pr.main(["帮我抢张杰演唱会门票", "--mode", "summary"])
        assert result == 0

    def test_discovery_failure_raises_runtime_error(self, monkeypatch):
        fake_config, base_dict = _make_fake_config()
        mock_bot = _make_mock_bot()
        mock_bot.discover_target_event.return_value = None  # simulate failure
        self._patch_main(monkeypatch, fake_config, base_dict, mock_bot)

        import mobile.prompt_runner as pr
        with pytest.raises(RuntimeError, match="提示词"):
            pr.main(["帮我抢张杰演唱会门票", "--mode", "summary"])

    def test_bot_driver_quit_called_on_exit(self, monkeypatch):
        fake_config, base_dict = _make_fake_config()
        mock_bot = _make_mock_bot()
        mock_driver = Mock()
        mock_bot.driver = mock_driver
        self._patch_main(monkeypatch, fake_config, base_dict, mock_bot)

        import mobile.prompt_runner as pr
        pr.main(["帮我抢张杰演唱会门票", "--mode", "summary"])
        mock_driver.quit.assert_called_once()

    def test_apply_mode_no_date_returns_1(self, monkeypatch):
        """When date cannot be confirmed, main returns 1."""
        fake_config, base_dict = _make_fake_config()
        summary = {
            "title": "张杰演唱会", "venue": "鸟巢", "state": "selling",
            "reservation_mode": False, "dates": ["04.06", "04.07"],
            "price_options": [{"index": 0, "text": "380元"}],
        }
        mock_bot = _make_mock_bot(summary=summary)
        self._patch_main(monkeypatch, fake_config, base_dict, mock_bot)
        # interactive input: empty → cancel date selection
        monkeypatch.setattr("builtins.input", lambda _: "")

        import mobile.prompt_runner as pr
        result = pr.main(["帮我抢张杰演唱会门票", "--mode", "apply"])
        assert result == 1

    def test_apply_mode_no_price_returns_1(self, monkeypatch):
        """When price cannot be confirmed, main returns 1."""
        fake_config, base_dict = _make_fake_config()
        summary = {
            "title": "张杰演唱会", "venue": "鸟巢", "state": "selling",
            "reservation_mode": False, "dates": ["04.06"],
            "price_options": [],  # no options → returns None
        }
        mock_bot = _make_mock_bot(summary=summary)
        self._patch_main(monkeypatch, fake_config, base_dict, mock_bot)

        import mobile.prompt_runner as pr
        result = pr.main(["帮我抢张杰演唱会门票", "--mode", "apply"])
        assert result == 1

    def test_apply_mode_user_cancels_write(self, monkeypatch):
        """User declines to write config → returns 1."""
        fake_config, base_dict = _make_fake_config()
        summary = {
            "title": "张杰演唱会", "venue": "鸟巢", "state": "selling",
            "reservation_mode": False, "dates": ["04.06"],
            "price_options": [{"index": 0, "text": "380元"}],
        }
        mock_bot = _make_mock_bot(summary=summary)
        self._patch_main(
            monkeypatch, fake_config, base_dict, mock_bot,
            chosen_price={"index": 0, "text": "380元"},
        )
        monkeypatch.setattr("builtins.input", lambda _: "n")

        import mobile.prompt_runner as pr
        result = pr.main(["帮我抢张杰演唱会门票", "--mode", "apply"])
        assert result == 1

    def test_apply_mode_writes_config_and_returns_0(self, monkeypatch):
        """apply mode writes config but does not execute; returns 0."""
        fake_config, base_dict = _make_fake_config()
        summary = {
            "title": "张杰演唱会", "venue": "鸟巢", "state": "selling",
            "reservation_mode": False, "dates": ["04.06"],
            "price_options": [{"index": 0, "text": "380元"}],
        }
        mock_bot = _make_mock_bot(summary=summary)
        self._patch_main(
            monkeypatch, fake_config, base_dict, mock_bot,
            chosen_price={"index": 0, "text": "380元"},
        )
        monkeypatch.setattr("builtins.input", lambda _: "y")

        import mobile.prompt_runner as pr
        mock_save = Mock()
        monkeypatch.setattr(pr, "save_config_dict", mock_save)
        result = pr.main(["帮我抢张杰演唱会门票", "--mode", "apply"])
        assert result == 0
        mock_save.assert_called_once()
