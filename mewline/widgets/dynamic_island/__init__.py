import os

from fabric import Application
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.stack import Stack
from fabric.widgets.wayland import WaylandWindow as Window

from utils.widget_utils import setup_cursor_hover
from widgets.dynamic_island.notifications import NotificationContainer
from widgets.dynamic_island.power import PowerMenu
from widgets.screen_corners import MyCorner


class DynamicIsland(Window):
    """A dynamic island window for the status bar."""
    def __init__(self, **kwargs):
        super().__init__(
            name="dynamic_island",
            layer="overlay",
            anchor="top",
            margin="-41px 10px 10px 41px",
            keyboard_mode="none",
            exclusivity="normal",
            visible=True,
            all_visible=True,
        )

        self.power = PowerMenu(self)
        self.notification = NotificationContainer(self)

        compact_button = Button(
            name="compact-label",
            label=f"{os.getlogin()}@{os.uname().nodename}",
            on_clicked=lambda *_: self.open("power"),
        )
        setup_cursor_hover(compact_button)
        self.compact = CenterBox(
            name="dynamic-island-compact",
            v_expand=True,
            h_expand=True,
            center_children=[compact_button],
        )

        self.stack = Stack(
            name="dynamic-island-content",
            v_expand=True,
            h_expand=True,
            transition_type="crossfade",
            transition_duration=250,
            children=[
                self.compact,
                self.power,
                self.notification
            ],
        )

        self.corner_left = Box(
            name="dynamic-island-corner-left",
            orientation="v",
            children=[
                MyCorner("top-right"),
                Box(),
            ],
        )

        self.corner_right = Box(
            name="dynamic-island-corner-right",
            orientation="v",
            children=[
                MyCorner("top-left"),
                Box(),
            ],
        )

        self.di_box = CenterBox(
            name="dynamic-island-box",
            orientation="h",
            h_align="center",
            v_align="center",
            start_children=Box(children=[self.corner_left]),
            center_children=self.stack,
            end_children=Box(children=[self.corner_right]),
        )

        self.hidden = False

        self.add(self.di_box)
        self.show_all()

        ## Настраиваем хоткеи
        Application.action("dynamic-island-open")(self.open)
        self.add_keybinding("Escape", lambda *_: self.close())

    def close(self):
        self.set_keyboard_mode("none")

        if self.hidden:
            self.di_box.remove_style_class("hideshow")
            self.di_box.add_style_class("hidden")

        for widget in [self.power, self.notification]:
            widget.remove_style_class("open")

        for style in ["power", "notification"]:
            self.stack.remove_style_class(style)

        self.stack.set_visible_child(self.compact)

    def open(self, widget):
        self.set_keyboard_mode("exclusive")

        if self.hidden:
            self.di_box.remove_style_class("hidden")
            self.di_box.add_style_class("hideshow")

        widgets = {
            "power": self.power,
            "notification": self.notification
        }

        for style, w in widgets.items():
            self.stack.remove_style_class(style)
            w.remove_style_class("open")

        if widget in widgets:
            self.stack.add_style_class(widget)
            self.stack.set_visible_child(widgets[widget])
            widgets[widget].add_style_class("open")

            if widget == "notification":
                self.set_keyboard_mode("none")
        else:
            self.stack.set_visible_child(self.dashboard)

    def toggle_hidden(self):
        self.hidden = not self.hidden
        if self.hidden:
            self.di_box.add_style_class("hidden")
        else:
            self.di_box.remove_style_class("hidden")
