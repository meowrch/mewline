from typing import Literal

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


class DatetimeModule(BaseModel):
    format: str


class SpeakersModule(BaseModel):
    icon_size: str
    tooltip: bool
    step_size: int


class MicrophoneModule(BaseModel):
    icon_size: str
    tooltip: bool
    step_size: int


class BatteryModule(BaseModel):
    label: bool
    tooltip: bool


class BrightnessModule(BaseModel):
    icon_size: str
    label: bool
    tooltip: bool
    step_size: int


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
    method: Literal["swww"]
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
    speakers: SpeakersModule
    microphone: MicrophoneModule
    battery: BatteryModule
    brightness: BrightnessModule
    ocr: OcrModule


class Config(BaseModel):
    theme: Theme
    options: Options
    modules: Modules
