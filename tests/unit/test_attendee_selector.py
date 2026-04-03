"""Unit tests for AttendeeSelector."""

from unittest.mock import MagicMock, patch
from mobile.attendee_selector import AttendeeSelector


class TestAttendeeRequiredCount:
    def test_infers_from_hint_text(self):
        bot = MagicMock()
        bot._safe_element_text.return_value = "仅需选择 3 位观演人"
        config = MagicMock()
        config.users = ["A", "B"]
        selector = AttendeeSelector(device=MagicMock(), config=config)
        selector.set_bot(bot)
        assert selector._attendee_required_count_on_confirm_page() == 3

    def test_falls_back_to_user_count(self):
        bot = MagicMock()
        bot._safe_element_text.return_value = None
        config = MagicMock()
        config.users = ["A", "B", "C"]
        selector = AttendeeSelector(device=MagicMock(), config=config)
        selector.set_bot(bot)
        assert selector._attendee_required_count_on_confirm_page() == 3

    def test_clamps_to_one_minimum(self):
        bot = MagicMock()
        bot._safe_element_text.return_value = None
        config = MagicMock()
        config.users = []
        selector = AttendeeSelector(device=MagicMock(), config=config)
        selector.set_bot(bot)
        assert selector._attendee_required_count_on_confirm_page() == 1


class TestAttendeeCheckboxElements:
    def test_returns_elements_from_bot(self):
        bot = MagicMock()
        bot._find_all.return_value = ["cb1", "cb2"]
        selector = AttendeeSelector(device=MagicMock(), config=MagicMock())
        selector.set_bot(bot)
        assert selector._attendee_checkbox_elements() == ["cb1", "cb2"]

    def test_returns_empty_on_exception(self):
        bot = MagicMock()
        bot._find_all.side_effect = RuntimeError("no device")
        selector = AttendeeSelector(device=MagicMock(), config=MagicMock())
        selector.set_bot(bot)
        assert selector._attendee_checkbox_elements() == []


class TestIsCheckboxSelected:
    def test_delegates_to_ui_primitives(self):
        checkbox = MagicMock()
        with patch("mobile.ui_primitives.UIPrimitives._is_checked", return_value=True):
            assert AttendeeSelector._is_checkbox_selected(checkbox) is True


class TestFindCheckboxes:
    def test_returns_elements_when_exist(self):
        d = MagicMock()
        elements = MagicMock()
        elements.exists = True
        elements.__iter__ = MagicMock(return_value=iter(["cb1", "cb2"]))
        d.return_value = elements
        d.__call__ = MagicMock(return_value=elements)
        selector = AttendeeSelector(device=d, config=MagicMock())
        result = selector._find_checkboxes()
        assert result == ["cb1", "cb2"]

    def test_returns_empty_on_exception(self):
        d = MagicMock()
        d.side_effect = Exception("error")
        selector = AttendeeSelector(device=d, config=MagicMock())
        assert selector._find_checkboxes() == []


class TestClickCheckbox:
    def test_clicks_element(self):
        element = MagicMock()
        selector = AttendeeSelector(device=MagicMock(), config=MagicMock())
        selector._click_checkbox(element)
        element.click.assert_called_once()

    def test_swallows_exception(self):
        element = MagicMock()
        element.click.side_effect = Exception("click failed")
        selector = AttendeeSelector(device=MagicMock(), config=MagicMock())
        selector._click_checkbox(element)  # should not raise


class TestClickAttendeeFast:
    def test_first_click_succeeds(self):
        checkbox = MagicMock()
        bot = MagicMock()
        selector = AttendeeSelector(device=MagicMock(), config=MagicMock())
        selector.set_bot(bot)
        assert selector._click_attendee_checkbox_fast(checkbox) is True
        checkbox.click.assert_called_once()

    def test_falls_back_to_bot_click(self):
        checkbox = MagicMock()
        checkbox.click.side_effect = Exception("fail")
        bot = MagicMock()
        selector = AttendeeSelector(device=MagicMock(), config=MagicMock())
        selector.set_bot(bot)
        assert selector._click_attendee_checkbox_fast(checkbox) is True
        bot._click_element_center.assert_called_once()

    def test_all_fail_returns_false(self):
        checkbox = MagicMock()
        checkbox.click.side_effect = Exception("fail")
        bot = MagicMock()
        bot._click_element_center.side_effect = Exception("fail")
        selector = AttendeeSelector(device=MagicMock(), config=MagicMock())
        selector.set_bot(bot)
        assert selector._click_attendee_checkbox_fast(checkbox) is False


class TestEnsureSelected:
    def test_selects_correct_number(self):
        d = MagicMock()
        config = MagicMock()
        config.users = ["user1", "user2"]
        selector = AttendeeSelector(device=d, config=config)
        cb1, cb2, cb3 = MagicMock(), MagicMock(), MagicMock()
        selector._find_checkboxes = MagicMock(return_value=[cb1, cb2, cb3])
        selector._click_checkbox = MagicMock()
        selector.ensure_selected()
        assert selector._click_checkbox.call_count == 2

    def test_no_checkboxes_found(self):
        d = MagicMock()
        config = MagicMock()
        config.users = ["user1"]
        selector = AttendeeSelector(device=d, config=config)
        selector._find_checkboxes = MagicMock(return_value=[])
        selector.ensure_selected()  # should not crash

    def test_single_user(self):
        d = MagicMock()
        config = MagicMock()
        config.users = ["user1"]
        selector = AttendeeSelector(device=d, config=config)
        cb1 = MagicMock()
        selector._find_checkboxes = MagicMock(return_value=[cb1])
        selector._click_checkbox = MagicMock()
        selector.ensure_selected()
        assert selector._click_checkbox.call_count == 1

    def test_empty_users_defaults_to_one(self):
        d = MagicMock()
        config = MagicMock()
        config.users = []
        selector = AttendeeSelector(device=d, config=config)
        cb1 = MagicMock()
        selector._find_checkboxes = MagicMock(return_value=[cb1])
        selector._click_checkbox = MagicMock()
        selector.ensure_selected()
        assert selector._click_checkbox.call_count == 1
