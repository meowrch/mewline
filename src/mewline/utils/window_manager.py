"""Window manager detection utilities."""

import os
import subprocess
from enum import Enum

from loguru import logger


class WindowManager(Enum):
    """Supported window managers."""

    HYPRLAND = "hyprland"
    BSPWM = "bspwm"
    UNKNOWN = "unknown"


def detect_window_manager() -> WindowManager:
    """Detect the currently running window manager.

    Returns:
        WindowManager: The detected window manager.
    """
    # Check for Wayland
    if os.environ.get("WAYLAND_DISPLAY"):
        # Check if Hyprland is running
        try:
            result = subprocess.run(
                ["hyprctl", "version"],
                capture_output=True,
                timeout=1,
                check=False,
            )
            if result.returncode == 0:
                logger.info("Detected Hyprland (Wayland)")
                return WindowManager.HYPRLAND
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Check for X11
    if os.environ.get("DISPLAY"):
        # Check if bspwm is running
        try:
            result = subprocess.run(
                ["pgrep", "-x", "bspwm"],
                capture_output=True,
                timeout=1,
                check=False,
            )
            if result.returncode == 0:
                logger.info("Detected bspwm (X11)")
                return WindowManager.BSPWM
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    logger.warning("Could not detect window manager, assuming Hyprland")
    return WindowManager.UNKNOWN


def get_display_backend() -> str | None:
    """Get the display backend (wayland or x11).

    Returns:
        Optional[str]: 'wayland' or 'x11' or None if unknown.
    """
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    elif os.environ.get("DISPLAY"):
        return "x11"
    return None
