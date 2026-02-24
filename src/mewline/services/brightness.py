import os
import re
import subprocess
from pathlib import Path

from fabric.core.service import Property
from fabric.core.service import Service
from fabric.core.service import Signal
from fabric.utils import exec_shell_command_async
from fabric.utils import monitor_file
from gi.repository import GLib
from loguru import logger

from mewline.utils.misc import executable_exists


def get_device(path: Path):
    if not path.exists():
        return ""
    for item in path.iterdir():
        if item.is_dir():
            return item.name
    return ""


class BrightnessService(Service):
    """Service to manage screen brightness levels.

    Supports two backends:
    - brightnessctl — for laptops / internal screens (backlight devices in
      /sys/class/backlight). Changes are detected via a file monitor so the
      UI stays in sync automatically.
    - ddcutil — for external / desktop monitors that speak DDC/CI over I2C.
      The first detected I2C bus is used. The brightness value (VCP 0x10) is
      cached locally so reads are instant; writes are sent asynchronously so
      the UI never freezes while waiting for the (slow) monitor response.
    """

    # ------------------------------------------------------------------
    # DDC helpers
    # ------------------------------------------------------------------

    def _ddc_detect_bus(self) -> str:
        """Return the first I2C bus number (e.g. '6') found by ddcutil, or ''."""
        try:
            out = subprocess.check_output(
                ["ddcutil", "detect", "--brief"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=3,
            )
        except Exception:
            return ""
        m = re.search(r"/dev/i2c-(\d+)", out)
        return m.group(1) if m else ""

    def _ddc_get_brightness(self, bus: str) -> tuple[int, int]:
        """Return (current, max) brightness from `ddcutil -b BUS getvcp 10 --brief`.

        Typical output: 'VCP 10 C 60 100'  => current=60, max=100
        """
        try:
            out = subprocess.check_output(
                ["ddcutil", "-b", bus, "getvcp", "10", "--brief"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=3,
            ).strip()
            parts = out.split()
            if len(parts) >= 5 and parts[0] == "VCP" and parts[1] == "10":
                return int(parts[3]), int(parts[4])
        except Exception:  # noqa: S110
            pass
        return 0, 100

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.is_ddc: bool = False
        self.ddc_bus: str = ""
        self._ddc_cached_brightness: int = 0
        self.max_brightness_level: int = -1

        self.base_blacklight_path = Path("/sys/class/backlight")
        self.screen_device = get_device(self.base_blacklight_path)

        # --- Path 1: internal backlight (laptop) ----------------------
        if self.screen_device:
            self.screen_backlight_path = (
                self.base_blacklight_path / self.screen_device
            )
            self.max_brightness_level = self.do_read_max_brightness(
                self.screen_backlight_path
            )

            self.screen_monitor = monitor_file(
                str(self.screen_backlight_path / "brightness")
            )
            self.screen_monitor.connect(
                "changed",
                lambda _, file, *args: self.emit(
                    "screen",
                    round(int(file.load_bytes()[0].get_data())),
                ),
            )

            logger.info(
                f"Brightness service initialised for backlight device: {self.screen_device}"
            )
            return

        # --- Path 2: external monitor via DDC/CI (desktop) -----------
        if executable_exists("ddcutil"):
            bus = self._ddc_detect_bus()
            if bus:
                cur, mx = self._ddc_get_brightness(bus)
                self.is_ddc = True
                self.ddc_bus = bus
                self._ddc_cached_brightness = cur
                self.max_brightness_level = mx if mx > 0 else 100
                logger.info(
                    f"Brightness service initialised via ddcutil (i2c-{bus}), "
                    f"current={cur}, max={self.max_brightness_level}"
                )
                return
            else:
                logger.warning(
                    "ddcutil is installed but no DDC/CI-capable monitors were found."
                )
        else:
            logger.warning("ddcutil is not installed — DDC/CI brightness unavailable.")

        logger.warning(
            "No backlight device and no DDC/CI monitor detected. "
            "Brightness control will be unavailable."
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def do_read_max_brightness(self, path: Path) -> int:
        """Reads the maximum brightness value from the specified path."""
        max_brightness_path = os.path.join(path, "max_brightness")
        if os.path.exists(max_brightness_path):
            with open(max_brightness_path) as f:
                return int(f.readline())
        return -1  # Return -1 if file doesn't exist, indicating an error.

    # ------------------------------------------------------------------
    # Property: screen_brightness
    # ------------------------------------------------------------------

    @Property(int, "read-write")
    def screen_brightness(self) -> int:
        """Property to get or set the screen brightness."""
        if self.is_ddc:
            # Reads from DDC are slow (~100 ms), so return the cached value.
            return self._ddc_cached_brightness

        brightness_path = self.screen_backlight_path / "brightness"
        if brightness_path.exists():
            with open(brightness_path) as f:
                return int(f.readline())
        logger.warning(f"Brightness file does not exist: {brightness_path}")
        return -1  # Return -1 if file doesn't exist, indicating error.

    @screen_brightness.setter
    def screen_brightness(self, value: int):
        """Setter for screen brightness property."""
        value = max(0, min(value, self.max_brightness_level))

        # --- DDC/CI path (external monitor) --------------------------
        if self.is_ddc and self.ddc_bus:
            self._ddc_cached_brightness = value
            # Update the UI percentage immediately (don't wait for hardware)
            if self.max_brightness_level > 0:
                self.emit(
                    "screen",
                    int((value / self.max_brightness_level) * 100),
                )
            try:
                exec_shell_command_async(
                    f"ddcutil -b {self.ddc_bus} setvcp 10 {value}"
                )
            except GLib.Error as e:
                logger.error(f"Error setting ddcutil brightness: {e.message}")
            except Exception as e:
                logger.exception(f"Unexpected error setting ddcutil brightness: {e}")
            return

        # --- brightnessctl path (laptop) -----------------------------
        try:
            if not executable_exists("brightnessctl"):
                logger.error("Command brightnessctl not found")
                return

            exec_shell_command_async(
                f"brightnessctl --device '{self.screen_device}' set {value}"
            )

            self.emit("screen", int((value / self.max_brightness_level) * 100))
        except GLib.Error as e:
            logger.error(f"Error setting screen brightness: {e.message}")
        except Exception as e:
            logger.exception(f"Unexpected error setting screen brightness: {e}")

    @Signal
    def screen(self, value: int) -> None:
        """Signal emitted when screen brightness changes."""
        ...
