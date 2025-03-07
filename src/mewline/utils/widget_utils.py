from typing import Literal

import gi
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from fabric.widgets.scale import ScaleMark
from gi.repository import Gdk
from gi.repository import GLib

from mewline import constants as cnst
from mewline.shared.scale import AnimatedScale

gi.require_version("Gtk", "3.0")


# Function to setup cursor hover
def setup_cursor_hover(
    button,
    cursor_name: Literal["pointer", "crosshair", "grab"] = "pointer",
):
    display = Gdk.Display.get_default()

    def on_enter_notify_event(widget, _):
        cursor = Gdk.Cursor.new_from_name(display, cursor_name)
        widget.get_window().set_cursor(cursor)

    def on_leave_notify_event(widget, _):
        cursor = Gdk.Cursor.new_from_name(display, "default")
        widget.get_window().set_cursor(cursor)

    button.connect("enter-notify-event", on_enter_notify_event)
    button.connect("leave-notify-event", on_leave_notify_event)


def get_icon(app_icon, size=25) -> Image:
    icon_size = size - 5
    try:
        match app_icon:
            case str(x) if "file://" in x:
                return Image(
                    name="app-icon",
                    image_file=app_icon[7:],
                    size=size,
                )
            case str(x) if len(x) > 0 and x[0] == "/":
                return Image(
                    name="app-icon",
                    image_file=app_icon,
                    size=size,
                )
            case _:
                return Image(
                    name="app-icon",
                    icon_name=app_icon if app_icon else "dialog-information-symbolic",
                    icon_size=icon_size,
                )
    except GLib.GError:
        return Image(
            name="app-icon",
            icon_name="dialog-information-symbolic",
            icon_size=icon_size,
        )


def text_icon(icon: str, size: str = "16px", **kwargs):
    label_props = {
        "label": str(icon),  # Directly use the provided icon name
        "name": "nerd-icon",
        "style": f"font-size: {size}; ",
        "h_align": "center",  # Align horizontally
        "v_align": "center",  # Align vertically
    }

    label_props.update(kwargs)
    return Label(**label_props)


def create_scale(
    marks=None,
    value=70,
    min_value=0,
    max_value=100,
    duration=0.8,
    increments=(1, 1),
    orientation="h",
    h_expand=True,
    h_align="center",
    style_classes="",
) -> AnimatedScale:
    if marks is None:
        marks = (ScaleMark(value=i) for i in range(1, 100, 10))

    return AnimatedScale(
        marks=marks,
        value=value,
        duration=duration,
        min_value=min_value,
        max_value=max_value,
        increments=increments,
        orientation=orientation,
        h_expand=h_expand,
        h_align=h_align,
        style_classes=style_classes,
    )



def get_audio_icon(volume: int, is_muted: bool) -> str:
        if is_muted:
            return cnst.icons["volume"]["muted"]

        # Define volume ranges and their corresponding values
        volume_levels = {
            (0, 0): cnst.icons["volume"]["low"],
            (1, 31): cnst.icons["volume"]["low"],
            (32, 65): cnst.icons["volume"]["medium"],
            (66, 100): cnst.icons["volume"]["high"],
        }

        for (min_volume, max_volume), icon in volume_levels.items():
            if min_volume <= volume <= max_volume:
                return icon

        # If the volume exceeds 100
        return cnst.icons["volume"]["overamplified"]


def get_brightness_icon(level: int) -> str:
    if level <= 0:
        return cnst.icons["brightness"]["off"]
    elif level > 0 and level < 32:
        return cnst.icons["brightness"]["low"]
    elif level > 32 and level < 66:
        return cnst.icons["brightness"]["medium"]
    else:
        return cnst.icons["brightness"]["high"]
