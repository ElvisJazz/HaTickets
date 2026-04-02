"""Unit tests for EventNavigator."""
from unittest.mock import MagicMock
import pytest
from mobile.event_navigator import EventNavigator

class TestNavigateToTarget:
    def test_already_on_detail_page_returns_true(self):
        d = MagicMock()
        config = MagicMock()
        config.auto_navigate = True
        probe = MagicMock()
        probe.probe_current_page.return_value = {"state": "detail_page"}
        nav = EventNavigator(device=d, config=config, probe=probe)
        assert nav.navigate_to_target_event() is True

    def test_auto_navigate_disabled_returns_false(self):
        d = MagicMock()
        config = MagicMock()
        config.auto_navigate = False
        probe = MagicMock()
        probe.probe_current_page.return_value = {"state": "homepage"}
        nav = EventNavigator(device=d, config=config, probe=probe)
        assert nav.navigate_to_target_event() is False

    def test_not_on_detail_returns_false_stub(self):
        d = MagicMock()
        config = MagicMock()
        config.auto_navigate = True
        probe = MagicMock()
        probe.probe_current_page.return_value = {"state": "homepage"}
        nav = EventNavigator(device=d, config=config, probe=probe)
        assert nav.navigate_to_target_event() is False
