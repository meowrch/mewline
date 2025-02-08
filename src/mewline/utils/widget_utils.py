from typing import Literal

import gi
from fabric.widgets.label import Label
from gi.repository import Gdk

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
