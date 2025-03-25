from pathlib import Path

from gi.repository import GLib

NOTIFICATION_WIDTH = 400
NOTIFICATION_IMAGE_SIZE = 64
NOTIFICATION_ACTION_NUMBER = 3
HIGH_POLL_INTERVAL = 1000 * 3600  # 1 hour

APPLICATION_NAME = "mewline"
APP_FOLDER = Path(__file__).resolve().parent
SYSTEM_CACHE_DIR = Path(GLib.get_user_cache_dir())
APP_CACHE_DIRECTORY = SYSTEM_CACHE_DIR / APPLICATION_NAME

WALLPAPERS_DIR = Path.home() / ".config" / "meowrch" / "wallpapers"
WALLPAPERS_THUMBS_DIR = APP_CACHE_DIRECTORY / "thumbs"

STYLES_FOLDER = APP_FOLDER / "styles"
DIST_FOLDER = APP_CACHE_DIRECTORY / "dist"
MAIN_STYLE = STYLES_FOLDER / "main.scss"
THEME_STYLE = STYLES_FOLDER / "theme.scss"
DEFAULT_THEME_STYLE = STYLES_FOLDER / "default_theme.scss"
COMPILED_STYLE = DIST_FOLDER / "main.css"

NOTIFICATION_CACHE_FILE = APP_CACHE_DIRECTORY / "notifications.json"

CLIPBOARD_THUMBS_DIR = APP_CACHE_DIRECTORY / "clipboard_thumbs"

HYPRLAND_CONFIG_FOLDER = Path.home() / ".config" / "hypr"
HYPRLAND_CONFIG_FILE = HYPRLAND_CONFIG_FOLDER / "hyprland.conf"

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
        "system_tray": {"icon_size": 16, "ignore": []},
        "power": {"icon": "", "icon_size": "16px", "tooltip": True},
        "datetime": {"format": "%d-%m-%y %H:%M"},
        "speakers": {
            "icon_size": "16px",
            "tooltip": True,
            "step_size": 5,
        },
        "microphone": {
            "icon_size": "16px",
            "tooltip": True,
            "step_size": 5,
        },
        "battery": {
            "hide_label_when_full": True,
            "label": True,
            "tooltip": True,
        },
        "brightness": {
            "icon_size": "14px",
            "label": True,
            "tooltip": True,
            "step_size": 5,
        },
        "ocr": {
            "icon": "󰴑",
            "icon_size": "20px",
            "tooltip": True,
            "default_lang": "eng",
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
                "shutdown_icon_size": "20px",
            },
            "compact": {
                "window_titles": {
                    "enable_icon": True,
                    "truncation": True,
                    "truncation_size": 50,
                    "title_map": []
                },
                "music": {
                    "enabled": True,
                    "truncation": True,
                    "truncation_size": 30,
                    "default_album_logo": "https://sonos-partner-documentation.s3.amazonaws.com/ReadMe-External/content-service-features/add-images/add-album-art/SonosApp-DefaultArt-Alone.png"
                }
            },
            "wallpapers": {
                "method": "swww"
            }
        },
    },
}


##==> Keybindings (prefix, suffix, command)
############################################
kb_prefix = "Super+Alt"
kb_di_open = "fabric-cli invoke-action mewline dynamic-island-open \"{module}\""
KEYBINDINGS = {
    "power_menu": (kb_prefix, "P", kb_di_open.format(module="power_menu")),
    "date_notification": (kb_prefix, "D", kb_di_open.format(module="date_notification")),
    "bluetooth": (kb_prefix, "B", kb_di_open.format(module="bluetooth")),
    "app_launcher": (kb_prefix, "A", kb_di_open.format(module="app_launcher")),
    "wallpapers": (kb_prefix, "W", kb_di_open.format(module="wallpapers")),
    "emoji": (kb_prefix, "code:60", kb_di_open.format(module="emoji")),
    "clip_history": (kb_prefix, "V", kb_di_open.format(module="clip_history"))
}


##==> Icons
############################################
icons = {
    "fallback": {
        "notification": "dialog-information-symbolic",
    },
    "ui": {
        "close": "window-close-symbolic",
    },
    "notifications": {
        "noisy": "org.gnome.Settings-notifications-symbolic",
        "silent": "notifications-disabled-symbolic",
        "message": "chat-bubbles-symbolic",
    },
    "trash": {
        "full": "user-trash-full-symbolic",
        "empty": "user-trash-symbolic",
    },
    "bluetooth": {
        "paired": "󰌆",
        "bluetooth_connected": "󰂯",
        "bluetooth_disconnected": "󰂲",
    },
    "volume": {
        "overamplified": "󰕾",
        "high": "󰕾",
        "medium": "󰖀",
        "low": "󰕿",
        "muted": "󰝟",
    },
    "microphone": {
        "active": "",
        "muted": ""
    },
    "brightness": {
        "symbolic": "display-brightness-symbolic",
        "off": "󰃝",
        "low": "󰃞",
        "medium": "󰃟",
        "high": "󰃠"
    }
}


WINDOW_TITLE_MAP = [
    # Original Entries
    ["firefox", "󰈹", "Firefox"],
    ["microsoft-edge", "󰇩", "Edge"],
    ["discord", "", "Discord"],
    ["vesktop", "", "Vesktop"],
    ["org.kde.dolphin", "", "Dolphin"],
    ["plex", "󰚺", "Plex"],
    ["steam", "", "Steam"],
    ["spotify", "󰓇", "Spotify"],
    ["yandexmusic", "", "Yandex Music"],
    ["ristretto", "󰋩", "Ristretto"],
    ["obsidian", "󱓧", "Obsidian"],
    ["com.obsproject.studio", "󰑋", "OBS Studio"],
    # Browsers
    ["google-chrome", "", "Google Chrome"],
    ["brave-browser", "󰖟", "Brave Browser"],
    ["chromium", "", "Chromium"],
    ["opera", "", "Opera"],
    ["vivaldi", "󰖟", "Vivaldi"],
    ["waterfox", "󰖟", "Waterfox"],
    ["zen", "󰖟", "Zen Browser"],
    ["thorium", "󰖟", "Thorium"],
    ["tor-browser", "", "Tor Browser"],
    ["floorp", "󰈹", "Floorp"],
    # Terminals
    ["gnome-terminal", "", "GNOME Terminal"],
    ["kitty", "󰄛", "Kitty Terminal"],
    ["konsole", "", "Konsole"],
    ["alacritty", "", "Alacritty"],
    ["wezterm", "", "Wezterm"],
    ["foot", "󰽒", "Foot Terminal"],
    ["tilix", "", "Tilix"],
    ["xterm", "", "XTerm"],
    ["urxvt", "", "URxvt"],
    ["st", "", "st Terminal"],
    ["com.mitchellh.ghostty", "󰊠", "Ghostty"],
    # Development Tools
    ["code", "󰨞", "Visual Studio Code"],
    ["vscode", "󰨞", "VS Code"],
    ["sublime-text", "", "Sublime Text"],
    ["atom", "", "Atom"],
    ["android-studio", "󰀴", "Android Studio"],
    ["intellij-idea", "", "IntelliJ IDEA"],
    ["pycharm", "󱃖", "PyCharm"],
    ["webstorm", "󱃖", "WebStorm"],
    ["phpstorm", "󱃖", "PhpStorm"],
    ["eclipse", "", "Eclipse"],
    ["netbeans", "", "NetBeans"],
    ["docker", "", "Docker"],
    ["vim", "", "Vim"],
    ["neovim", "", "Neovim"],
    ["neovide", "", "Neovide"],
    ["emacs", "", "Emacs"],
    ["pgadmin4", "", "PgAdmin4"],
    # Communication Tools
    ["slack", "󰒱", "Slack"],
    ["telegram-desktop", "", "Telegram"],
    ["org.telegram.desktop", "", "Telegram"],
    ["whatsapp", "󰖣", "WhatsApp"],
    ["teams", "󰊻", "Microsoft Teams"],
    ["skype", "󰒯", "Skype"],
    ["thunderbird", "", "Thunderbird"],
    # File Managers
    ["nautilus", "󰝰", "Files (Nautilus)"],
    ["thunar", "󰝰", "Thunar"],
    ["pcmanfm", "󰝰", "PCManFM"],
    ["nemo", "󰝰", "Nemo"],
    ["ranger", "󰝰", "Ranger"],
    ["doublecmd", "󰝰", "Double Commander"],
    ["krusader", "󰝰", "Krusader"],
    # Media Players
    ["vlc", "󰕼", "VLC Media Player"],
    ["mpv", "", "MPV"],
    ["rhythmbox", "󰓃", "Rhythmbox"],
    # Graphics Tools
    ["gimp", "", "GIMP"],
    ["inkscape", "", "Inkscape"],
    ["krita", "", "Krita"],
    ["blender", "󰂫", "Blender"],
    # Video Editing
    ["kdenlive", "", "Kdenlive"],
    # Games and Gaming Platforms
    ["lutris", "󰺵", "Lutris"],
    ["portproton", "󰺵", "Port Proton"],
    ["heroic", "󰺵", "Heroic Games Launcher"],
    ["minecraft", "󰍳", "Minecraft"],
    ["csgo", "󰺵", "CS:GO"],
    ["dota2", "󰺵", "Dota 2"],
    # Office and Productivity
    ["evernote", "", "Evernote"],
    ["sioyek", "", "Sioyek"],
    # Cloud Services and Sync
    ["dropbox", "󰇣", "Dropbox"],
    # Desktop
    ["^$", "󰇄", "Desktop"],
]
