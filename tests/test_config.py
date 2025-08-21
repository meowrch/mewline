# tests/test_config.py

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from mewline.config import load_config
from mewline.utils.config_structure import Config


# Mock constants used in the config module
class MockConstants:
    DEFAULT_CONFIG = {  # noqa: RUF012
        "theme": {"name": "default"},
        "options": {
            "screen_corners": True,
            "intercept_notifications": True,
            "osd_enabled": True,
        },
        "modules": {
            "osd": {"timeout": 2000, "anchor": "top"},
            "workspaces": {
                "count": 5,
                "hide_unoccupied": False,
                "ignored": [],
                "reverse_scroll": False,
                "empty_scroll": False,
                "icon_map": {},
            },
            "system_tray": {
                "icon_size": 24,
                "ignore": [],
            },
            "power": {
                "icon": "power-icon",
                "icon_size": "16px",
                "tooltip": True,
            },
            "dynamic_island": {
                "power_menu": {
                    "lock_icon": "lock",
                    "lock_icon_size": "16px",
                    "suspend_icon": "suspend",
                    "suspend_icon_size": "16px",
                    "logout_icon": "logout",
                    "logout_icon_size": "16px",
                    "reboot_icon": "reboot",
                    "reboot_icon_size": "16px",
                    "shutdown_icon": "shutdown",
                    "shutdown_icon_size": "16px",
                },
                "compact": {
                    "window_titles": {
                        "enable_icon": True,
                        "truncation": True,
                        "truncation_size": 30,
                        "title_map": [],
                    },
                    "music": {
                        "enabled": True,
                        "truncation": True,
                        "truncation_size": 30,
                        "default_album_logo": "logo.png",
                    },
                },
                "wallpapers": {
                    "wallpapers_dirs": [],
                    "method": "swww",
                    "save_current_wall": True,
                    "current_wall_path": "/path/to/wall",
                },
            },
            "datetime": {"format": "%H:%M"},
            "speakers": {"icon_size": "16px", "tooltip": True, "step_size": 5},
            "microphone": {"icon_size": "16px", "tooltip": True, "step_size": 5},
            "battery": {"show_label": True, "tooltip": True},
            "brightness": {
                "icon_size": "16px",
                "label": True,
                "tooltip": True,
                "step_size": 5,
            },
            "ocr": {
                "icon": "ocr-icon",
                "icon_size": "16px",
                "tooltip": True,
                "default_lang": "eng",
            },
        },
    }


@pytest.fixture(autouse=True)
def caplog_for_loguru(caplog):
    from loguru import logger

    logger.remove()
    logger.add(
        caplog.handler,
        format="{message}",
        level="INFO",
        enqueue=False,  # Set to False for immediate logging
    )


@pytest.fixture
def mock_config_file(tmp_path: Path):
    def _mock_config_file(content):
        path = tmp_path / "config.json"
        if content is not None:
            with open(path, "w") as f:
                json.dump(content, f)
        return path

    return _mock_config_file


@patch("mewline.config.cnst", MockConstants)
def test_load_config_no_file(mock_config_file):
    config_path = mock_config_file(None)
    if os.path.exists(config_path):
        os.remove(config_path)

    config = load_config(config_path)
    assert config == Config.model_validate(MockConstants.DEFAULT_CONFIG)


@patch("mewline.config.cnst", MockConstants)
def test_load_config_with_valid_user_config(mock_config_file):
    user_config = {
        "theme": {"name": "custom"},
        "modules": {"osd": {"timeout": 3000}},
    }
    config_path = mock_config_file(user_config)
    config = load_config(config_path)

    assert config.theme.name == "custom"
    assert config.modules.osd.timeout == 3000
    assert config.options.screen_corners is True  # Merged from default


@patch("mewline.config.cnst", MockConstants)
def test_load_config_with_invalid_json(mock_config_file):
    config_path = mock_config_file(None)
    with open(config_path, "w") as f:
        f.write("not a valid json")

    config = load_config(config_path)
    assert config == Config.model_validate(MockConstants.DEFAULT_CONFIG)


@patch("mewline.config.cnst", MockConstants)
def test_load_config_with_validation_errors(mock_config_file, caplog):
    user_config = {
        "options": {"screen_corners": "not-a-bool"},
        "modules": {"osd": {"timeout": "not-an-int"}},
    }
    config_path = mock_config_file(user_config)

    config = load_config(config_path)

    # Check that invalid fields are reverted to default
    assert config.options.screen_corners is True
    assert config.modules.osd.timeout == 2000

    # Check that a valid user-provided field is kept
    assert config.theme.name == "default"  # from default

    # Check logs for warnings
    assert "Invalid values found in configuration" in caplog.text
    assert "Reverted 'options.screen_corners' to its default value" in caplog.text
    assert "Reverted 'modules.osd.timeout' to its default value" in caplog.text


@patch("mewline.config.cnst", MockConstants)
def test_deeply_nested_config_merge(mock_config_file):
    user_config = {"modules": {"workspaces": {"icon_map": {"1": "a", "2": "b"}}}}
    config_path = mock_config_file(user_config)
    config = load_config(config_path)

    # Merged value
    assert config.modules.workspaces.icon_map == {"1": "a", "2": "b"}
    # Default value from the same level
    assert config.modules.workspaces.count == 5


@patch("mewline.config.cnst", MockConstants)
def test_new_field_in_user_config(mock_config_file):
    # Pydantic should ignore extra fields by default
    user_config = {"new_top_level_field": "some_value", "modules": {"new_module": {}}}
    config_path = mock_config_file(user_config)
    config = load_config(config_path)

    # Should not raise an error, and the new fields should not be in the model
    assert not hasattr(config, "new_top_level_field")
    assert not hasattr(config.modules, "new_module")
