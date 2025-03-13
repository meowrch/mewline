import os
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
    for item in path.iterdir():
        if item.is_file():
            return item.stem

    return ""


class BrightnessService(Service):
    """Service to manage screen brightness levels."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.base_blacklight_path = Path("/sys/class/backlight")
        self.screen_device = get_device(self.base_blacklight_path)

        self.screen_backlight_path = self.base_blacklight_path / self.screen_device
        self.max_brightness_level = self.do_read_max_brightness(
            self.screen_backlight_path
        )

        if self.screen_device == "":
            logger.warning("No backlight devices found!")
            return

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

        logger.info(f"Brightness service initialized for device: {self.screen_device}")

    def do_read_max_brightness(self, path: str) -> int:
        """Reads the maximum brightness value from the specified path."""
        max_brightness_path = os.path.join(path, "max_brightness")
        if os.path.exists(max_brightness_path):
            with open(max_brightness_path) as f:
                return int(f.readline())
        return -1  # Return -1 if file doesn't exist, indicating an error.

    @Property(int, "read-write")
    def screen_brightness(self) -> int:
        """Property to get or set the screen brightness."""
        brightness_path = self.screen_backlight_path / "brightness"
        if brightness_path.exists():
            with open(brightness_path) as f:
                return int(f.readline())
        logger.warning(f"Brightness file does not exist: {brightness_path}")
        return -1  # Return -1 if file doesn't exist, indicating error.

    @screen_brightness.setter
    def screen_brightness(self, value: int):
        """Setter for screen brightness property."""
        if not (0 <= value <= self.max_brightness_level):
            value = max(0, min(value, self.max_brightness_level))

        try:
            if not executable_exists("brightnessctl"):
                logger.error("Command brightnessctl not found")

            exec_shell_command_async(
                f"brightnessctl --device '{self.screen_device}' set {value}"
            )

            self.emit("screen", int((value / self.max_brightness_level) * 100))
            logger.info(
                f"Set screen brightness to {value} (out of {self.max_brightness_level})"
            )
        except GLib.Error as e:
            logger.error(f"Error setting screen brightness: {e.message}")
        except Exception as e:
            logger.exception(f"Unexpected error setting screen brightness: {e}")

    @Signal
    def screen(self, value: int) -> None:
        """Signal emitted when screen brightness changes."""
        ...
