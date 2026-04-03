"""
Shared pytest fixtures and configuration.
"""

import json
import sys
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import Mock, patch

import pytest

# Add project root + web/ to sys.path.
# web/ is added for bare imports inside web modules (from config import Config, from concert import Concert).
# mobile/ is NOT added — use mobile.config / mobile.damai_app to avoid Config name clash.
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
_web_dir = str(_project_root / "web")
if _web_dir not in sys.path:
    sys.path.insert(0, _web_dir)

# Preserve the real uiautomator2.exceptions module before mocking the package,
# so ``from uiautomator2.exceptions import ConnectError`` still resolves.
import importlib as _importlib

_real_u2_exceptions = _importlib.import_module("uiautomator2.exceptions")

# Mock uiautomator2 package for tests that exercise u2 backend without real devices
_mock_uiautomator2 = Mock()
_mock_uiautomator2.connect = Mock()
sys.modules["uiautomator2"] = _mock_uiautomator2
sys.modules["uiautomator2.exceptions"] = _real_u2_exceptions


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_config() -> dict:
    """Provide a mock configuration for tests."""
    return {
        "username": "test_user",
        "password": "test_password",
        "target_url": "https://example.com",
        "ticket_count": 1,
        "seat_type": "VIP",
        "price_levels": ["580", "380"],
        "dates": ["2024-01-01"],
        "retry_times": 3,
        "timeout": 30,
    }


@pytest.fixture
def mock_selenium_driver():
    """Mock Selenium WebDriver for unit tests."""
    with patch("selenium.webdriver.Chrome") as mock_driver_class:
        mock_driver = Mock()
        mock_driver_class.return_value = mock_driver

        # Common WebDriver methods
        mock_driver.get = Mock()
        mock_driver.find_element = Mock()
        mock_driver.find_elements = Mock()
        mock_driver.quit = Mock()
        mock_driver.current_url = "https://example.com"
        mock_driver.title = "Test Page"

        yield mock_driver


@pytest.fixture
def mock_u2_driver():
    """Mock u2 device for mobile tests."""
    mock_driver = Mock()
    mock_driver.find_element = Mock()
    mock_driver.find_elements = Mock()
    mock_driver.tap = Mock()
    mock_driver.swipe = Mock()
    mock_driver.quit = Mock()
    mock_driver.click = Mock()
    mock_driver.shell = Mock()
    mock_driver.app_current = Mock(return_value={"package": "cn.damai"})
    mock_driver.settings = {}
    yield mock_driver


@pytest.fixture
def sample_html_response() -> str:
    """Provide sample HTML response for parsing tests."""
    return """
    <html>
        <body>
            <div class="ticket-info">
                <span class="price">¥380</span>
                <span class="seat-type">VIP座位</span>
                <button class="buy-btn">立即购买</button>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def mock_time(monkeypatch):
    """Mock time-related functions for deterministic tests."""
    import time

    current_time = 1704067200.0  # 2024-01-01 00:00:00 UTC

    def mock_time_func():
        return current_time

    def mock_sleep(seconds):
        nonlocal current_time
        current_time += seconds

    monkeypatch.setattr(time, "time", mock_time_func)
    monkeypatch.setattr(time, "sleep", mock_sleep)

    return mock_time_func


@pytest.fixture(autouse=True)
def reset_environment(monkeypatch):
    """Reset environment variables for each test."""
    # Clear any environment variables that might affect tests
    env_vars_to_clear = [
        "DAMAI_USERNAME",
        "DAMAI_PASSWORD",
        "SELENIUM_DRIVER_PATH",
    ]

    for var in env_vars_to_clear:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def mock_file_operations(tmp_path):
    """Provide mocked file operations for tests."""

    def create_test_file(filename: str, content: str = "") -> Path:
        file_path = tmp_path / filename
        file_path.write_text(content)
        return file_path

    return create_test_file


# Pytest configuration hooks
def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Add custom markers description
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add markers based on test file location
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


# ── New fixtures for regression tests ──


@pytest.fixture
def web_config():
    """Create a real web Config instance for testing."""
    from config import Config as WebConfig

    return WebConfig(
        index_url="https://www.damai.cn/",
        login_url="https://passport.damai.cn/login",
        target_url="https://detail.damai.cn/item.htm?id=123",
        users=["UserA", "UserB"],
        city="杭州",
        dates=["2026-04-11"],
        prices=["680"],
        if_listen=True,
        if_commit_order=True,
        max_retries=3,
        fast_mode=True,
        page_load_delay=0.1,
    )


@pytest.fixture
def mobile_config():
    """Create a real mobile Config instance for testing."""
    from mobile.config import Config as MobileConfig

    return MobileConfig(
        keyword="test",
        users=["UserA", "UserB"],
        city="深圳",
        date="12.06",
        price="799元",
        price_index=1,
        if_commit_order=True,
    )


@pytest.fixture
def mock_concert(web_config, mock_selenium_driver):
    """Create a Concert instance with mocked WebDriver."""
    with (
        patch("concert.get_chromedriver_path", return_value="/fake/chromedriver"),
        patch("concert.webdriver.Chrome", return_value=mock_selenium_driver),
        patch("concert.Service"),
    ):
        from concert import Concert

        concert = Concert(web_config)
        yield concert


@pytest.fixture
def mock_damai_bot(mobile_config, mock_u2_driver):
    """Create a DamaiBot instance with mocked u2 driver."""
    mock_u2_driver.update_settings = Mock()
    mock_u2_driver.execute_script = Mock()
    mock_u2_driver.find_element = Mock()
    mock_u2_driver.find_elements = Mock(return_value=[])

    with (
        patch("mobile.damai_app.Config.load_config", return_value=mobile_config),
        patch("uiautomator2.connect", return_value=mock_u2_driver),
    ):
        from mobile.damai_app import DamaiBot

        bot = DamaiBot()
        yield bot


@pytest.fixture
def mock_web_config_file(tmp_path):
    """Create a temporary web config.json file."""

    def create(content=None):
        if content is None:
            content = {
                "index_url": "https://www.damai.cn/",
                "login_url": "https://passport.damai.cn/login",
                "target_url": "https://detail.damai.cn/item.htm?id=123",
                "users": ["UserA", "UserB"],
                "city": "杭州",
                "dates": ["2026-04-11"],
                "prices": ["680"],
                "if_listen": True,
                "if_commit_order": True,
                "max_retries": 3,
            }
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(content, ensure_ascii=False), encoding="utf-8"
        )
        return config_path

    return create


@pytest.fixture
def mock_mobile_config_file(tmp_path):
    """Create a temporary mobile config.jsonc file."""

    def create(content=None, raw_text=None):
        if raw_text is not None:
            config_path = tmp_path / "config.jsonc"
            config_path.write_text(raw_text, encoding="utf-8")
            return config_path
        if content is None:
            content = {
                "keyword": "test",
                "users": ["UserA", "UserB"],
                "city": "深圳",
                "date": "12.06",
                "price": "799元",
                "price_index": 1,
                "if_commit_order": True,
            }
        config_path = tmp_path / "config.jsonc"
        config_path.write_text(
            json.dumps(content, ensure_ascii=False), encoding="utf-8"
        )
        return config_path

    return create
