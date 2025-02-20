from fabric import Application
from fabric.widgets.box import Box
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.stack import Stack
from fabric.widgets.wayland import WaylandWindow as Window

from mewline.widgets.dynamic_island.app_launcher import AppLauncher
from mewline.widgets.dynamic_island.base import BaseDiWidget
from mewline.widgets.dynamic_island.bluetooth import BluetoothConnections
from mewline.widgets.dynamic_island.compact import Compact
from mewline.widgets.dynamic_island.date_notification import DateNotificationMenu
from mewline.widgets.dynamic_island.notifications import NotificationContainer
from mewline.widgets.dynamic_island.power import PowerMenu
from mewline.widgets.screen_corners import MyCorner


class DynamicIsland(Window):
    """A dynamic island window for the status bar."""

    def __init__(self):
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

        self.hidden = False

        ##==> Defining the widgets
        #########################################
        self.compact = Compact(self)
        self.notification = NotificationContainer(self)
        self.date_notification = DateNotificationMenu()
        self.power_menu = PowerMenu(self)
        self.bluetooth = BluetoothConnections()
        self.app_launcher = AppLauncher(self)

        self.widgets: dict[str, type[BaseDiWidget]] = {
            "compact": self.compact,
            "notification": self.notification,
            "date_notification": self.date_notification,
            "power_menu": self.power_menu,
            "bluetooth": self.bluetooth,
            "app_launcher": self.app_launcher
        }
        self.stack = Stack(
            name="dynamic-island-content",
            v_expand=True,
            h_expand=True,
            transition_type="crossfade",
            transition_duration=250,
            children=[*self.widgets.values()],
        )

        ##==> Customizing the hotkeys
        ########################################################
        Application.action("dynamic-island-open")(self.open)
        Application.action("dynamic-island-close")(self.close)
        self.add_keybinding("Escape", lambda *_: self.close())

        self.di_box = CenterBox(
            name="dynamic-island-box",
            orientation="h",
            h_align="center",
            v_align="center",
            start_children=Box(
                children=[
                    Box(
                        name="dynamic-island-corner-left",
                        orientation="v",
                        children=[
                            MyCorner("top-right"),
                            Box(),
                        ],
                    )
                ]
            ),
            center_children=self.stack,
            end_children=Box(
                children=[
                    Box(
                        name="dynamic-island-corner-right",
                        orientation="v",
                        children=[
                            MyCorner("top-left"),
                            Box(),
                        ],
                    )
                ]
            ),
        )

        ##==> Show the dynamic island
        ######################################
        self.add(self.di_box)

    def close(self):
        self.set_keyboard_mode("none")

        if self.hidden:
            self.di_box.remove_style_class("hideshow")
            self.di_box.add_style_class("hidden")

        for widget in self.widgets.values():
            widget.remove_style_class("open")

        for style in self.widgets:
            self.stack.remove_style_class(style)

        self.stack.set_visible_child(self.compact)

    def open(self, widget: str = "date_notification"):
        if widget == "compact":
            return

        if self.hidden:
            self.di_box.remove_style_class("hidden")
            self.di_box.add_style_class("hideshow")

        for style, w in self.widgets.items():
            self.stack.remove_style_class(style)
            w.remove_style_class("open")

        if widget in self.widgets:
            if self.widgets[widget].focuse_kb:
                self.set_keyboard_mode("exclusive")

            self.stack.add_style_class(widget)
            self.stack.set_visible_child(self.widgets[widget])
            self.widgets[widget].add_style_class("open")

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
