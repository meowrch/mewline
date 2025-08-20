from __future__ import annotations

from typing import ClassVar

from fabric.widgets.box import Box
from fabric.widgets.wayland import WaylandWindow
from fabric.widgets.widget import Widget
from gi.repository import Gdk
from gi.repository import GObject


class PopoverManager:
    """Singleton manager to handle shared resources for popovers."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Shared overlay window for all popovers
        self.overlay = WaylandWindow(
            name="popover-overlay",
            style_classes="popover-overlay",
            anchor="left top right bottom",
            exclusivity="auto",
            layer="overlay",
            type="top-level",
            visible=False,
            all_visible=False,
            style="background-color: rgba(0,0,0,0.0);",
        )
        self.overlay.add(Box())
        self.active_popover = None
        self.available_windows = []
        self.overlay.connect("button-press-event", self._on_overlay_clicked)

    def _on_overlay_clicked(self, widget, event):
        if self.active_popover:
            self.active_popover.hide_popover()
        return True

    def get_popover_window(self):
        if self.available_windows:
            return self.available_windows.pop()
        window = WaylandWindow(
            type="popup",
            layer="overlay",
            name="popover-window",
            anchor="left top",
            visible=False,
            all_visible=False,
        )
        return window

    def return_popover_window(self, window):
        for child in window.get_children():
            window.remove(child)
        window.hide()
        if len(self.available_windows) < 5:
            self.available_windows.append(window)
        else:
            window.destroy()

    def activate_popover(self, popover):
        if self.active_popover and self.active_popover != popover:
            self.active_popover.hide_popover()
        self.active_popover = popover
        self.overlay.show()


@GObject.Signal(
    flags=GObject.SignalFlags.RUN_LAST, return_type=GObject.TYPE_NONE, arg_types=()
)
def popover_opened(widget: Widget): ...


@GObject.Signal(
    flags=GObject.SignalFlags.RUN_LAST, return_type=GObject.TYPE_NONE, arg_types=()
)
def popover_closed(widget: Widget): ...


@GObject.type_register
class Popover(Widget):
    """Memory-efficient popover implementation (ported from Tsumiki style)."""

    __gsignals__: ClassVar = {
        "popover-opened": (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE, ()),
        "popover-closed": (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE, ()),
    }

    def __init__(self, content=None, point_to=None, gap: int = 2):
        super().__init__()
        self._content_factory = None
        self._point_to = point_to
        self._content_window = None
        self._content = content
        self._visible = False
        self._gap = gap
        self._manager = PopoverManager()

    def set_pointing_to(self, widget):
        self._point_to = widget

    def set_content(self, content):
        self._content = content

    def open(self, *_):
        if not self._content_window:
            self._create_popover()
        else:
            self._manager.activate_popover(self)
            self._content_window.show()
            self._visible = True
        self.emit("popover-opened")

    def _calculate_margins(self):
        widget_allocation = self._point_to.get_allocation()
        popover_size = self._content_window.get_size()
        display = Gdk.Display.get_default()
        screen = display.get_default()
        monitor_at_window = screen.get_monitor_at_window(self._point_to.get_window())
        monitor_geometry = monitor_at_window.get_geometry()
        # Center under widget horizontally
        x = (
            widget_allocation.x
            + (widget_allocation.width / 2)
            - (popover_size.width / 2)
        )
        y = widget_allocation.y + widget_allocation.height + self._gap
        if x <= 0:
            x = widget_allocation.x
        elif x + popover_size.width >= monitor_geometry.width:
            x = widget_allocation.x - popover_size.width + widget_allocation.width
        return [y, 0, 0, int(x)]

    def set_position(self, position: tuple[int, int, int, int] | None = None):
        if position is None:
            self._content_window.set_margin(self._calculate_margins())
            return False
        self._content_window.set_margin(position)
        return False

    def _on_content_ready(self, widget, event):
        self.set_position()

    def _create_popover(self):
        if self._content is None and self._content_factory is not None:
            self._content = self._content_factory()
        self._content_window = self._manager.get_popover_window()
        self._content.connect("draw", self._on_content_ready)
        self._content_window.add(
            Box(style_classes="popover-content", children=self._content)
        )
        self._manager.activate_popover(self)
        self._content_window.show()
        self._visible = True

    def hide_popover(self):
        if not self._visible or not self._content_window:
            return False
        self._content_window.hide()
        self._manager.overlay.hide()
        self._visible = False
        self.emit("popover-closed")
        return False

    # Compatibility helpers
    def close(self):
        return self.hide_popover()

    def get_visible(self) -> bool:
        return bool(self._visible)
