from pydantic import BaseModel


class Theme(BaseModel):
    name: str


class Options(BaseModel):
    screen_corners: bool
    intercept_notifications: bool
    osd_enabled: bool


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


class TrayModule(BaseModel):
    icon_size: int
    ignore: list[str]


class PowerModule(BaseModel):
    icon: str
    icon_size: str
    tooltip: bool


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


class DynamicIsland(BaseModel):
    power_menu: PowerMenu


class DatetimeModule(BaseModel):
    format: str


class VolumeModule(BaseModel):
    icon_size: str
    label: bool
    tooltip: bool
    step_size: int
    overamplified_icon: str
    high_icon: str
    medium_icon: str
    low_icon: str
    muted_icon: str


class BatteryModule(BaseModel):
    hide_label_when_full: bool
    label: bool
    tooltip: bool

class Modules(BaseModel):
    osd: OSDModule
    workspaces: WorkspacesModule
    system_tray: TrayModule
    power: PowerModule
    dynamic_island: DynamicIsland
    datetime: DatetimeModule
    volume: VolumeModule
    battery: BatteryModule


class Config(BaseModel):
    theme: Theme
    options: Options
    modules: Modules
