import re
from typing import Literal

from pydantic import BaseModel
from pydantic import field_validator

# Shell metacharacters that could enable command injection.
# $( and backtick allow command substitution; |, ;, & chain commands;
# <, > redirect I/O; ( ) start subshells.
# Plain $VAR / ${VAR} references are intentionally allowed so users can
# point to scripts via env-var paths (expanded at runtime, not here).
_UNSAFE_SHELL_RE = re.compile(r"[|;&`<>()]|\$\(")


class Theme(BaseModel):
    name: str


class Options(BaseModel):
    screen_corners: bool
    intercept_notifications: bool
    osd_enabled: bool


class MonitorsConfig(BaseModel):
    """Configuration for multi-monitor support.

    mode:
      - "all"    – show the bar and dynamic island on every connected monitor
      - "cursor" – show only on the monitor that currently holds the pointer
      - "list"   – show only on the monitors explicitly listed in *list*
    monitors_list:
      List of Hyprland monitor names (e.g. ["DP-1", "HDMI-A-1"]) used when
      mode == "list".
    """

    mode: Literal["all", "cursor", "list"] = "all"
    monitors_list: list[str] = []


class NotificationsMonitorConfig(BaseModel):
    """Configuration for notifications display across monitors.

    mode:
      - "all"    – show notifications on every connected monitor (default)
      - "cursor" – show only on the monitor that currently holds the pointer
      - "list"   – show only on the monitors explicitly listed in *list*
    monitors_list:
      List of Hyprland monitor names (e.g. ["DP-1", "HDMI-A-1"]) used when
      mode == "list".
    """

    mode: Literal["all", "cursor", "list"] = "all"
    monitors_list: list[str] = []


class OSDModule(BaseModel):
    timeout: int
    anchor: str


class WorkspacesModule(BaseModel):
    count: int
    hide_unoccupied: bool
    ignored: list[int]
    reverse_scroll: bool
    empty_scroll: bool
    icon_map: dict[str, str]
    navigate_empty: bool


class TrayModule(BaseModel):
    icon_size: int
    ignore: list[str]
    pinned: list[str]


class PowerModule(BaseModel):
    icon: str
    icon_size: str
    tooltip: bool


class PowerMenuCommands(BaseModel):
    """Commands executed for each power-menu action.

    Keys of the ``commands`` dict in :class:`PowerMenu` must match the value
    of ``XDG_CURRENT_DESKTOP`` (compared case-insensitively at runtime).

    **Environment-variable substitution** – ``$VAR`` and ``${VAR}`` references
    inside a command string are expanded at runtime via
    :func:`os.path.expandvars` *before* the command is split and executed.
    This lets you write paths like ``$HOME/.local/bin/screen-lock.sh``
    without hard-coding your home directory.

    **Security** – Commands are executed via :func:`subprocess.Popen` with
    ``shell=False``, so no shell features (pipes, redirections, command
    substitution, etc.) are available.  To enforce this, the validator rejects
    any command string that contains the following characters or sequences:
    ``|``, ``;``, ``&``, backtick, ``<``, ``>``, ``(``, ``)``, ``$(``.  If
    you need complex logic, put it in a standalone script and reference that
    script here.
    """

    lock: str = "hyprlock"
    logout: str = "hyprctl dispatch exit"
    suspend: str = "systemctl suspend"
    reboot: str = "systemctl reboot"
    shutdown: str = "systemctl poweroff"

    @field_validator("lock", "logout", "suspend", "reboot", "shutdown", mode="before")
    @classmethod
    def _no_shell_metacharacters(cls, v: str) -> str:
        if _UNSAFE_SHELL_RE.search(v):
            raise ValueError(
                f"Command contains unsafe shell metacharacters: {v!r}. "
                "Shell features are not supported; use an absolute path to a "
                "wrapper script instead (e.g. /home/user/.local/bin/lock.sh)."
            )
        return v


class PowerMenu(BaseModel):
    lock_icon: str
    lock_icon_size: str
    suspend_icon: str
    suspend_icon_size: str
    logout_icon: str
    logout_icon_size: str
    reboot_icon: str
    reboot_icon_size: str
    shutdown_icon: str
    shutdown_icon_size: str
    commands: dict[str, PowerMenuCommands] = {}


class DatetimeModule(BaseModel):
    format: str


class BatteryModule(BaseModel):
    show_label: bool
    tooltip: bool


class OcrModule(BaseModel):
    icon: str
    icon_size: str
    tooltip: bool
    default_lang: str


class WindowTitlesModule(BaseModel):
    enable_icon: bool
    truncation: bool
    truncation_size: int
    title_map: list[tuple[str, str, str]]


class MusicModule(BaseModel):
    enabled: bool
    truncation: bool
    truncation_size: int
    default_album_logo: str


class Compact(BaseModel):
    window_titles: WindowTitlesModule
    music: MusicModule


class WallpapersMenu(BaseModel):
    wallpapers_dirs: list[str]
    x11_method: Literal["feh"]
    wayland_method: Literal["swww"]
    save_current_wall: bool
    current_wall_path: str


class DynamicIsland(BaseModel):
    power_menu: PowerMenu
    compact: Compact
    wallpapers: WallpapersMenu


class Modules(BaseModel):
    osd: OSDModule
    workspaces: WorkspacesModule
    system_tray: TrayModule
    power: PowerModule
    dynamic_island: DynamicIsland
    datetime: DatetimeModule
    battery: BatteryModule
    ocr: OcrModule


class Config(BaseModel):
    theme: Theme
    options: Options
    modules: Modules
    monitors: MonitorsConfig = MonitorsConfig()
    notifications_monitors: NotificationsMonitorConfig = NotificationsMonitorConfig()
