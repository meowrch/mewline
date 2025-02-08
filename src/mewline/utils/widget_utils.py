from typing import Literal

import gi
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from gi.repository import Gdk
from gi.repository import GLib

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


def text_icon(icon: str, size: str = "16px", props=None):
    label_props = {
        "label": str(icon),  # Directly use the provided icon name
        "name": "nerd-icon",
        "style": f"font-size: {size}; ",
        "h_align": "center",  # Align horizontally
        "v_align": "center",  # Align vertically
    }

    if props:
        label_props.update(props)

    return Label(**label_props)
