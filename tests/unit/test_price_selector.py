"""Unit tests for PriceSelector."""

from unittest.mock import MagicMock
from mobile.price_selector import PriceSelector


class TestSelectByIndex:
    def test_clicks_correct_coordinates_via_bot(self):
        bot = MagicMock()
        bot._get_price_option_coordinates_by_config_index.return_value = (100, 200)
        d = MagicMock()
        config = MagicMock()
        config.price_index = 2
        selector = PriceSelector(device=d, config=config, probe=MagicMock())
        selector.set_bot(bot)
        result = selector.select_by_index()
        assert result is True
        d.click.assert_called_once_with(100, 200)

    def test_returns_false_when_bot_returns_none(self):
        bot = MagicMock()
        bot._get_price_option_coordinates_by_config_index.return_value = None
        selector = PriceSelector(
            device=MagicMock(), config=MagicMock(price_index=99), probe=MagicMock()
        )
        selector.set_bot(bot)
        assert selector.select_by_index() is False

    def test_returns_false_when_no_bot(self):
        selector = PriceSelector(
            device=MagicMock(), config=MagicMock(price_index=0), probe=MagicMock()
        )
        assert selector.select_by_index() is False

    def test_click_coordinates_swallows_exception(self):
        bot = MagicMock()
        bot._get_price_option_coordinates_by_config_index.return_value = (10, 20)
        d = MagicMock()
        d.click.side_effect = Exception("device error")
        selector = PriceSelector(
            device=d, config=MagicMock(price_index=0), probe=MagicMock()
        )
        selector.set_bot(bot)
        assert selector.select_by_index() is True


class TestGetPriceCoordsByIndex:
    def test_exception_returns_none(self):
        bot = MagicMock()
        bot._get_price_option_coordinates_by_config_index.side_effect = RuntimeError(
            "fail"
        )
        selector = PriceSelector(
            device=MagicMock(), config=MagicMock(), probe=MagicMock()
        )
        selector.set_bot(bot)
        assert selector.get_price_coords_by_index() is None

    def test_success_returns_coords(self):
        bot = MagicMock()
        bot._get_price_option_coordinates_by_config_index.return_value = (50, 60)
        selector = PriceSelector(
            device=MagicMock(), config=MagicMock(), probe=MagicMock()
        )
        selector.set_bot(bot)
        assert selector.get_price_coords_by_index() == (50, 60)


class TestGetBuyButtonCoordsExc:
    def test_exception_returns_none(self):
        bot = MagicMock()
        bot._get_buy_button_coordinates.side_effect = RuntimeError("fail")
        selector = PriceSelector(
            device=MagicMock(), config=MagicMock(), probe=MagicMock()
        )
        selector.set_bot(bot)
        assert selector.get_buy_button_coords() is None


class TestExtractPriceDigits:
    def _selector(self):
        return PriceSelector(device=MagicMock(), config=MagicMock(), probe=MagicMock())

    def test_extracts_digits_from_price_text(self):
        assert self._selector()._extract_price_digits("¥580元") == 580

    def test_returns_none_for_no_digits(self):
        assert self._selector()._extract_price_digits("免费") is None

    def test_handles_non_string(self):
        assert self._selector()._extract_price_digits(None) is None

    def test_extracts_four_digit_price(self):
        assert self._selector()._extract_price_digits("1680元") == 1680


class TestIsPriceOptionAvailable:
    def _selector(self):
        return PriceSelector(device=MagicMock(), config=MagicMock(), probe=MagicMock())

    def test_available_when_no_tag(self):
        assert self._selector()._is_price_option_available({"tag": ""}) is True

    def test_unavailable_when_sold_out(self):
        assert self._selector()._is_price_option_available({"tag": "售罄"}) is False

    def test_unavailable_when_no_ticket(self):
        assert self._selector()._is_price_option_available({"tag": "无票"}) is False

    def test_available_when_tag_is_none(self):
        assert self._selector()._is_price_option_available({"tag": None}) is True


class TestNormalizeOcrPriceText:
    def _selector(self):
        return PriceSelector(device=MagicMock(), config=MagicMock(), probe=MagicMock())

    def test_extracts_three_digit_price(self):
        assert self._selector()._normalize_ocr_price_text("票价580元起") == "580元"

    def test_extracts_four_digit_price(self):
        assert self._selector()._normalize_ocr_price_text("1280RMB") == "1280元"

    def test_returns_empty_for_no_digits(self):
        assert self._selector()._normalize_ocr_price_text("免费入场") == ""

    def test_handles_non_string(self):
        assert self._selector()._normalize_ocr_price_text(None) == ""

    def test_scattered_digits_three(self):
        assert self._selector()._normalize_ocr_price_text("价 3 8 0 元") == "380元"


class TestPriceTextMatchesTarget:
    def test_exact_match(self):
        config = MagicMock()
        config.price = "580元"
        selector = PriceSelector(device=MagicMock(), config=config, probe=MagicMock())
        assert selector._price_text_matches_target("580元") is True

    def test_digit_match(self):
        config = MagicMock()
        config.price = "¥580"
        selector = PriceSelector(device=MagicMock(), config=config, probe=MagicMock())
        assert selector._price_text_matches_target("580元") is True

    def test_no_match(self):
        config = MagicMock()
        config.price = "380元"
        selector = PriceSelector(device=MagicMock(), config=config, probe=MagicMock())
        assert selector._price_text_matches_target("580元") is False


class TestGetBuyButtonCoords:
    def test_delegates_to_bot(self):
        bot = MagicMock()
        bot._get_buy_button_coordinates.return_value = (300, 400)
        selector = PriceSelector(
            device=MagicMock(), config=MagicMock(), probe=MagicMock()
        )
        selector.set_bot(bot)
        assert selector.get_buy_button_coords() == (300, 400)

    def test_returns_none_when_no_bot(self):
        selector = PriceSelector(
            device=MagicMock(), config=MagicMock(), probe=MagicMock()
        )
        assert selector.get_buy_button_coords() is None


class TestGetPriceCoordsFromXml:
    def _make_xml(self, container_id, num_cards):
        """Build minimal XML with clickable FrameLayout cards."""
        import xml.etree.ElementTree as ET

        root = ET.Element("hierarchy")
        container = ET.SubElement(
            root,
            "node",
            attrib={
                "resource-id": container_id,
                "class": "android.widget.LinearLayout",
            },
        )
        for i in range(num_cards):
            x1, y1, x2, y2 = 100 * i, 200, 100 * i + 80, 280
            ET.SubElement(
                container,
                "node",
                attrib={
                    "class": "android.widget.FrameLayout",
                    "clickable": "true",
                    "bounds": f"[{x1},{y1}][{x2},{y2}]",
                },
            )
        return root

    def test_finds_card_in_primary_container(self):
        bot = MagicMock()
        bot._using_u2.return_value = True
        bot._parse_bounds.return_value = (0, 200, 80, 280)
        config = MagicMock()
        config.price_index = 0
        selector = PriceSelector(device=MagicMock(), config=config, probe=MagicMock())
        selector.set_bot(bot)
        xml = self._make_xml("cn.damai:id/project_detail_perform_price_flowlayout", 3)
        result = selector._get_price_coords_from_xml(xml)
        assert result == (40, 240)

    def test_falls_back_to_layout_price(self):
        bot = MagicMock()
        bot._using_u2.return_value = True
        bot._parse_bounds.return_value = (100, 200, 180, 280)
        config = MagicMock()
        config.price_index = 1
        selector = PriceSelector(device=MagicMock(), config=config, probe=MagicMock())
        selector.set_bot(bot)
        xml = self._make_xml("cn.damai:id/layout_price", 5)
        result = selector._get_price_coords_from_xml(xml)
        assert result == (140, 240)

    def test_returns_none_when_index_out_of_range(self):
        bot = MagicMock()
        bot._using_u2.return_value = True
        config = MagicMock()
        config.price_index = 10
        selector = PriceSelector(device=MagicMock(), config=config, probe=MagicMock())
        selector.set_bot(bot)
        xml = self._make_xml("cn.damai:id/project_detail_perform_price_flowlayout", 3)
        result = selector._get_price_coords_from_xml(xml)
        assert result is None

    def test_returns_none_when_no_xml(self):
        bot = MagicMock()
        bot._using_u2.return_value = True
        bot._dump_hierarchy_xml.return_value = None
        config = MagicMock()
        config.price_index = 0
        selector = PriceSelector(device=MagicMock(), config=config, probe=MagicMock())
        selector.set_bot(bot)
        result = selector._get_price_coords_from_xml(None)
        assert result is None

    def test_retry_on_cold_path(self):
        """When xml_root is provided but index out of range, retry with fresh dump."""

        bot = MagicMock()
        bot._using_u2.return_value = True
        bot._parse_bounds.return_value = (0, 200, 80, 280)
        # First XML: only 2 cards (index 2 out of range)
        xml_small = self._make_xml(
            "cn.damai:id/project_detail_perform_price_flowlayout", 2
        )
        # Fresh dump returns 5 cards
        xml_full = self._make_xml(
            "cn.damai:id/project_detail_perform_price_flowlayout", 5
        )
        bot._dump_hierarchy_xml.return_value = xml_full
        config = MagicMock()
        config.price_index = 2
        selector = PriceSelector(device=MagicMock(), config=config, probe=MagicMock())
        selector.set_bot(bot)
        result = selector._get_price_option_coordinates_by_config_index(
            xml_root=xml_small
        )
        assert result is not None  # retry succeeded
