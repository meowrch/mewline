from typing import Dict, List

from pydantic import BaseModel


class Theme(BaseModel):  # noqa: D101
    name: str


class Options(BaseModel):  # noqa: D101
    screen_corners: bool
    intercept_notifications: bool
    osd_enabled: bool


class OSDModule(BaseModel):  # noqa: D101
    timeout: int
    anchor: str


class WorkspacesModule(BaseModel):  # noqa: D101
    count: int
    hide_unoccupied: bool
    ignored: List[int]
    reverse_scroll: bool
    empty_scroll: bool
    icon_map: Dict[str, str]


class TrayModule(BaseModel):  # noqa: D101
    icon_size: int
    ignore: List[str]


class PowerModule(BaseModel):  # noqa: D101
    icon: str
    icon_size: str
    tooltip: bool


class PowerMenu(BaseModel):  # noqa: D101
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


class DynamicIsland(BaseModel):  # noqa: D101
    power_menu: PowerMenu


class DatetimeModule(BaseModel):  # noqa: D101
    format: str


class Modules(BaseModel):  # noqa: D101
    osd: OSDModule
    workspaces: WorkspacesModule
    system_tray: TrayModule
    power: PowerModule
    dynamic_island: DynamicIsland
    datetime: DatetimeModule


class Config(BaseModel):  # noqa: D101
    theme: Theme
    options: Options
    modules: Modules
