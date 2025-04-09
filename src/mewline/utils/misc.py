import datetime
import os
import shlex
import shutil
import subprocess
import time
from functools import lru_cache
from typing import Literal

import gi
import psutil
from fabric.utils import exec_shell_command
from fabric.utils import exec_shell_command_async
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gtk
from loguru import logger

gi.require_version("Gtk", "3.0")


# Function to escape the markup
def parse_markup(text):
    return text


# support for multiple monitors
def for_monitors(widget):
    n = Gdk.Display.get_default().get_n_monitors() if Gdk.Display.get_default() else 1
    return [widget(i) for i in range(n)]


# Merge the parsed data with the default configuration
def merge_defaults(data: dict, defaults: dict):
    return {**defaults, **data}


# Validate the widgets
def validate_widgets(parsed_data, default_config):
    layout = parsed_data["layout"]
    for section in layout:
        for widget in layout[section]:
            if widget not in default_config:
                raise ValueError(
                    f"Invalid widget {widget} found in section {section}. Please check the widget name."
                )


# Function to exclude keys from a dictionary        )
def exclude_keys(d: dict, keys_to_exclude: list[str]) -> dict:
    return {k: v for k, v in d.items() if k not in keys_to_exclude}


# Function to format time in hours and minutes
def format_time(secs: int):
    mm, _ = divmod(secs, 60)
    hh, mm = divmod(mm, 60)
    return f"{hh} h {mm} min"


# Function to convert bytes to kilobytes, megabytes, or gigabytes
def convert_bytes(bytes: int, to: Literal["kb", "mb", "gb"], format_spec=".1f"):
    multiplier = 1

    if to == "mb":
        multiplier = 2
    elif to == "gb":
        multiplier = 3

    return f"{format(bytes / (1024**multiplier), format_spec)}{to.upper()}"


# Function to get the system uptime
def uptime():
    boot_time = psutil.boot_time()
    now = datetime.datetime.now()

    diff = now.timestamp() - boot_time

    # Convert the difference in seconds to hours and minutes
    hours, remainder = divmod(diff, 3600)
    minutes, _ = divmod(remainder, 60)

    return f"{int(hours):02}:{int(minutes):02}"


# Function to convert seconds to milliseconds
def convert_seconds_to_milliseconds(seconds: int):
    return seconds * 1000


# Function to check if an icon exists, otherwise use a fallback icon
def check_icon_exists(icon_name: str, fallback_icon: str) -> str:
    if Gtk.IconTheme.get_default().has_icon(icon_name):
        return icon_name
    return fallback_icon


# Function to execute a shell command asynchronously
def play_sound(file: str):
    exec_shell_command_async(f"play {file}", None)


# Function to check if an executable exists
def executable_exists(executable_name):
    executable_path = shutil.which(executable_name)
    return bool(executable_path)


def send_notification(
    title: str,
    body: str,
    urgency: Literal["low", "normal", "critical"],
    icon=None,
    app_name="Application",
    timeout=None,
):
    """Sends a notification using the notify-send command.

    Args:
        title (str): The title of the notification
        body (str): The message body of the notification
        urgency (Literal): The urgency of the notification ('low', 'normal', 'critical')
        icon (_type_, optional): Optional icon for the notification. Defaults to None.
        app_name (str, optional): The application name. Defaults to "Application".
        timeout (_type_, optional): Timeout in milliseconds. Defaults to None.
    """
    # Base command
    command = [
        "notify-send",
        "--urgency",
        shlex.quote(urgency),
        "--app-name",
        shlex.quote(app_name),
        shlex.quote(title),
        shlex.quote(body),
    ]

    # Add icon if provided
    if icon:
        command.extend(["--icon", icon])

    if timeout is not None:
        command.extend(["-t", str(timeout)])

    if urgency not in ["low", "normal", "critical"]:
        raise ValueError("Invalid urgency level")

    if icon and not os.path.isfile(icon):
        raise ValueError("Invalid icon path")

    if timeout is not None and not isinstance(timeout, int):
        raise ValueError("Timeout must be an integer")

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to send notification: {e}")


# Function to get the relative time
def get_relative_time(mins: int) -> str:
    # Seconds
    if mins == 0:
        return "now"

    # Minutes
    if mins < 60:
        return f"{mins} minute{'s' if mins > 1 else ''} ago"

    # Hours
    if mins < 1440:
        hours = mins // 60
        return f"{hours} hour{'s' if hours > 1 else ''} ago"

    # Days
    days = mins // 1440
    return f"{days} day{'s' if days > 1 else ''} ago"


# Function to get the percentage of a value
def convert_to_percent(
    current: int | float, max: int | float, is_int=True
) -> int | float:
    if is_int:
        return int((current / max) * 100)
    else:
        return (current / max) * 100


# Function to ensure the directory exists
def ensure_dir_exists(path: str):
    if not os.path.exists(path):
        os.makedirs(path)


# Function to unique list
def unique_list(lst) -> list:
    return list(set(lst))


# Function to check if an app is running
def is_app_running(app_name: str) -> bool:
    return len(exec_shell_command(f"pidof {app_name}")) != 0


def disable_logging():
    for log in [
        "fabric.hyprland.widgets",
        "fabric.audio.service",
        "fabric.bluetooth.service",
    ]:
        logger.disable(log)


def ttl_lru_cache(seconds_to_live: int, maxsize: int = 128):
    def wrapper(func):
        @lru_cache(maxsize)
        def inner(__ttl, *args, **kwargs):
            return func(*args, **kwargs)

        return lambda *args, **kwargs: inner(
            time.time() // seconds_to_live, *args, **kwargs
        )

    return wrapper


def check_tools_available(tools: list[str]):
    return all(shutil.which(tool) is not None for tool in tools)


def copy_text(text: str) -> bool:
    try:
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)
        clipboard.store()
        logger.info("Text successfully copied to clipboard")
        return True
    except Exception as e:
        logger.error(f"Clipboard error: {e}")
        return False

def copy_image(image_path: str) -> bool:
    try:
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        image = GdkPixbuf.Pixbuf.new_from_file(image_path)
        clipboard.set_image(image)
        clipboard.store()
        logger.info("Image successfully copied to clipboard")
        return True
    except Exception as e:
        logger.error(f"Clipboard error: {e}")
        return False
