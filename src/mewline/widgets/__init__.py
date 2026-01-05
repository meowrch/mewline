"""Widget exports with automatic window manager detection."""

from loguru import logger

from mewline.utils.window_manager import WindowManager
from mewline.utils.window_manager import detect_window_manager
from mewline.widgets.battery import Battery
from mewline.widgets.bluetooth import Bluetooth
from mewline.widgets.combined_controls import CombinedControlsButton
from mewline.widgets.datetime import DateTimeWidget
from mewline.widgets.language import LanguageWidget
from mewline.widgets.network_status import NetworkStatus
from mewline.widgets.ocr import OCRWidget
from mewline.widgets.power import PowerButton
from mewline.widgets.status_bar import BspwmStatusBar
from mewline.widgets.status_bar import WaylandStatusBar
from mewline.widgets.system_tray import SystemTray
from mewline.widgets.workspaces import HyprlandWorkSpacesWidget

# Detect window manager and set StatusBar accordingly
_wm = detect_window_manager()

if _wm == WindowManager.BSPWM:
    logger.info("Using BspwmStatusBar for X11/bspwm")
    StatusBar = BspwmStatusBar
elif _wm == WindowManager.HYPRLAND:
    logger.info("Using WaylandStatusBar for Hyprland")
    StatusBar = WaylandStatusBar
else:
    logger.warning(
        "Unknown window manager, defaulting to WaylandStatusBar. "
        "If you're using bspwm, make sure it's running."
    )
    StatusBar = WaylandStatusBar

__all__ = [
    "Battery",
    "Bluetooth",
    "CombinedControlsButton",
    "DateTimeWidget",
    "LanguageWidget",
    "NetworkStatus",
    "OCRWidget",
    "PowerButton",
    "StatusBar",
    "SystemTray",
    "HyprlandWorkSpacesWidget",
    "BspwmStatusBar",
    "WaylandStatusBar",
]
