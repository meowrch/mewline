from __future__ import annotations

import contextlib
from typing import ClassVar

import cairo
from fabric.widgets.box import Box
from fabric.widgets.wayland import WaylandWindow
from fabric.widgets.widget import Widget
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gtk
from loguru import logger

from mewline.utils.window_manager import WindowManagerContext


class WaylandPopoverManager:
    """Singleton manager to handle shared resources for Wayland popovers."""

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
            margin="-50px 0px 0px 0px",
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
            keyboard_mode="on-demand",
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


class X11PopoverManager:
    """Singleton manager to handle shared resources for X11 popovers."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.active_popover = None
        self.available_windows = []

    def get_popover_window(self):
        if self.available_windows:
            return self.available_windows.pop()

        # Get RGBA visual before creating window for transparency
        screen = Gdk.Screen.get_default()
        visual = screen.get_rgba_visual()

        window = Gtk.Window(type=Gtk.WindowType.POPUP)

        # Set visual and app_paintable for transparency
        if visual is not None:
            window.set_visual(visual)
        else:
            logger.warning("RGBA visual not available for popover, transparency may not work")

        window.set_app_paintable(True)
        window.connect("draw", self._on_draw)

        # Window properties for popup behavior
        window.set_name("popover-window")
        window.set_decorated(False)
        window.set_resizable(False)
        window.set_type_hint(Gdk.WindowTypeHint.POPUP_MENU)  # Popup menu behavior
        window.set_skip_taskbar_hint(True)  # Don't show in taskbar
        window.set_skip_pager_hint(True)  # Don't show in workspace switcher
        window.set_accept_focus(True)  # Can receive focus for keyboard input
        window.set_keep_above(True)  # Stay above other windows

        return window

    def _on_draw(self, widget, context):
        """Draw handler for transparency."""
        # Clear with transparent background
        context.set_source_rgba(0, 0, 0, 0)
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        context.set_operator(cairo.OPERATOR_OVER)
        return False

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


@GObject.Signal(
    flags=GObject.SignalFlags.RUN_LAST, return_type=GObject.TYPE_NONE, arg_types=()
)
def popover_opened(widget: Widget): ...


@GObject.Signal(
    flags=GObject.SignalFlags.RUN_LAST, return_type=GObject.TYPE_NONE, arg_types=()
)
def popover_closed(widget: Widget): ...


@GObject.type_register
class WaylandPopover(Widget):
    """Memory-efficient Wayland popover implementation."""

    __gsignals__: ClassVar = {
        "popover-opened": (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE, ()),
        "popover-closed": (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE, ()),
    }

    def __init__(self, content=None, point_to=None, gap: int = 4):
        super().__init__()
        self._content_factory = None
        self._point_to = point_to
        self._content_window = None
        self._content = content
        self._visible = False
        self._gap = gap
        self._manager = WaylandPopoverManager()

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
        monitor_at_window = screen.get_monitor_at_window(
            self._point_to.get_window()
        )
        monitor_geometry = monitor_at_window.get_geometry()

        # Center horizontally under the widget
        x = (
            widget_allocation.x
            + widget_allocation.width / 2
            - popover_size.width / 2
        )

        y = widget_allocation.y + self._gap

        # Horizontal bounds check
        if x <= 0:
            x = widget_allocation.x
        elif x + popover_size.width >= monitor_geometry.width:
            x = widget_allocation.x - popover_size.width + widget_allocation.width

        return [int(y), 0, 0, int(x)]

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
        try:
            self._content_window.connect("key-press-event", self._on_key_press)
            self._content_window.set_can_focus(True)
        except Exception:
            ...

        self._manager.activate_popover(self)
        self._content_window.show()

        with contextlib.suppress(Exception):
            self._content_window.grab_focus()

        self._visible = True

    def hide_popover(self):
        if not self._visible or not self._content_window:
            return False
        self._content_window.hide()
        self._manager.overlay.hide()
        self._visible = False
        self.emit("popover-closed")
        return False

    def _on_key_press(self, widget, event):
        try:
            if event.keyval == Gdk.KEY_Escape:
                self.hide_popover()
                return True
        except Exception:
            ...
        return False

    def close(self):
        return self.hide_popover()

    def get_visible(self) -> bool:
        return bool(self._visible)


@GObject.type_register
class X11Popover(Widget):
    """Memory-efficient X11 popover implementation."""

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
        self._manager = X11PopoverManager()

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

    def _calculate_position(self):
        """Calculate absolute screen position for X11 popup window."""
        # Get anchor widget's position on screen
        anchor_window = self._point_to.get_window()
        if not anchor_window:
            return (0, 0)

        # Get anchor widget allocation (relative to its parent)
        anchor_alloc = self._point_to.get_allocation()

        # Get anchor widget's absolute position on screen
        origin_x, origin_y = anchor_window.get_origin()[1:]

        # Calculate popup position
        x = origin_x + anchor_alloc.x
        y = origin_y + anchor_alloc.y + anchor_alloc.height + self._gap

        # Get popup window size
        popup_alloc = self._content_window.get_allocation()
        popup_width = popup_alloc.width if popup_alloc.width > 0 else 200

        # Center horizontally under anchor widget
        x += (anchor_alloc.width - popup_width) // 2

        # Get monitor geometry to keep popup on screen
        display = Gdk.Display.get_default()
        if display:
            monitor = display.get_monitor_at_window(anchor_window)
            if monitor:
                monitor_geom = monitor.get_geometry()
                # Keep within screen bounds
                if x < monitor_geom.x:
                    x = monitor_geom.x
                elif x + popup_width > monitor_geom.x + monitor_geom.width:
                    x = monitor_geom.x + monitor_geom.width - popup_width

        return (int(x), int(y))

    def set_position(self, position: tuple[int, int] | None = None):
        """Set popup window position."""
        if position is None:
            position = self._calculate_position()
        x, y = position
        self._content_window.move(x, y)
        return False

    def _on_content_ready(self, widget, event):
        """Called when content is drawn and sized."""
        self.set_position()

    def _create_popover(self):
        if self._content is None and self._content_factory is not None:
            self._content = self._content_factory()

        self._content_window = self._manager.get_popover_window()

        # Wrap content in styled box
        content_box = Box(style_classes="popover-content", children=self._content)
        self._content_window.add(content_box)

        # Connect signals
        self._content_window.connect("key-press-event", self._on_key_press)
        self._content.connect("draw", self._on_content_ready)

        # Position and show
        self._manager.activate_popover(self)
        self._content_window.show_all()

        # Calculate position after window is realized
        self.set_position()

        with contextlib.suppress(Exception):
            self._content_window.grab_focus()

        self._visible = True

    def hide_popover(self):
        if not self._visible or not self._content_window:
            return False
        self._content_window.hide()
        self._visible = False
        self.emit("popover-closed")
        return False

    def _on_key_press(self, widget, event):
        try:
            if event.keyval == Gdk.KEY_Escape:
                self.hide_popover()
                return True
        except Exception:
            ...
        return False

    def close(self):
        return self.hide_popover()

    def get_visible(self) -> bool:
        return bool(self._visible)


# Factory function for creating popovers with lazy WM detection
def Popover(content=None, point_to=None, gap: int = 2):
    """Create appropriate Popover implementation based on window manager.

    Args:
        content: The content widget to display in the popover.
        point_to: The widget to point/anchor the popover to.
        gap: Gap between anchor widget and popover in pixels.

    Returns:
        WaylandPopover or X11Popover instance based on current window manager.
    """
    if WindowManagerContext.is_wayland():
        return WaylandPopover(content=content, point_to=point_to, gap=gap)
    else:
        return X11Popover(content=content, point_to=point_to, gap=gap)
