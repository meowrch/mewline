import datetime
import shutil
import time
from functools import lru_cache

import gi
import psutil
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gtk
from loguru import logger

gi.require_version("Gtk", "3.0")


# Function to escape the markup
def parse_markup(text):
    return text


# Function to format time in hours and minutes
def format_time(secs: int):
    mm, _ = divmod(secs, 60)
    hh, mm = divmod(mm, 60)
    return f"{hh} h {mm} min"


# Function to get the system uptime
def uptime():
    boot_time = psutil.boot_time()
    now = datetime.datetime.now()

    diff = now.timestamp() - boot_time

    # Convert the difference in seconds to hours and minutes
    hours, remainder = divmod(diff, 3600)
    minutes, _ = divmod(remainder, 60)

    return f"{int(hours):02}:{int(minutes):02}"


# Function to check if an icon exists, otherwise use a fallback icon
def check_icon_exists(icon_name: str, fallback_icon: str) -> str:
    if Gtk.IconTheme.get_default().has_icon(icon_name):
        return icon_name
    return fallback_icon


# Function to check if an executable exists
def executable_exists(executable_name):
    executable_path = shutil.which(executable_name)
    return bool(executable_path)


# Function to get the percentage of a value
def convert_to_percent(
    current: int | float, max: int | float, is_int=True
) -> int | float:
    if is_int:
        return int((current / max) * 100)
    else:
        return (current / max) * 100


# Function to unique list
def unique_list(lst) -> list:
    return list(set(lst))


def ttl_lru_cache(seconds_to_live: int, maxsize: int = 128):
    def wrapper(func):
        @lru_cache(maxsize)
        def inner(_, *args, **kwargs):
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
