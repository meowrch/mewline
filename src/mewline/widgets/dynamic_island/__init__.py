from fabric import Application
from fabric.widgets.box import Box
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.stack import Stack
from fabric.widgets.wayland import WaylandWindow as Window

from mewline.widgets.dynamic_island.app_launcher import AppLauncher
from mewline.widgets.dynamic_island.base import BaseDiWidget
from mewline.widgets.dynamic_island.bluetooth import BluetoothConnections
from mewline.widgets.dynamic_island.clipboard import Clipboard
from mewline.widgets.dynamic_island.compact import Compact
from mewline.widgets.dynamic_island.date_notification import DateNotificationMenu
from mewline.widgets.dynamic_island.emoji import EmojiPicker
from mewline.widgets.dynamic_island.network import NetworkConnections
from mewline.widgets.dynamic_island.notifications import NotificationContainer
from mewline.widgets.dynamic_island.power import PowerMenu
from mewline.widgets.dynamic_island.wallpapers import WallpaperSelector
from mewline.widgets.screen_corners import MyCorner


class DynamicIsland(Window):
    """A dynamic island window for the status bar."""

    def __init__(self):
        super().__init__(
            name="dynamic_island",
            layer="top",
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
        self.wallpapers = WallpaperSelector()
        self.emoji = EmojiPicker(self)
        self.clipboard = Clipboard(self)
        self.network = NetworkConnections()

        self.widgets: dict[str, type[BaseDiWidget]] = {
            "compact": self.compact,
            "notification": self.notification,
            "date-notification": self.date_notification,
            "power-menu": self.power_menu,
            "bluetooth": self.bluetooth,
            "app-launcher": self.app_launcher,
            "wallpapers": self.wallpapers,
            "emoji": self.emoji,
            "clipboard": self.clipboard,
            "network": self.network,
        }
        self.current_widget: str | None = None

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

    def call_module_method_if_exists(
        self, module: BaseDiWidget, method_name: str, **kwargs
    ) -> bool:
        if hasattr(module, method_name) and callable(getattr(module, method_name)):
            method = getattr(module, method_name)
            method(**kwargs)
            return True

        return False

    def close(self):
        self.set_keyboard_mode("none")

        if self.current_widget is not None:
            self.call_module_method_if_exists(
                self.widgets[self.current_widget], "close_widget_from_di"
            )

        if self.hidden:
            self.di_box.remove_style_class("hideshow")
            self.di_box.add_style_class("hidden")

        for widget in self.widgets.values():
            widget.remove_style_class("open")

        for style in self.widgets:
            self.stack.remove_style_class(style)

        self.current_widget = None
        self.stack.set_visible_child(self.compact)

    def open(self, widget: str = "date-notification") -> None:
        if widget == "compact":
            self.current_widget = None
            return

        if self.hidden:
            self.di_box.remove_style_class("hidden")
            self.di_box.add_style_class("hideshow")

        for style, w in self.widgets.items():
            self.stack.remove_style_class(style)
            w.remove_style_class("open")

        if widget not in self.widgets:
            widget = "date-notification"

        self.current_widget = widget

        if self.widgets[widget].focuse_kb:
            self.set_keyboard_mode("exclusive")

        self.stack.add_style_class(widget)
        self.stack.set_visible_child(self.widgets[widget])
        self.widgets[widget].add_style_class("open")
        self.call_module_method_if_exists(
            self.widgets[self.current_widget], "open_widget_from_di"
        )

        if widget == "notification":
            self.set_keyboard_mode("none")


    def toggle_hidden(self):
        self.hidden = not self.hidden
        if self.hidden:
            self.di_box.add_style_class("hidden")
        else:
            self.di_box.remove_style_class("hidden")
