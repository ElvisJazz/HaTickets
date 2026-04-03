"""Unit tests for EventNavigator."""

from unittest.mock import MagicMock
from mobile.event_navigator import EventNavigator


class TestKeywordTokens:
    def _nav(self, keyword):
        config = MagicMock()
        config.keyword = keyword
        return EventNavigator(device=MagicMock(), config=config, probe=MagicMock())

    def test_splits_by_space(self):
        tokens = self._nav("张杰 演唱会")._keyword_tokens()
        assert tokens == ["张杰", "演唱会"]

    def test_splits_by_comma(self):
        tokens = self._nav("张杰,演唱会")._keyword_tokens()
        assert tokens == ["张杰", "演唱会"]

    def test_filters_short_tokens(self):
        tokens = self._nav("张杰 A 演唱会")._keyword_tokens()
        assert "A" not in tokens
        assert "张杰" in tokens

    def test_empty_keyword(self):
        assert self._nav("")._keyword_tokens() == []

    def test_none_keyword(self):
        assert self._nav(None)._keyword_tokens() == []

    def test_deduplicates(self):
        tokens = self._nav("张杰 张杰 演唱会")._keyword_tokens()
        assert tokens.count("张杰") == 1


class TestTitleMatchesTarget:
    def test_matches_item_detail_name(self):
        bot = MagicMock()
        bot.item_detail = MagicMock()
        bot.item_detail.item_name = "张杰未·LIVE巡回演唱会"
        bot.item_detail.item_name_display = "张杰未·LIVE"
        bot._keyword_tokens.return_value = []
        config = MagicMock()
        config.target_title = None
        config.keyword = None
        nav = EventNavigator(device=MagicMock(), config=config, probe=MagicMock())
        nav.set_bot(bot)
        assert nav._title_matches_target("张杰未·LIVE巡回演唱会") is True

    def test_no_match_returns_false(self):
        bot = MagicMock()
        bot.item_detail = None
        bot._keyword_tokens.return_value = []
        config = MagicMock()
        config.target_title = "张杰"
        config.keyword = None
        nav = EventNavigator(device=MagicMock(), config=config, probe=MagicMock())
        nav.set_bot(bot)
        assert nav._title_matches_target("周杰伦演唱会") is False

    def test_empty_title_returns_false(self):
        bot = MagicMock()
        bot.item_detail = None
        bot._keyword_tokens.return_value = []
        config = MagicMock()
        config.target_title = "张杰"
        config.keyword = None
        nav = EventNavigator(device=MagicMock(), config=config, probe=MagicMock())
        nav.set_bot(bot)
        assert nav._title_matches_target("") is False

    def test_keyword_tokens_match(self):
        bot = MagicMock()
        bot.item_detail = None
        bot._keyword_tokens.return_value = ["张杰", "演唱会"]
        config = MagicMock()
        config.target_title = None
        config.keyword = "张杰 演唱会"
        nav = EventNavigator(device=MagicMock(), config=config, probe=MagicMock())
        nav.set_bot(bot)
        assert nav._title_matches_target("张杰2026巡回演唱会北京站") is True


class TestCurrentPageMatchesTarget:
    def test_wrong_state_returns_false(self):
        bot = MagicMock()
        config = MagicMock()
        nav = EventNavigator(device=MagicMock(), config=config, probe=MagicMock())
        nav.set_bot(bot)
        assert nav._current_page_matches_target({"state": "homepage"}) is False

    def test_no_target_info_returns_true(self):
        bot = MagicMock()
        bot.item_detail = None
        config = MagicMock()
        config.target_title = None
        config.keyword = None
        nav = EventNavigator(device=MagicMock(), config=config, probe=MagicMock())
        nav.set_bot(bot)
        assert nav._current_page_matches_target({"state": "detail_page"}) is True

    def test_delegates_to_title_match(self):
        bot = MagicMock()
        bot.item_detail = MagicMock()
        bot._get_detail_title_text.return_value = "张杰演唱会"
        bot._title_matches_target.return_value = True
        config = MagicMock()
        config.target_title = "张杰"
        config.keyword = None
        nav = EventNavigator(device=MagicMock(), config=config, probe=MagicMock())
        nav.set_bot(bot)
        assert nav._current_page_matches_target({"state": "sku_page"}) is True


class TestNavigateToTarget:
    def test_already_on_detail_page_returns_true(self):
        probe = MagicMock()
        probe.probe_current_page.return_value = {"state": "detail_page"}
        nav = EventNavigator(
            device=MagicMock(), config=MagicMock(auto_navigate=True), probe=probe
        )
        assert nav.navigate_to_target_event() is True

    def test_auto_navigate_disabled_returns_false(self):
        probe = MagicMock()
        probe.probe_current_page.return_value = {"state": "homepage"}
        nav = EventNavigator(
            device=MagicMock(), config=MagicMock(auto_navigate=False), probe=probe
        )
        assert nav.navigate_to_target_event() is False

    def test_delegates_to_bot(self):
        probe = MagicMock()
        probe.probe_current_page.return_value = {"state": "homepage"}
        bot = MagicMock()
        bot._navigate_to_target_impl.return_value = True
        nav = EventNavigator(
            device=MagicMock(), config=MagicMock(auto_navigate=True), probe=probe
        )
        nav.set_bot(bot)
        result = nav.navigate_to_target_event()
        bot._navigate_to_target_impl.assert_called_once()
        assert result is True

    def test_delegates_to_bot_returns_false_on_failure(self):
        probe = MagicMock()
        probe.probe_current_page.return_value = {"state": "homepage"}
        bot = MagicMock()
        bot._navigate_to_target_impl.return_value = False
        nav = EventNavigator(
            device=MagicMock(), config=MagicMock(auto_navigate=True), probe=probe
        )
        nav.set_bot(bot)
        result = nav.navigate_to_target_event()
        assert result is False

    def test_delegates_to_bot_catches_exception(self):
        probe = MagicMock()
        probe.probe_current_page.return_value = {"state": "homepage"}
        bot = MagicMock()
        bot._navigate_to_target_impl.side_effect = RuntimeError("device disconnected")
        nav = EventNavigator(
            device=MagicMock(), config=MagicMock(auto_navigate=True), probe=probe
        )
        nav.set_bot(bot)
        result = nav.navigate_to_target_event()
        assert result is False

    def test_no_bot_returns_false(self):
        probe = MagicMock()
        probe.probe_current_page.return_value = {"state": "homepage"}
        nav = EventNavigator(
            device=MagicMock(), config=MagicMock(auto_navigate=True), probe=probe
        )
        assert nav.navigate_to_target_event() is False

    def test_passes_initial_probe_to_bot(self):
        probe = MagicMock()
        bot = MagicMock()
        bot._navigate_to_target_impl.return_value = True
        nav = EventNavigator(
            device=MagicMock(), config=MagicMock(auto_navigate=True), probe=probe
        )
        nav.set_bot(bot)
        initial = {"state": "search_page"}
        nav.navigate_to_target_event(initial_probe=initial)
        bot._navigate_to_target_impl.assert_called_once_with(initial_probe=initial)
