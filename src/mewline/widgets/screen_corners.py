import cairo
from fabric.widgets.box import Box
from fabric.widgets.shapes import Corner
from fabric.widgets.wayland import WaylandWindow
from gi.repository import Gdk
from gi.repository import Gtk
from loguru import logger

from mewline.utils.window_manager import WindowManagerContext


class MyCorner(Box):
    """A container for a corner widget."""

    def __init__(self, corner):
        super().__init__(
            name="corner-container",
            children=Corner(
                name="corner",
                orientation=corner,
                size=20,
            ),
        )


class WaylandScreenCorners(WaylandWindow):
    """Screen corners widget for Wayland (Hyprland)."""

    def __init__(self):
        all_corners = Box(
            name="all-corners",
            orientation="v",
            h_expand=True,
            v_expand=True,
            h_align="fill",
            v_align="fill",
            children=[
                Box(
                    name="top-corners",
                    orientation="h",
                    h_align="fill",
                    children=[
                        MyCorner("top-left"),
                        Box(h_expand=True),
                        MyCorner("top-right"),
                    ],
                ),
                Box(v_expand=True),
                Box(
                    name="bottom-corners",
                    orientation="h",
                    h_align="fill",
                    children=[
                        MyCorner("bottom-left"),
                        Box(h_expand=True),
                        MyCorner("bottom-right"),
                    ],
                ),
            ],
        )

        super().__init__(
            name="corners",
            layer="background",  # Behind all windows
            anchor="top bottom left right",  # Full screen
            pass_through=True,  # Don't intercept mouse clicks
            keyboard_mode="none",  # Don't take keyboard focus
            exclusivity="normal",
            visible=False,
            all_visible=False,
            child=all_corners,
        )

        self.show_all()
        logger.info("Initialized WaylandScreenCorners")


class X11ScreenCorners(Gtk.Window):
    """Screen corners widget for X11 (bspwm) with transparency support."""

    def __init__(self):
        # Get RGBA visual before creating window for transparency
        screen = Gdk.Screen.get_default()
        visual = screen.get_rgba_visual()

        super().__init__(type=Gtk.WindowType.TOPLEVEL)

        # Set visual and app_paintable immediately for transparency
        if visual is not None:
            self.set_visual(visual)
        else:
            logger.warning("RGBA visual not available, transparency may not work")

        self.set_app_paintable(True)

        # Connect draw handler for transparency
        self.connect("screen-changed", self._on_screen_changed)
        self.connect("draw", self._on_draw)

        # Window properties - DESKTOP type stays behind all windows
        self.set_title("mewline-corners")
        self.set_name("corners")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_type_hint(Gdk.WindowTypeHint.DESKTOP)  # Desktop type is behind normal windows
        self.set_accept_focus(False)  # Don't take focus
        self.set_keep_below(True)  # Stay below all windows
        self.stick()  # Show on all workspaces

        # Get monitor geometry to set full screen size
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() if display else None
        if monitor is None and display is not None:
            monitor = display.get_monitor(0)

        if monitor is not None:
            geometry = monitor.get_geometry()
            screen_width = geometry.width
            screen_height = geometry.height
            logger.info(f"Setting corners window to full screen: {screen_width}x{screen_height}")
        else:
            # Fallback to common resolution
            screen_width = 1920
            screen_height = 1080
            logger.warning(f"Could not get monitor geometry, using default: {screen_width}x{screen_height}")

        # Set window to full screen size
        self.set_default_size(screen_width, screen_height)
        self.move(0, 0)

        # Create corners layout
        all_corners = Box(
            name="all-corners",
            orientation="v",
            h_expand=True,
            v_expand=True,
            h_align="fill",
            v_align="fill",
            children=[
                Box(
                    name="top-corners",
                    orientation="h",
                    h_align="fill",
                    children=[
                        MyCorner("top-left"),
                        Box(h_expand=True),
                        MyCorner("top-right"),
                    ],
                ),
                Box(v_expand=True),
                Box(
                    name="bottom-corners",
                    orientation="h",
                    h_align="fill",
                    children=[
                        MyCorner("bottom-left"),
                        Box(h_expand=True),
                        MyCorner("bottom-right"),
                    ],
                ),
            ],
        )

        # Ensure the box expands to fill the window
        all_corners.set_hexpand(True)
        all_corners.set_vexpand(True)

        self.add(all_corners)
        self.show_all()
        logger.info("Initialized X11ScreenCorners with transparency support")

    def _on_screen_changed(self, _widget, _old_screen):
        """Update visual when screen changes.

        Args:
            _widget: The widget that changed screens.
            _old_screen: The previous screen.
        """
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)
            logger.debug("Updated RGBA visual on screen change")

    def _on_draw(self, widget, context):
        """Draw handler for transparency.

        Args:
            widget: The widget being drawn.
            context: The Cairo context.

        Returns:
            bool: False to allow further processing.
        """
        # Clear with transparent background
        context.set_source_rgba(0, 0, 0, 0)
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        context.set_operator(cairo.OPERATOR_OVER)
        return False


def ScreenCorners():
    """Factory function to create appropriate ScreenCorners implementation.

    Returns:
        WaylandScreenCorners or X11ScreenCorners based on current window manager.
    """
    if WindowManagerContext.is_wayland():
        logger.info("Creating WaylandScreenCorners")
        return WaylandScreenCorners()
    else:
        logger.info("Creating X11ScreenCorners for bspwm")
        return X11ScreenCorners()
