"""Unit tests for web/check_environment.py"""

import json
import subprocess
import sys
from collections import namedtuple
from unittest.mock import MagicMock, patch

import pytest

from check_environment import (
    _get_version_from_output,
    _run_command_get_version,
    check_chrome,
    check_chromedriver,
    check_config_file,
    check_dependencies,
    check_python_version,
    check_version_match,
    get_chromedriver_path,
    main,
)


# ---------------------------------------------------------------------------
# _get_version_from_output
# ---------------------------------------------------------------------------

class TestGetVersionFromOutput:
    def test_extracts_major_version_from_chrome_string(self):
        assert _get_version_from_output("Google Chrome 131.0.6778.86") == "131"

    def test_extracts_major_version_from_chromedriver_string(self):
        assert _get_version_from_output("ChromeDriver 131.0.6778.87") == "131"

    def test_returns_none_for_string_without_version(self):
        assert _get_version_from_output("no version here") is None

    def test_returns_none_for_empty_string(self):
        assert _get_version_from_output("") is None


# ---------------------------------------------------------------------------
# _run_command_get_version
# ---------------------------------------------------------------------------

class TestRunCommandGetVersion:
    def test_returns_stdout_on_success(self):
        fake_result = subprocess.CompletedProcess(
            args=["cmd"], returncode=0, stdout="  Google Chrome 131.0.6778.86  \n", stderr=""
        )
        with patch("check_environment.subprocess.run", return_value=fake_result):
            assert _run_command_get_version(["cmd"]) == "Google Chrome 131.0.6778.86"

    def test_returns_none_on_nonzero_returncode(self):
        fake_result = subprocess.CompletedProcess(args=["cmd"], returncode=1, stdout="", stderr="err")
        with patch("check_environment.subprocess.run", return_value=fake_result):
            assert _run_command_get_version(["cmd"]) is None

    def test_returns_none_on_exception(self):
        with patch("check_environment.subprocess.run", side_effect=FileNotFoundError):
            assert _run_command_get_version(["nonexistent"]) is None


# ---------------------------------------------------------------------------
# check_python_version
# ---------------------------------------------------------------------------

class TestCheckPythonVersion:
    def test_returns_true_for_python_3_10(self, monkeypatch):
        VersionInfo = namedtuple("version_info", ["major", "minor", "micro", "releaselevel", "serial"])
        monkeypatch.setattr(sys, "version_info", VersionInfo(3, 10, 0, "final", 0))
        assert check_python_version() is True

    def test_returns_false_for_python_2_7(self, monkeypatch):
        VersionInfo = namedtuple("version_info", ["major", "minor", "micro", "releaselevel", "serial"])
        monkeypatch.setattr(sys, "version_info", VersionInfo(2, 7, 18, "final", 0))
        assert check_python_version() is False

    def test_returns_true_for_python_3_7_boundary(self, monkeypatch):
        VersionInfo = namedtuple("version_info", ["major", "minor", "micro", "releaselevel", "serial"])
        monkeypatch.setattr(sys, "version_info", VersionInfo(3, 7, 0, "final", 0))
        assert check_python_version() is True

    def test_returns_false_for_python_3_6(self, monkeypatch):
        VersionInfo = namedtuple("version_info", ["major", "minor", "micro", "releaselevel", "serial"])
        monkeypatch.setattr(sys, "version_info", VersionInfo(3, 6, 9, "final", 0))
        assert check_python_version() is False


# ---------------------------------------------------------------------------
# check_dependencies
# ---------------------------------------------------------------------------

class TestCheckDependencies:
    def test_returns_true_when_all_importable(self):
        with patch("builtins.__import__", side_effect=lambda name, *a, **kw: MagicMock()):
            assert check_dependencies() is True

    def test_returns_false_when_selenium_missing(self):
        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def selective_import(name, *args, **kwargs):
            if name == "selenium":
                raise ImportError("No module named 'selenium'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=selective_import):
            assert check_dependencies() is False


# ---------------------------------------------------------------------------
# check_chrome
# ---------------------------------------------------------------------------

class TestCheckChrome:
    def test_returns_true_when_chrome_found(self):
        with patch("check_environment.os.path.exists", return_value=True), \
             patch("check_environment._run_command_get_version", return_value="Google Chrome 131.0.6778.86"):
            assert check_chrome() is True

    def test_returns_false_when_no_chrome_found(self):
        with patch("check_environment.os.path.exists", return_value=False):
            assert check_chrome() is False


# ---------------------------------------------------------------------------
# check_chromedriver
# ---------------------------------------------------------------------------

class TestCheckChromedriver:
    def test_returns_true_when_driver_found_via_exists(self):
        with patch("check_environment.os.path.exists", return_value=True), \
             patch("check_environment.os.path.islink", return_value=False), \
             patch("check_environment._run_command_get_version", return_value="ChromeDriver 131.0.6778.87"):
            assert check_chromedriver() is True

    def test_returns_true_when_driver_found_via_islink(self):
        with patch("check_environment.os.path.exists", return_value=False), \
             patch("check_environment.os.path.islink", return_value=True), \
             patch("check_environment._run_command_get_version", return_value="ChromeDriver 131.0.6778.87"):
            assert check_chromedriver() is True

    def test_returns_false_when_no_driver_found(self):
        with patch("check_environment.os.path.exists", return_value=False), \
             patch("check_environment.os.path.islink", return_value=False):
            assert check_chromedriver() is False


# ---------------------------------------------------------------------------
# check_version_match
# ---------------------------------------------------------------------------

class TestCheckVersionMatch:
    def test_returns_true_when_versions_match(self):
        def fake_exists(path):
            return True

        with patch("check_environment.os.path.exists", side_effect=fake_exists), \
             patch("check_environment.os.path.islink", return_value=False), \
             patch("check_environment._run_command_get_version", return_value="Google Chrome 131.0.6778.86"):
            assert check_version_match() is True

    def test_returns_false_when_versions_mismatch(self):
        call_count = {"n": 0}

        def fake_run(cmd):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return "Google Chrome 131.0.6778.86"
            return "ChromeDriver 130.0.6723.58"

        with patch("check_environment.os.path.exists", return_value=True), \
             patch("check_environment.os.path.islink", return_value=False), \
             patch("check_environment._run_command_get_version", side_effect=fake_run):
            assert check_version_match() is False

    def test_returns_false_when_chrome_not_found(self):
        with patch("check_environment.os.path.exists", return_value=False), \
             patch("check_environment.os.path.islink", return_value=False):
            assert check_version_match() is False


# ---------------------------------------------------------------------------
# get_chromedriver_path
# ---------------------------------------------------------------------------

class TestGetChromedriverPath:
    def test_returns_matching_driver_path(self):
        def fake_exists(path):
            return True

        with patch("check_environment.os.path.exists", side_effect=fake_exists), \
             patch("check_environment.os.path.islink", return_value=False), \
             patch("check_environment._run_command_get_version", return_value="ChromeDriver 131.0.6778.86"):
            result = get_chromedriver_path()
            assert result == "/opt/homebrew/bin/chromedriver"

    def test_raises_when_chrome_not_found(self):
        with patch("check_environment.os.path.exists", return_value=False):
            with pytest.raises(RuntimeError, match="Chrome"):
                get_chromedriver_path()

    def test_raises_when_chrome_version_undetectable(self):
        def fake_exists(path):
            # Chrome path exists but drivers do not
            return path == "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

        with patch("check_environment.os.path.exists", side_effect=fake_exists), \
             patch("check_environment._run_command_get_version", return_value=None):
            with pytest.raises(RuntimeError, match="Chrome"):
                get_chromedriver_path()


# ---------------------------------------------------------------------------
# check_config_file
# ---------------------------------------------------------------------------

class TestCheckConfigFile:
    def test_returns_true_for_valid_config(self, tmp_path, monkeypatch):
        config = {
            "index_url": "https://www.damai.cn/",
            "login_url": "https://passport.damai.cn/login",
            "target_url": "https://detail.damai.cn/item.htm?id=123",
            "users": ["UserA"],
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        assert check_config_file() is True

    def test_returns_false_when_config_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert check_config_file() is False

    def test_returns_false_when_required_fields_missing(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"index_url": "x"}), encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        assert check_config_file() is False

    def test_returns_false_for_invalid_json(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.json"
        config_path.write_text("not json {{{", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        assert check_config_file() is False


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

class TestMain:
    def test_returns_zero_when_all_checks_pass(self):
        with patch("check_environment.check_python_version", return_value=True), \
             patch("check_environment.check_dependencies", return_value=True), \
             patch("check_environment.check_chrome", return_value=True), \
             patch("check_environment.check_chromedriver", return_value=True), \
             patch("check_environment.check_version_match", return_value=True), \
             patch("check_environment.check_config_file", return_value=True):
            assert main() == 0

    def test_returns_one_when_any_check_fails(self):
        with patch("check_environment.check_python_version", return_value=True), \
             patch("check_environment.check_dependencies", return_value=False), \
             patch("check_environment.check_chrome", return_value=True), \
             patch("check_environment.check_chromedriver", return_value=True), \
             patch("check_environment.check_version_match", return_value=True), \
             patch("check_environment.check_config_file", return_value=True):
            assert main() == 1
