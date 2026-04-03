# -*- coding: UTF-8 -*-
"""Unit tests for shared/xpath_utils.py."""


from shared.xpath_utils import escape_xpath_string


class TestEscapeXpathString:
    def test_simple_string(self):
        assert escape_xpath_string("hello") == "'hello'"

    def test_empty_string(self):
        assert escape_xpath_string("") == "''"

    def test_string_with_single_quote(self):
        result = escape_xpath_string("O'Brien")
        assert result == '"O\'Brien"'

    def test_string_with_double_quote(self):
        result = escape_xpath_string('say "hi"')
        assert result == "'say \"hi\"'"

    def test_string_with_both_quotes(self):
        result = escape_xpath_string('it\'s a "test"')
        assert "concat(" in result

    def test_concat_result_contains_original_parts(self):
        value = 'it\'s a "test"'
        result = escape_xpath_string(value)
        # Should contain both text parts split around the single quote
        assert "it" in result
        assert "s a" in result

    def test_chinese_name_no_quotes(self):
        result = escape_xpath_string("张三")
        assert result == "'张三'"

    def test_no_quotes_uses_single_quote_wrapper(self):
        result = escape_xpath_string("normal text")
        assert result.startswith("'")
        assert result.endswith("'")

    def test_only_double_quotes_uses_single_quote_wrapper(self):
        result = escape_xpath_string('has "double" quotes')
        assert result.startswith("'")
        assert result.endswith("'")

    def test_only_single_quotes_uses_double_quote_wrapper(self):
        result = escape_xpath_string("has 'single' quotes")
        assert result.startswith('"')
        assert result.endswith('"')

    def test_both_quotes_uses_concat(self):
        result = escape_xpath_string('O\'Brien said "hello"')
        assert result.startswith("concat(")

    def test_xpath_injection_safety_single_quote(self):
        """Verify the escaped value can be safely embedded in an XPath contains() call."""
        user = "O'Brien"
        escaped = escape_xpath_string(user)
        xpath = f"//*[contains(text(), {escaped})]"
        # The XPath should not contain an unescaped bare single quote that breaks parsing
        # The entire literal is now wrapped in double quotes
        assert escaped == '"O\'Brien"'
        assert '"O\'Brien"' in xpath
