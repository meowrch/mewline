"""Status bar implementations for different window managers."""

import cairo
from fabric.widgets.box import Box
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.wayland import WaylandWindow
from gi.repository import Gdk
from gi.repository import Gtk
from loguru import logger

try:
    from Xlib import X as XServer
    from Xlib.display import Display as XDisplay

    XLIB_AVAILABLE = True
except ImportError:
    XLIB_AVAILABLE = False
    logger.warning("Xlib not available, bspwm support will be limited")

from mewline.utils.hyprland_monitors import HyprlandMonitors
from mewline.widgets.battery import Battery
from mewline.widgets.bluetooth import Bluetooth
from mewline.widgets.combined_controls import CombinedControlsButton
from mewline.widgets.datetime import DateTimeWidget
from mewline.widgets.language import LanguageWidget
from mewline.widgets.network_status import NetworkStatus
from mewline.widgets.ocr import OCRWidget
from mewline.widgets.power import PowerButton
from mewline.widgets.system_tray import SystemTray
from mewline.widgets.workspaces import HyprlandWorkSpacesWidget


class StatusBarBase:
    """Base class for status bar with common widget layout."""

    def __init__(self, **kwargs):
        self.combined_controls = CombinedControlsButton()
        self.osd_widget = None

    def create_layout(self) -> CenterBox:
        """Create the status bar layout.

        Returns:
            CenterBox: The layout container with widgets.
        """
        return CenterBox(
            name="panel-inner",
            start_children=Box(
                spacing=4,
                orientation="h",
                children=[SystemTray(), HyprlandWorkSpacesWidget()],
            ),
            center_children=Box(
                spacing=4,
                orientation="h",
                children=None,
            ),
            end_children=Box(
                spacing=4,
                orientation="h",
                children=[
                    OCRWidget(),
                    Battery(),
                    self.combined_controls,
                    LanguageWidget(),
                    DateTimeWidget(),
                    Bluetooth(),
                    NetworkStatus(),
                    PowerButton(),
                ],
            ),
        )

    def set_osd_widget(self, osd_widget):
        """Set OSD widget reference for combined controls.

        Args:
            osd_widget: The OSD widget instance.
        """
        self.osd_widget = osd_widget
        if hasattr(self, "combined_controls"):
            self.combined_controls.set_osd_widget(osd_widget)


class WaylandStatusBar(WaylandWindow, StatusBarBase):
    """Status bar for Wayland (Hyprland)."""

    def __init__(self, **kwargs):
        StatusBarBase.__init__(self, **kwargs)
        box = self.create_layout()

        WaylandWindow.__init__(
            self,
            name="panel",
            layer="top",
            anchor="left top right",
            pass_through=False,
            monitor=HyprlandMonitors().get_current_gdk_monitor_id(),
            exclusivity="auto",
            visible=True,
            all_visible=False,
            child=box,
            **kwargs,
        )
        logger.info("Initialized WaylandStatusBar")


class BspwmStatusBar(Gtk.Window, StatusBarBase):
    """Status bar for bspwm (X11) with transparency and STRUT support."""

    BAR_HEIGHT = 40

    def __init__(self, **kwargs) -> None:
        StatusBarBase.__init__(self, **kwargs)

        if not XLIB_AVAILABLE:
            logger.error("Xlib is not available, cannot create bspwm status bar")
            raise ImportError("Xlib is required for bspwm support")

        # Get RGBA visual before creating window
        screen = Gdk.Screen.get_default()
        visual = screen.get_rgba_visual()

        Gtk.Window.__init__(self, type=Gtk.WindowType.TOPLEVEL)

        # Set visual and app_paintable immediately
        if visual is not None:
            self.set_visual(visual)
        else:
            logger.warning("RGBA visual not available, transparency may not work")

        self.set_app_paintable(True)

        # Connect draw handler for transparency
        self.connect("screen-changed", self._on_screen_changed)
        self.connect("draw", self._on_draw)

        # Window properties
        self.set_title("mewline-bspwm")
        self.set_name("panel")
        self.set_decorated(False)
        self.set_resizable(True)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_keep_above(True)
        self.stick()

        # Get monitor geometry
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() if display else None
        if monitor is None and display is not None:
            monitor = display.get_monitor(0)

        if monitor is not None:
            geometry = monitor.get_geometry()
            self.set_default_size(geometry.width, self.BAR_HEIGHT)
            self.move(0, 0)
            screen_width = geometry.width
            logger.info(
                f"Setting bar size to {geometry.width}x{self.BAR_HEIGHT} at position (0, 0)"
            )
        else:
            screen_width = 1920
            self.set_default_size(screen_width, self.BAR_HEIGHT)
            self.move(0, 0)
            logger.warning(
                f"Could not get monitor geometry, using default width {screen_width}"
            )

        # Add widgets
        box = self.create_layout()
        box.set_hexpand(True)
        self.add(box)

        self.show_all()

        # Apply X11 STRUT properties to reserve space
        self._apply_struts(screen_width)
        logger.info("Initialized BspwmStatusBar with X11 STRUT support")

    def _on_screen_changed(self, widget, old_screen):
        """Update visual when screen changes.

        Args:
            widget: The widget that changed screens.
            old_screen: The previous screen.
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

    def _apply_struts(self, screen_width: int):
        """Apply X11 STRUT properties to reserve space at top of screen.

        Args:
            screen_width: The width of the screen in pixels.
        """
        if not XLIB_AVAILABLE:
            logger.warning("Xlib not available, cannot apply STRUT properties")
            return

        gdk_window = self.get_window()
        if gdk_window is None:
            logger.warning("GDK window not available, cannot apply STRUT properties")
            return

        try:
            xid = gdk_window.get_xid()  # type: ignore[attr-defined]
        except Exception as e:
            logger.error(f"Could not get XID from GDK window: {e}")
            return

        try:
            xdisplay = XDisplay()
            xwindow = xdisplay.create_resource_object("window", xid)
        except Exception as e:
            logger.error(f"Could not create X display/window: {e}")
            return

        # Set _NET_WM_STRUT for simple reservation
        try:
            xwindow.change_property(
                xdisplay.intern_atom("_NET_WM_STRUT"),
                xdisplay.intern_atom("CARDINAL"),
                32,
                [0, 0, self.BAR_HEIGHT, 0],
                XServer.PropModeReplace,
            )
            logger.debug(f"Set _NET_WM_STRUT: top={self.BAR_HEIGHT}")
        except Exception as e:
            logger.error(f"Could not set _NET_WM_STRUT: {e}")

        # Set _NET_WM_STRUT_PARTIAL for more precise reservation
        try:
            xwindow.change_property(
                xdisplay.intern_atom("_NET_WM_STRUT_PARTIAL"),
                xdisplay.intern_atom("CARDINAL"),
                32,
                [
                    0,  # left
                    0,  # right
                    self.BAR_HEIGHT,  # top
                    0,  # bottom
                    0,  # left_start_y
                    0,  # left_end_y
                    0,  # right_start_y
                    0,  # right_end_y
                    0,  # top_start_x
                    screen_width,  # top_end_x
                    0,  # bottom_start_x
                    0,  # bottom_end_x
                ],
                XServer.PropModeReplace,
            )
            logger.debug(
                f"Set _NET_WM_STRUT_PARTIAL: top={self.BAR_HEIGHT}, width=0-{screen_width}"
            )
        except Exception as e:
            logger.error(f"Could not set _NET_WM_STRUT_PARTIAL: {e}")

        try:
            xdisplay.flush()
            logger.info("Successfully applied X11 STRUT properties")
        except Exception as e:
            logger.error(f"Could not flush X display: {e}")
