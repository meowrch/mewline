from fabric import Application
from fabric.widgets.box import Box
from fabric.widgets.box import Box as FabricBox
from fabric.widgets.button import Button as FabricButton
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.centerbox import CenterBox as FabricCenterBox
from fabric.widgets.image import Image as FabricImage
from fabric.widgets.revealer import Revealer
from fabric.widgets.stack import Stack
from fabric.widgets.stack import Stack as FabricStack
from fabric.widgets.wayland import WaylandWindow as Window
from gi.repository import Gtk

from mewline.widgets.dynamic_island.app_launcher import AppLauncher
from mewline.widgets.dynamic_island.base import BaseDiWidget
from mewline.widgets.dynamic_island.bluetooth import BluetoothConnections
from mewline.widgets.dynamic_island.clipboard import Clipboard
from mewline.widgets.dynamic_island.compact import Compact
from mewline.widgets.dynamic_island.date_notification import DateNotificationMenu
from mewline.widgets.dynamic_island.emoji import EmojiPicker
from mewline.widgets.dynamic_island.network import NetworkConnections
from mewline.widgets.dynamic_island.notifications import NotificationContainer
from mewline.widgets.dynamic_island.pawlette_themes import PawletteThemes
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
            visible=False,
            all_visible=False,
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
        self.pawlette_themes = PawletteThemes()

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
            "pawlette-themes": self.pawlette_themes,
        }
        self.current_widget: str | None = None

        self.stack = Stack(
            name="dynamic-island-content",
            v_expand=True,
            h_expand=True,
            transition_type="crossfade",
            transition_duration=50,
            children=[*self.widgets.values()],
        )

        # Inline notification area shown below the current widget when DI is open
        self.inline_notification_container = Box(
            name="inline-notification-container",
            orientation="v",
            visible=False,
        )

        # Inline carousel: stack + navigation (dots + prev/next)
        self._inline_items: list[Box] = []
        self._inline_index: int = 0
        self.inline_stack = FabricStack(
            name="inline-notification-stack",
            transition_type="slide-left-right",
            transition_duration=200,
            v_expand=True,
            h_expand=True,
        )
        self.inline_dots = Box(
            name="inline-dots",
            orientation="h",
            spacing=6,
            h_align="center",
            v_align="end",
        )
        self.inline_prev_btn = FabricButton(
            name="inline-nav-button",
            v_align="center",
            child=FabricImage(icon_name="go-previous-symbolic", icon_size=12),
            on_clicked=lambda *_: self._inline_prev(),
        )
        self.inline_next_btn = FabricButton(
            name="inline-nav-button",
            v_align="center",
            child=FabricImage(icon_name="go-next-symbolic", icon_size=12),
            on_clicked=lambda *_: self._inline_next(),
        )
        # Close button at capsule corner (top-right of capsule)
        self.inline_close_btn = FabricButton(
            name="inline-close-button",
            v_align="start",
            h_align="end",
            child=FabricImage(icon_name="window-close-symbolic", icon_size=16),
            on_clicked=lambda *_: self._inline_close_current(),
        )

        # Center section of capsule: content expands, dots anchored at bottom
        self.inline_capsule_center = Box(
            name="inline-capsule-center",
            orientation="v",
            v_expand=True,
            h_expand=True,
            children=[
                Box(v_expand=True, h_expand=True, children=[self.inline_stack]),
                self.inline_dots,
            ],
        )

        # Right side container: three blocks
        # (close at top, arrow centered, bottom spacer expands)
        self.inline_next_btn.set_halign(Gtk.Align.CENTER)
        self.inline_next_btn.set_valign(Gtk.Align.CENTER)
        self.inline_capsule_right = FabricCenterBox(
            orientation="v",
            start_children=self.inline_close_btn,
            center_children=self.inline_next_btn,
            end_children=Box(v_expand=True),
            v_expand=True,
            h_expand=False,
        )

        self.inline_capsule = FabricCenterBox(
            name="inline-capsule",
            start_children=self.inline_prev_btn,
            center_children=self.inline_capsule_center,
            end_children=self.inline_capsule_right,
            v_expand=True,
            h_expand=True,
        )

        self.inline_notification_container.children = [self.inline_capsule]

        self.inline_notification_revealer = Revealer(
            name="inline-notification-revealer",
            transition_type="slide-down",
            transition_duration=200,
            reveal_child=False,
            child=self.inline_notification_container,
            h_expand=False,
            h_align="center",
        )

        # Root column holds the island box and (optionally)
        # the inline notifications BELOW the island
        # This ensures inline notifications
        # do NOT affect the size/shape of the island itself
        self.di_root_column = Box(
            name="dynamic-island-root-column",
            orientation="v",
            v_expand=False,
            h_expand=True,
            children=[],
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

        self.di_root_column.children = [self.di_box, self.inline_notification_revealer]

        ##==> Show the dynamic island
        ######################################
        self.add(self.di_root_column)
        self.show()

    def _inline_prev(self):
        if not self._inline_items:
            return
        if self._inline_index > 0:
            self._inline_index -= 1
        self.inline_stack.set_visible_child(self._inline_items[self._inline_index])
        self._update_inline_nav()

    def _inline_next(self):
        if not self._inline_items:
            return
        if self._inline_index < len(self._inline_items) - 1:
            self._inline_index += 1
        self.inline_stack.set_visible_child(self._inline_items[self._inline_index])
        self._update_inline_nav()

    def _update_inline_nav(self):
        # Rebuild dots reflecting current count and index
        try:
            for child in list(self.inline_dots.get_children()):
                self.inline_dots.remove(child)
                child.destroy()
        except Exception: ...

        for i in range(len(self._inline_items)):
            dot_shape = FabricBox(name="inline-dot-shape")
            dot = FabricButton(
                name="inline-dot",
                on_clicked=(lambda _w, idx=i: self._inline_go_to(idx)),
                child=dot_shape,
            )
            if i == self._inline_index:
                dot.add_style_class("active")
            self.inline_dots.add(dot)
        # Toggle nav visibility (prev/next) and dots
        show_nav = len(self._inline_items) > 1
        self.inline_prev_btn.set_visible(show_nav)
        self.inline_next_btn.set_visible(show_nav)
        self.inline_dots.set_visible(show_nav)

    def _inline_go_to(self, idx: int):
        if 0 <= idx < len(self._inline_items):
            self._inline_index = idx
            self.inline_stack.set_visible_child(self._inline_items[self._inline_index])
            self._update_inline_nav()

    def _inline_close_current(self):
        if not self._inline_items:
            return
        current = self._inline_items[self._inline_index]
        try:
            # Attempt to signal close on the underlying notification
            if hasattr(current, "notification"):
                current.notification.close("dismissed-by-user")
            else:
                # Fallback: remove from carousel
                self.remove_inline_notification(current)
        except Exception:
            self.remove_inline_notification(current)

    def _hide_internal_close_button(self, container: Box):
        try:
            # Recursively search for button named "notify-close-button" and hide it
            def hide_in(widget):
                try:
                    if (
                        hasattr(widget, "get_name")
                        and widget.get_name() == "notify-close-button"
                    ):
                        widget.set_visible(False)
                        return True
                except Exception: ...
                try:
                    for child in widget.get_children():
                        if hide_in(child):
                            return True
                except Exception: ...

                return False

            hide_in(container)
        except Exception: ...

    def show_inline_notification(self, notif_box: Box) -> None:
        """Add notification to inline carousel and show it."""
        try:
            name = f"notif-{len(self._inline_items)}"
            self.inline_stack.add_named(notif_box, name)
            self._inline_items.append(notif_box)
            self._inline_index = len(self._inline_items) - 1
            # Hide internal close button of the card (we show capsule close instead)
            self._hide_internal_close_button(notif_box)
            self.inline_stack.set_visible_child(notif_box)
            self._update_inline_nav()
            self.inline_notification_container.set_visible(True)
            self.inline_notification_revealer.set_reveal_child(True)
        except Exception:
            self.inline_notification_container.set_visible(True)
            self.inline_notification_revealer.set_reveal_child(True)
            self.inline_notification_revealer.set_reveal_child(True)

    def remove_inline_notification(self, notif_box: Box) -> None:
        # Remove from our carousel tracking and stack
        try:
            if notif_box in self._inline_items:
                idx = self._inline_items.index(notif_box)
                self._inline_items.pop(idx)
                if notif_box.get_parent() == self.inline_stack:
                    self.inline_stack.remove(notif_box)
                # Adjust current index
                if self._inline_items:
                    self._inline_index = min(idx, len(self._inline_items) - 1)
                    self.inline_stack.set_visible_child(
                        self._inline_items[self._inline_index]
                    )
                else:
                    self._inline_index = 0
        except Exception: ...

        self._update_inline_nav()

        if not self._inline_items:
            self.hide_inline_notifications()

    def hide_inline_notifications(self) -> None:
        self.inline_notification_revealer.set_reveal_child(False)
        self.inline_notification_container.set_visible(False)
        # Clear carousel
        try:
            for child in list(self.inline_stack.get_children()):
                self.inline_stack.remove(child)
                child.destroy()
        except Exception: ...
        self._inline_items.clear()
        self._inline_index = 0
        self._update_inline_nav()

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
        # Hide and clear inline notifications when closing DI
        self.hide_inline_notifications()

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

        # Sync inline container styling with current widget to mirror width constraints
        for style in self.widgets:
            self.inline_notification_container.remove_style_class(style)

        self.inline_notification_container.add_style_class(widget)

        self.call_module_method_if_exists(
            self.widgets[self.current_widget], "open_widget_from_di"
        )

        if widget == "notification":
            self.set_keyboard_mode("none")
