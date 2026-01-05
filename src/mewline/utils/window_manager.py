"""Window manager detection and adaptive window utilities."""

import os
import subprocess
from enum import Enum
from typing import Any

from fabric.widgets.wayland import WaylandWindow
from loguru import logger

try:
    from fabric.widgets.x11 import X11Window

    X11_AVAILABLE = True
except ImportError:
    X11_AVAILABLE = False
    logger.warning("X11Window not available in fabric, X11 support will be limited")


class WindowManager(Enum):
    """Supported window managers."""

    HYPRLAND = "hyprland"
    BSPWM = "bspwm"
    UNKNOWN = "unknown"


class WindowManagerContext:
    """Global context for window manager type."""

    _wm: WindowManager | None = None

    @classmethod
    def set_wm(cls, wm: WindowManager):
        """Set the current window manager type.

        Args:
            wm: The window manager to set.
        """
        cls._wm = wm
        logger.info(f"Window manager context set to: {wm.value}")

    @classmethod
    def get_wm(cls) -> WindowManager:
        """Get the current window manager type.

        Returns:
            The current window manager.

        Raises:
            RuntimeError: If window manager not set.
        """
        if cls._wm is None:
            raise RuntimeError(
                "Window manager not set. Call WindowManagerContext.set_wm() first."
            )
        return cls._wm

    @classmethod
    def is_wayland(cls) -> bool:
        """Check if current WM is Wayland-based.

        Returns:
            True if Wayland-based WM.
        """
        return cls.get_wm() == WindowManager.HYPRLAND

    @classmethod
    def is_x11(cls) -> bool:
        """Check if current WM is X11-based.

        Returns:
            True if X11-based WM.
        """
        return cls.get_wm() == WindowManager.BSPWM


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
        str | None: 'wayland' or 'x11' or None if unknown.
    """
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    elif os.environ.get("DISPLAY"):
        return "x11"
    return None


class AdaptiveWindow:
    """Base class for creating windows that adapt to the current window manager.

    This class automatically creates either a WaylandWindow or X11Window based on
    the detected window manager, allowing platform-specific configuration.

    Usage:
        window = AdaptiveWindow(
            wayland_kwargs={
                'layer': 'top',
                'anchor': 'top left right',
            },
            x11_kwargs={
                'type_hint': 'dock',
                'geometry': 'top',
            },
            visible=True,
            child=my_widget,
        )
    """

    def __new__(
        cls,
        wayland_kwargs: dict | None = None,
        x11_kwargs: dict | None = None,
        **common_kwargs,
    ):
        """Create appropriate window type based on current WM.

        Args:
            wayland_kwargs: Parameters specific to WaylandWindow.
            x11_kwargs: Parameters specific to X11Window.
            **common_kwargs: Common parameters for both window types.

        Returns:
            WaylandWindow or X11Window instance.

        Raises:
            RuntimeError: If X11 window requested but not available.
        """
        wayland_kwargs = wayland_kwargs or {}
        x11_kwargs = x11_kwargs or {}

        if WindowManagerContext.is_wayland():
            # Merge wayland-specific and common kwargs
            kwargs = {**common_kwargs, **wayland_kwargs}
            logger.debug(f"Creating WaylandWindow with kwargs: {kwargs.keys()}")
            return WaylandWindow(**kwargs)
        else:
            if not X11_AVAILABLE:
                logger.error(
                    "X11Window not available in fabric, cannot create X11 window"
                )
                raise RuntimeError(
                    "X11Window not available. Please update fabric to a version with X11 support."
                )
            # Merge x11-specific and common kwargs
            kwargs = {**common_kwargs, **x11_kwargs}
            logger.debug(f"Creating X11Window with kwargs: {kwargs.keys()}")
            return X11Window(**kwargs)


def create_adaptive_window(
    wayland_kwargs: dict | None = None,
    x11_kwargs: dict | None = None,
    **common_kwargs,
) -> Any:
    """Factory function to create adaptive windows.

    This is the recommended way to create windows that work across both
    Wayland and X11 environments.

    Args:
        wayland_kwargs: Parameters specific to WaylandWindow (e.g., layer, anchor).
        x11_kwargs: Parameters specific to X11Window (e.g., type_hint, geometry).
        **common_kwargs: Common parameters for both window types (e.g., visible, child).

    Returns:
        WaylandWindow or X11Window instance based on current WM.

    Example:
        window = create_adaptive_window(
            wayland_kwargs={
                'layer': 'overlay',
                'anchor': 'bottom',
                'pass_through': True,
            },
            x11_kwargs={
                'type_hint': 'dock',
                'geometry': 'bottom',
            },
            visible=False,
            child=my_widget,
        )
    """
    return AdaptiveWindow(
        wayland_kwargs=wayland_kwargs,
        x11_kwargs=x11_kwargs,
        **common_kwargs,
    )
