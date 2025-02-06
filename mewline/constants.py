from pathlib import Path

from gi.repository import GLib

APP_FOLDER = Path(__file__).resolve().parent
STYLES_FOLDER = APP_FOLDER / "styles"
DIST_FOLDER = APP_FOLDER / "dist"

APPLICATION_NAME = "mewline"
SYSTEM_CACHE_DIR = Path(GLib.get_user_cache_dir())
APP_CACHE_DIRECTORY = SYSTEM_CACHE_DIR / APPLICATION_NAME

MAIN_STYLE = STYLES_FOLDER / "main.scss"
THEME_STYLE = STYLES_FOLDER / "theme.scss"
DEFAULT_THEME_STYLE = STYLES_FOLDER / "default_theme.scss"
COMPILED_STYLE = DIST_FOLDER / "main.css"

MEWLINE_SETTINGS_FOLDER = Path.home() / ".config" / "mewline"
MEWLINE_CONFIG_PATH = MEWLINE_SETTINGS_FOLDER / "config.json"
MEWLINE_THEMES_FOLDER = MEWLINE_SETTINGS_FOLDER / "themes"

##==> Default settings
############################################
DEFAULT_CONFIG = {
    "theme": {"name": "default"},
    "options": {
        "screen_corners": True,
        "intercept_notifications": True,
        "osd_enabled": True,
    },
    "modules": {
        "osd": {"timeout": 1500, "anchor": "bottom center"},
        "workspaces": {
            "count": 8,
            "hide_unoccupied": True,
            "ignored": [-99],
            "reverse_scroll": False,
            "empty_scroll": False,
            "icon_map": {
                "1": "1",
                "2": "2",
                "3": "3",
                "4": "4",
                "5": "5",
                "6": "6",
                "7": "7",
                "8": "8",
                "9": "9",
                "10": "10",
            },
        },
        "system_tray": { "icon_size": 16, "ignore": [] },
        "power": { "icon": "", "icon_size": "16px", "tooltip": True },
        "datetime": { "format": "%d-%m-%y %H:%M" },
        "volume": {
            "icon_size": "14px",
            "label": True,
            "tooltip": True,
            "step_size": 5,
            "overamplified_icon": "󰕾",
            "high_icon": "󰕾",
            "medium_icon": "󰖀",
            "low_icon": "󰕿",
            "muted_icon": "󰝟",
        },
        "dynamic_island": {
            "power_menu": {
                "lock_icon": "",
                "lock_icon_size": "20px",
                "suspend_icon": "󰤄",
                "suspend_icon_size": "20px",
                "logout_icon": "󰗽",
                "logout_icon_size": "20px",
                "reboot_icon": "󰑓",
                "reboot_icon_size": "20px",
                "shutdown_icon": "",
                "shutdown_icon_size": "20px"

            }
        }
    },
}

volume_text_icons = {
    "overamplified": "󰕾",
    "high": "󰕾",
    "medium": "󰖀",
    "low": "󰕿",
    "muted": "󰝟",
}