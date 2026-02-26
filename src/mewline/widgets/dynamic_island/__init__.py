import contextlib
import subprocess
from typing import ClassVar

import cairo
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
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from loguru import logger

from mewline.utils.window_manager import WindowManagerContext
from mewline.utils.window_manager import create_adaptive_window
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
from mewline.widgets.dynamic_island.workspaces import WorkspacesOverview
from mewline.widgets.screen_corners import MyCorner


class DynamicIsland:
    """A dynamic island window for the status bar.

    Works on both Wayland (Hyprland) and X11 (bspwm).
    This is a wrapper that creates and manages the actual window.
    """

    # Target dimensions for each widget state on X11
    # Matches min-width/min-height in island.scss
    TARGET_SIZES: ClassVar[dict[str, tuple[int, int]]] = {
        "compact": (256, 40),
        "notification": (300, 80),
        "date-notification": (500, 300),
        "power-menu": (320, 80),
        "bluetooth": (500, 300),
        "app-launcher": (480, 220),
        "wallpapers": (620, 420),
        "emoji": (574, 238),
        "clipboard": (500, 300),
        "network": (500, 300),
        "pawlette-themes": (620, 420),
        "workspaces": (980, 280),
    }

    def __init__(self):
        self.hidden = False

        # Stores the bspwm node ID that was focused just before DI stole input.
        # Used by _restore_x11_focus() to return focus to the exact window,
        # rather than relying on bspwm's 'last' history which can point to a
        # different desktop or a different window among several.
        self._focused_node_before_open: str | None = None

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
        self.workspaces_overview = WorkspacesOverview()

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
            "workspaces": self.workspaces_overview,
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
        # Animated dots revealer
        self.inline_dots_revealer = Revealer(
            transition_type="slide-down",
            transition_duration=200,
            reveal_child=True,
            child=self.inline_dots,
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

        # External urgency line for inline capsule (shown below dots)
        self.inline_urgency_line = Box(
            name="notification-urgency-line",
            visible=False,
            h_expand=True,
            h_align="fill",
            margin_bottom=6,
        )

        # Center section of capsule: content expands,
        # dots and urgency line anchored at bottom
        self.inline_capsule_center = Box(
            name="inline-capsule-center",
            orientation="v",
            v_expand=True,
            h_expand=True,
            spacing=16,
            children=[
                Box(v_expand=True, h_expand=True, children=[self.inline_stack]),
                Box(
                    orientation="v",
                    spacing=6,
                    children=[
                        self.inline_dots_revealer,
                        self.inline_urgency_line,
                    ],
                ),
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
        # Animated revealers for nav
        self.inline_right_revealer = Revealer(
            transition_type="slide-left",
            transition_duration=200,
            reveal_child=True,
            child=self.inline_capsule_right,
        )
        self.inline_prev_revealer = Revealer(
            transition_type="slide-right",
            transition_duration=200,
            reveal_child=True,
            child=self.inline_prev_btn,
        )

        self.inline_capsule = FabricCenterBox(
            name="inline-capsule",
            start_children=self.inline_prev_revealer,
            center_children=self.inline_capsule_center,
            end_children=self.inline_right_revealer,
            v_expand=True,
            h_expand=True,
        )

        # Simple single-notification container (no navigation)
        self.inline_simple_container = Box(
            name="inline-simple-notification",
            orientation="v",
            v_expand=True,
            h_expand=True,
        )

        # Add hover support for simple container too
        try:

            def _simple_pause(*_a):
                for item in self._inline_items:
                    if hasattr(item, "pause_timeout"):
                        item.pause_timeout()
                return False

            def _simple_resume(*_a):
                for item in self._inline_items:
                    if hasattr(item, "resume_timeout"):
                        item.resume_timeout()
                return False

            self.inline_simple_container.add_events(
                Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK
            )
            self.inline_simple_container.connect("enter-notify-event", _simple_pause)
            self.inline_simple_container.connect("leave-notify-event", _simple_resume)
        except Exception:
            ...

        # Pause all inline notification timeouts while hovering the capsule
        try:

            def _inline_pause(*_a):
                for item in self._inline_items:
                    if hasattr(item, "pause_timeout"):
                        item.pause_timeout()
                return False

            def _inline_resume(*_a):
                for item in self._inline_items:
                    if hasattr(item, "resume_timeout"):
                        item.resume_timeout()
                return False

            self.inline_capsule.add_events(
                Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK
            )
            self.inline_capsule.connect("enter-notify-event", _inline_pause)
            self.inline_capsule.connect("leave-notify-event", _inline_resume)
        except Exception:
            ...

        # Initially empty - will be set dynamically based on notification count
        self.inline_notification_container.children = []

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

        # Set up hover detection for the entire Dynamic Island
        # to pause notification timers
        self._setup_island_hover_detection()
        # Recursively hook pointer events for all island children
        self._hook_pointer_events_recursively(self.di_root_column)
        # Fallback pointer polling (silent) to ensure hover works across backends
        self._start_island_pointer_polling()

        # Create adaptive window that works on both Wayland and X11
        try:
            self.window = create_adaptive_window(
                name="dynamic_island",
                wayland_kwargs={
                    "layer": "top",
                    "anchor": "top",
                    "margin": "-41px 10px 10px 41px",
                    "keyboard_mode": "none",
                    "exclusivity": "normal",
                },
                x11_kwargs={
                    "type_hint": "notification",
                    "geometry": "top",
                },
                visible=False,
                all_visible=False,
                child=self.di_root_column,
            )
            logger.info("Created Dynamic Island window with adaptive window system")

            # For X11: set up window properly
            if WindowManagerContext.is_x11():
                self._setup_x11_window()

        except Exception as e:
            logger.error(f"Failed to create Dynamic Island window: {e}")
            raise

        # Add keybinding for escape - must be after window creation
        self._setup_keybindings()

        ##==> Show the dynamic island
        ######################################
        self.window.show()

    def _update_x11_constraints(self, widget_name: str):
        """Update window geometry hints for BSPWM/X11 to prevent unwanted expansion."""
        try:
            if not WindowManagerContext.is_x11():
                return

            # Get target dimensions from map, default to compact
            width, height = self.TARGET_SIZES.get(widget_name, (256, 40))

            # Create geometry struct
            geom = Gdk.Geometry()
            geom.min_width = width
            geom.min_height = height
            geom.max_width = width
            geom.max_height = height

            self.window.set_geometry_hints(
                None,
                geom,
                Gdk.WindowHints.MIN_SIZE | Gdk.WindowHints.MAX_SIZE,
            )

            self.window.resize(width, height)

            # Re-center the window since size changed
            GLib.idle_add(self._position_x11_window)

        except Exception as e:
            logger.warning(f"Failed to update X11 constraints: {e}")

    def _setup_keybindings(self):
        """Setup keyboard bindings for the window."""
        try:
            if hasattr(self.window, "add_keybinding"):
                # Wayland windows
                self.window.add_keybinding("Escape", lambda *_: self.close())
            else:
                # X11 windows: connect key-press-event directly.
                # This fires whenever the window has keyboard focus
                # (either via normal focus or after steal_input / steal_input_soft).
                def on_key_press(widget, event):
                    if event.keyval == Gdk.KEY_Escape:
                        self.close()
                        return True
                    return False

                self.window.connect("key-press-event", on_key_press)
        except Exception as e:
            logger.warning(f"Failed to setup keybindings: {e}")

    def _setup_x11_window(self):
        """Configure X11-specific window properties for bspwm."""
        try:
            self.window.set_decorated(False)
            self.window.set_keep_above(True)
            self.window.stick()
            self.window.set_resizable(True)

            # Allow the window to receive focus so key-press-event fires.
            # Actual focus stealing is done via steal_input_soft() / steal_input()
            # inside set_keyboard_mode(); here we just tell the WM the window CAN
            # be focused.
            self.window.set_accept_focus(True)

            self._update_x11_constraints("compact")

            # Enable transparency
            screen = self.window.get_screen()
            visual = screen.get_rgba_visual()
            if visual:
                self.window.set_visual(visual)
            self.window.set_app_paintable(True)
            self.window.connect("draw", self._on_x11_draw)

            self.window.connect("size-allocate", self._on_x11_size_allocate)
            GLib.idle_add(self._position_x11_window)

            logger.info("Configured Dynamic Island for X11/bspwm")
        except Exception as e:
            logger.error(f"Failed to setup X11 window: {e}")

    def _on_x11_draw(self, widget, context):
        """Draw handler for X11 transparency."""
        context.set_source_rgba(0, 0, 0, 0)
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        context.set_operator(cairo.OPERATOR_OVER)
        return False

    def _on_x11_size_allocate(self, widget, allocation):
        """Keep window centered horizontally when size changes."""
        if WindowManagerContext.is_x11():
            GLib.idle_add(self._position_x11_window)

    def _position_x11_window(self):
        """Position the X11 window at top center of screen."""
        try:
            display = Gdk.Display.get_default()
            if not display:
                return False

            # Get primary monitor geometry
            monitor = display.get_primary_monitor()
            if not monitor:
                monitor = display.get_monitor(0)

            if monitor:
                geometry = monitor.get_geometry()
                screen_width = geometry.width

                # Get window width
                window_width = self.window.get_allocated_width()

                # Calculate center position
                x = (screen_width - window_width) // 2
                y = 10  # Small margin from top

                self.window.move(x, y)
        except Exception as e:
            logger.error(f"Failed to position X11 window: {e}")

        return False

    def _get_focused_node_id(self) -> str | None:
        """Return the bspwm node ID that currently holds keyboard focus.

        Uses `bspc query -N -n focused` which returns the numeric XID of the
        focused node (e.g. '0x02400007').  This is different from bspwm's
        'last' selector, which tracks navigation history and may point to a
        node on a different desktop.
        """
        try:
            result = subprocess.run(
                ["bspc", "query", "-N", "-n", "focused"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if result.returncode == 0:
                node_id = result.stdout.strip()
                return node_id if node_id else None
        except Exception:
            ...
        return None

    def _restore_x11_focus(self):
        """Return X11 keyboard focus to the node that was focused when DI opened.

        Prefers the explicitly saved node ID over bspwm's 'last' selector so
        that focus returns to the exact window and desktop, even when the user
        was on an empty desktop or had multiple terminals open.
        """
        try:
            if self._focused_node_before_open:
                result = subprocess.run(
                    ["bspc", "node", self._focused_node_before_open, "--focus"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                if result.returncode == 0:
                    logger.debug(
                        f"[X11] Restored focus to node {self._focused_node_before_open}"
                    )
                    self._focused_node_before_open = None
                    return
                # Node no longer exists (window was closed while DI was open).
                # Clear the saved ID and fall through to the fallback.
                logger.debug(
                    f"[X11] Saved node {self._focused_node_before_open} gone, using fallback"
                )
                self._focused_node_before_open = None

            # Fallback: focus any node on the current desktop.
            subprocess.run(
                ["bspc", "node", "any.local", "--focus"],
                capture_output=True,
                timeout=1,
            )
        except Exception: ...

    def set_keyboard_mode(self, mode: str):
        """Set keyboard mode.

        On Wayland: delegates to WaylandWindow.set_keyboard_mode().
        On X11/bspwm:
            "exclusive" - steal_input_soft() puts X11 focus on the DI window;
                          steal_input() additionally does Gdk.keyboard_grab so
                          ALL key events are routed here even if another X window
                          nominally holds focus (needed for focuse_kb widgets).
            "none"      - unsteal_input() releases Gdk.keyboard_grab, then
                          _restore_x11_focus() hands focus back to the node
                          that was focused when DI opened.
        """
        if WindowManagerContext.is_x11():
            try:
                if mode == "exclusive":
                    # First: soft focus via XSetInputFocus (Xlib)
                    if hasattr(self.window, "steal_input_soft"):
                        self.window.steal_input_soft(can_release=True)
                        logger.debug("[X11] steal_input_soft() called")
                    # Second: hard keyboard grab so events arrive even when
                    # another window is focused by the WM
                    if hasattr(self.window, "steal_input"):
                        self.window.steal_input()
                        logger.debug("[X11] steal_input() (Gdk.keyboard_grab) called")
                else:
                    # Release keyboard grab if any
                    if hasattr(self.window, "unsteal_input"):
                        self.window.unsteal_input()
                        logger.debug("[X11] unsteal_input() called")
                    # Return focus to the window that had it before DI opened
                    self._restore_x11_focus()
            except Exception as e:
                logger.warning(f"[X11] set_keyboard_mode({mode!r}) failed: {e}")
            return

        # Wayland path
        if hasattr(self.window, "set_keyboard_mode"):
            self.window.set_keyboard_mode(mode)

    def set_visible(self, visible: bool):
        """Set window visibility."""
        self.window.set_visible(visible)

    def add_keybinding(self, key: str, callback):
        """Add keybinding if supported."""
        if hasattr(self.window, "add_keybinding"):
            self.window.add_keybinding(key, callback)

    def _inline_prev(self):
        if not self._inline_items:
            return
        if self._inline_index > 0:
            self._inline_index -= 1
        self.inline_stack.set_visible_child(self._inline_items[self._inline_index])
        self._update_inline_nav()
        self._update_inline_external_urgency_line()

    def _inline_next(self):
        if not self._inline_items:
            return
        if self._inline_index < len(self._inline_items) - 1:
            self._inline_index += 1
        self.inline_stack.set_visible_child(self._inline_items[self._inline_index])
        self._update_inline_nav()
        self._update_inline_external_urgency_line()

    def _switch_inline_container(self):
        """Switch between simple container (single notification) and capsule (multiple)."""  # noqa: W505
        try:
            # Clear current children
            for child in list(self.inline_notification_container.get_children()):
                self.inline_notification_container.remove(child)

            if len(self._inline_items) == 1:
                # Single notification: use simple container without navigation
                current_box = self._inline_items[0]

                # Remove from all possible parents first
                current_parent = current_box.get_parent()
                if current_parent == self.inline_stack:
                    self.inline_stack.remove(current_box)
                elif current_parent == self.inline_simple_container:
                    self.inline_simple_container.remove(current_box)

                # Clear simple container first, then add the notification
                for child in list(self.inline_simple_container.get_children()):
                    self.inline_simple_container.remove(child)
                self.inline_simple_container.add(current_box)
                self.inline_notification_container.add(self.inline_simple_container)

                # Show internal close button for single mode
                self._set_inline_internal_close_visibility(current_box, True)
                # Show internal urgency line for single mode
                self._set_inline_internal_urgency_visibility(current_box, True)

            elif len(self._inline_items) > 1:
                # Multiple notifications: use capsule with navigation

                # Ensure all items are in the stack, removing from other parents first
                for i, box in enumerate(self._inline_items):
                    current_parent = box.get_parent()
                    if current_parent != self.inline_stack:
                        # Remove from current parent first
                        if current_parent == self.inline_simple_container:
                            self.inline_simple_container.remove(box)
                        elif current_parent is not None:
                            with contextlib.suppress(Exception):
                                current_parent.remove(box)
                        # Add to stack
                        self.inline_stack.add_named(box, f"notif-{i}")
                    # Hide internal close buttons in multi mode
                    self._hide_internal_close_button(box)
                    # Hide internal urgency lines in multi mode
                    self._set_inline_internal_urgency_visibility(box, False)

                # Set current visible child
                if self._inline_items:
                    self.inline_stack.set_visible_child(
                        self._inline_items[self._inline_index]
                    )

                self.inline_notification_container.add(self.inline_capsule)

        except Exception as e:
            print(f"Error switching inline container: {e}")

    def _update_inline_nav(self):
        # First switch container based on count
        self._switch_inline_container()

        # Only update navigation if we're in multi mode (capsule)
        if len(self._inline_items) <= 1:
            return

        # Rebuild dots reflecting current count and index
        try:
            for child in list(self.inline_dots.get_children()):
                self.inline_dots.remove(child)
                child.destroy()
        except Exception:
            ...

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

        show_nav = len(self._inline_items) > 1
        # Animate via revealers
        with contextlib.suppress(Exception):
            # Prev arrow only when multiple
            self.inline_prev_revealer.set_reveal_child(show_nav)
            # Keep the right column (with the corner close button)
            # visible whenever there is at least one item
            self.inline_right_revealer.set_reveal_child(len(self._inline_items) > 0)
            # Show dots only when multiple
            self.inline_dots_revealer.set_reveal_child(show_nav)
            # Hide only the right arrow (next) when single;
            # keep the corner close button visible
            self.inline_next_btn.set_visible(show_nav)
        # Hide internal urgency lines for items in multi mode;
        # show external line only in multi
        self._toggle_inline_urgency_lines(show_nav)
        self._update_inline_external_urgency_line()

    def _inline_go_to(self, idx: int):
        if 0 <= idx < len(self._inline_items):
            self._inline_index = idx
            self.inline_stack.set_visible_child(self._inline_items[self._inline_index])
            self._update_inline_nav()
            self._update_inline_external_urgency_line()

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

            def hide_in(widget):
                try:
                    if (
                        hasattr(widget, "get_name")
                        and widget.get_name() == "notify-close-button"
                    ):
                        widget.set_visible(False)
                        return True
                except Exception:
                    ...
                try:
                    for child in widget.get_children():
                        if hide_in(child):
                            return True
                except Exception:
                    ...

                return False

            hide_in(container)
        except Exception:
            ...

    def _set_inline_internal_close_visibility(self, container: Box, visible: bool):
        try:

            def set_vis(widget):
                try:
                    if (
                        hasattr(widget, "get_name")
                        and widget.get_name() == "notify-close-button"
                    ):
                        widget.set_visible(visible)
                        return True
                except Exception:
                    ...
                try:
                    for child in widget.get_children():
                        if set_vis(child):
                            return True
                except Exception:
                    ...
                return False

            set_vis(container)
        except Exception:
            ...

    def _set_inline_internal_urgency_visibility(self, container: Box, visible: bool):
        try:

            def set_vis(widget):
                try:
                    if (
                        hasattr(widget, "get_name")
                        and widget.get_name() == "notification-urgency-line"
                    ):
                        widget.set_visible(visible)
                        return True
                except Exception:
                    ...
                try:
                    for child in widget.get_children():
                        if set_vis(child):
                            return True
                except Exception:
                    ...
                return False

            set_vis(container)
        except Exception:
            ...

    def _current_inline_view_box(self) -> Box | None:
        try:
            if not self._inline_items:
                return None
            return self._inline_items[self._inline_index]
        except Exception:
            return None

    def _toggle_inline_urgency_lines(self, multi: bool):
        # In capsule: always hide internal urgency lines; use external only in multi
        try:
            for item in self._inline_items:
                self._set_inline_internal_urgency_visibility(item, False)
        except Exception:
            ...
        with contextlib.suppress(Exception):
            self.inline_urgency_line.set_visible(
                False if not multi else self.inline_urgency_line.get_visible()
            )

    def _update_inline_external_urgency_line(self):
        # Update external urgency line for inline capsule.
        # In capsule mode we always hide internal lines, and use the external line:
        # - show it for critical urgency (2) even when there is only one item
        # - hide it for normal/low
        try:
            if not self._inline_items:
                self.inline_urgency_line.set_visible(False)
                return
            current = self._current_inline_view_box()
            if current is None:
                self.inline_urgency_line.set_visible(False)
                return
            urgency = getattr(getattr(current, "notification", None), "urgency", 1)
            # Reset classes
            try:
                for cls in ("low-urgency", "normal-urgency", "critical-urgency"):
                    self.inline_urgency_line.remove_style_class(cls)
            except Exception:
                ...
            if urgency == 2:
                self.inline_urgency_line.add_style_class("critical-urgency")
                self.inline_urgency_line.set_visible(True)
            elif urgency == 1:
                self.inline_urgency_line.add_style_class("normal-urgency")
                self.inline_urgency_line.set_visible(False)
            else:
                self.inline_urgency_line.add_style_class("low-urgency")
                self.inline_urgency_line.set_visible(False)
        except Exception:
            with contextlib.suppress(Exception):
                self.inline_urgency_line.set_visible(False)

    def show_inline_notification(self, notif_box: Box) -> None:
        """Add notification to inline carousel and show it."""
        try:
            # Add to items list first
            self._inline_items.append(notif_box)
            self._inline_index = len(self._inline_items) - 1

            # Set up hover events for the notification
            try:
                notif_box.add_events(
                    Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK
                )
                notif_box.connect(
                    "enter-notify-event",
                    lambda *_: hasattr(notif_box, "pause_timeout")
                    and notif_box.pause_timeout(),
                )
                notif_box.connect(
                    "leave-notify-event",
                    lambda *_: hasattr(notif_box, "resume_timeout")
                    and notif_box.resume_timeout(),
                )
            except Exception:
                ...

            # Update navigation and container - this will handle single vs multi mode
            self._update_inline_nav()
            self.inline_notification_container.set_visible(True)
            self.inline_notification_revealer.set_reveal_child(True)

            # Update external urgency line state
            self._update_inline_external_urgency_line()
            # Hook pointer events on the newly added notification card
            self._hook_pointer_events_recursively(notif_box)
        except Exception:
            self.inline_notification_container.set_visible(True)
            self.inline_notification_revealer.set_reveal_child(True)

    def remove_inline_notification(self, notif_box: Box) -> None:
        # Remove from our carousel tracking and both possible containers
        try:
            if notif_box in self._inline_items:
                idx = self._inline_items.index(notif_box)
                self._inline_items.pop(idx)

                # Remove from stack if it's there
                if notif_box.get_parent() == self.inline_stack:
                    self.inline_stack.remove(notif_box)

                # Remove from simple container if it's there
                if notif_box.get_parent() == self.inline_simple_container:
                    self.inline_simple_container.remove(notif_box)

                # Adjust current index
                if self._inline_items:
                    self._inline_index = min(idx, len(self._inline_items) - 1)
                else:
                    self._inline_index = 0
        except Exception:
            ...

        self._update_inline_nav()
        self._update_inline_external_urgency_line()

        if not self._inline_items:
            self.hide_inline_notifications()

    def hide_inline_notifications(self) -> None:
        self.inline_notification_revealer.set_reveal_child(False)
        self.inline_notification_container.set_visible(False)
        with contextlib.suppress(Exception):
            self.inline_urgency_line.set_visible(False)
        # Clear carousel
        try:
            for child in list(self.inline_stack.get_children()):
                self.inline_stack.remove(child)
                child.destroy()
        except Exception:
            ...
        self._inline_items.clear()
        self._inline_index = 0
        self._update_inline_nav()
        self._update_inline_nav()

    def _setup_island_hover_detection(self):
        """Set up hover detection for the entire Dynamic Island."""
        try:
            # Enable mouse events on the main DI container
            self.di_box.add_events(
                Gdk.EventMask.ENTER_NOTIFY_MASK
                | Gdk.EventMask.LEAVE_NOTIFY_MASK
                | Gdk.EventMask.POINTER_MOTION_MASK
            )

            # Connect hover events to pause/resume notification timers
            self.di_box.connect("enter-notify-event", self._on_island_mouse_enter)
            self.di_box.connect("leave-notify-event", self._on_island_mouse_leave)
            self.di_box.connect("motion-notify-event", self._on_island_mouse_motion)

            # Also enable events on the inline notification container
            self.inline_notification_container.add_events(
                Gdk.EventMask.ENTER_NOTIFY_MASK
                | Gdk.EventMask.LEAVE_NOTIFY_MASK
                | Gdk.EventMask.POINTER_MOTION_MASK
            )

            self.inline_notification_container.connect(
                "enter-notify-event", self._on_island_mouse_enter
            )
            self.inline_notification_container.connect(
                "leave-notify-event", self._on_island_mouse_leave
            )
            self.inline_notification_container.connect(
                "motion-notify-event", self._on_island_mouse_motion
            )

            # Track hover state for the entire island
            self._island_hovered = False

        except Exception as e:
            print(f"Failed to setup island hover detection: {e}")

    def _hook_pointer_events_recursively(self, widget):
        """Recursively add pointer event masks
        and connect to island handlers for all children widgets.
        """  # noqa: D205
        try:
            # Avoid double-hooking
            if getattr(widget, "_di_hover_hooked", False):
                return
            widget.add_events(
                Gdk.EventMask.ENTER_NOTIFY_MASK
                | Gdk.EventMask.LEAVE_NOTIFY_MASK
                | Gdk.EventMask.POINTER_MOTION_MASK
            )
            widget.connect("enter-notify-event", self._on_island_mouse_enter)
            widget.connect("leave-notify-event", self._on_island_mouse_leave)
            widget.connect("motion-notify-event", self._on_island_mouse_motion)
            widget._di_hover_hooked = True
        except Exception:
            ...

        # Recurse into children if available
        try:
            for child in widget.get_children():
                self._hook_pointer_events_recursively(child)
        except Exception:
            ...

    def _on_island_mouse_enter(self, widget, event):
        """Handle mouse entering the Dynamic Island area."""
        self._island_hovered = True
        self._pause_all_notification_timers()
        return False

    def _on_island_mouse_leave(self, widget, event):
        """Handle mouse leaving the Dynamic Island area."""
        self._island_hovered = False
        # Small delay before resuming to avoid flicker
        # when moving between island elements
        GLib.timeout_add(150, self._delayed_resume_all_timers)
        return False

    def _on_island_mouse_motion(self, widget, event):
        """Handle mouse motion within the Dynamic Island."""
        if not self._island_hovered:
            self._island_hovered = True
            self._pause_all_notification_timers()
        return False

    def _delayed_resume_all_timers(self):
        """Resume all notification timers after delay if not hovered."""
        if not self._island_hovered:
            self._resume_all_notification_timers()
        return False

    def _start_island_pointer_polling(self):
        try:
            if getattr(self, "_pointer_poll_id", None):
                return
            self._pointer_poll_id = GLib.timeout_add(200, self._poll_pointer_inside)
        except Exception:
            ...

    def _poll_pointer_inside(self):
        try:
            gdk_window = self.window.get_window()
            if not gdk_window:
                return True
            display = gdk_window.get_display()
            seat = display.get_default_seat() if display else None
            pointer = seat.get_pointer() if seat else None
            if not pointer:
                return True
            _, x, y, _ = gdk_window.get_device_position(pointer)
            width = gdk_window.get_width()
            height = gdk_window.get_height()
            inside = 0 <= x <= width and 0 <= y <= height
            if inside and not self._island_hovered:
                self._island_hovered = True
                self._pause_all_notification_timers()
            elif not inside and self._island_hovered:
                self._island_hovered = False
                self._resume_all_notification_timers()
        except Exception:
            ...

        return True

    def _pause_all_notification_timers(self):
        """Pause timeout timers for all active notifications."""
        # Pause timers for notifications in dedicated view
        try:
            for notif_box in self.notification._view_items:
                if hasattr(notif_box, "pause_timeout"):
                    notif_box.pause_timeout()
        except Exception:
            ...

        # Pause timers for inline notifications
        try:
            for notif_box in self._inline_items:
                if hasattr(notif_box, "pause_timeout"):
                    notif_box.pause_timeout()
        except Exception:
            ...

    def _resume_all_notification_timers(self):
        """Resume timeout timers for all active notifications."""
        # Resume timers for notifications in dedicated view
        try:
            for notif_box in self.notification._view_items:
                if hasattr(notif_box, "resume_timeout"):
                    notif_box.resume_timeout()
        except Exception:
            ...

        # Resume timers for inline notifications
        try:
            for notif_box in self._inline_items:
                if hasattr(notif_box, "pause_timeout"):
                    notif_box.resume_timeout()
        except Exception:
            ...

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
        # Move inline notifications to dedicated view (ordinary) before hiding capsule
        moved = False
        try:
            migrated = []
            for box in list(self._inline_items):
                moved = True
                migrated.append(box)
                # Remove from both possible inline containers
                with contextlib.suppress(Exception):
                    if box.get_parent() == self.inline_stack:
                        self.inline_stack.remove(box)
                with contextlib.suppress(Exception):
                    if box.get_parent() == self.inline_simple_container:
                        self.inline_simple_container.remove(box)
                # Adopt into dedicated notification view
                with contextlib.suppress(Exception):
                    box._inline = False
                with contextlib.suppress(Exception):
                    self.notification.view_stack.add_named(
                        box,
                        f"n-{getattr(getattr(box, 'notification', None), 'id', 'x')}",
                    )
            # Clear inline state now that we've migrated
            with contextlib.suppress(Exception):
                self._inline_items.clear()
                self._inline_index = 0
        except Exception:
            ...
        if moved:
            # Build dedicated view presentation (single vs. multi)
            try:
                # Reset containers visibility first
                self.notification.simple_container.set_visible(False)
                self.notification.view_box.set_visible(False)
            except Exception:
                ...
            try:
                self.notification._view_items = list(migrated)
                self.notification._view_index = 0
            except Exception:
                ...
            try:
                if len(self.notification._view_items) == 1:
                    # Single mode: ensure internal close is visible
                    # and show in simple container
                    one = self.notification._view_items[0]
                    with contextlib.suppress(Exception):
                        if one.get_parent() == self.notification.view_stack:
                            self.notification.view_stack.remove(one)
                    with contextlib.suppress(Exception):
                        self.notification._set_internal_close_visibility(one, True)
                        self.notification._update_internal_urgency_for_box(one)
                    self.notification._show_single_notification(one)
                    # Hide external urgency line in single mode
                    with contextlib.suppress(Exception):
                        self.notification.view_urgency_line.set_visible(False)
                elif len(self.notification._view_items) > 1:
                    # Multi mode: make sure all items are in the stack and configure nav
                    for i, box in enumerate(self.notification._view_items):
                        with contextlib.suppress(Exception):
                            if box.get_parent() != self.notification.view_stack:
                                self.notification.view_stack.add_named(
                                    box,
                                    f"n-{getattr(getattr(box, 'notification', None), 'id', i)}",
                                )
                        with contextlib.suppress(Exception):
                            self.notification._set_internal_close_visibility(box, False)
                    with contextlib.suppress(Exception):
                        self.notification.view_stack.set_visible_child(
                            self.notification._view_items[self.notification._view_index]
                        )
                    self.notification._show_multi_notification_view()
                    self.notification._update_view_nav()
                    self.notification._update_external_urgency_line()
            except Exception:
                ...

            # Hide the inline area and switch to dedicated notification view
            with contextlib.suppress(Exception):
                self.inline_notification_revealer.set_reveal_child(False)
                self.inline_notification_container.set_visible(False)
            self.open("notification")
            return
        # Hide and clear inline notifications when closing DI
        self.hide_inline_notifications()
        # Stop pointer polling
        try:
            if getattr(self, "_pointer_poll_id", None):
                GLib.source_remove(self._pointer_poll_id)
                self._pointer_poll_id = None
        except Exception:
            ...

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
        self._update_x11_constraints("compact")

    def open(self, widget: str = "date-notification") -> None:
        if widget == "compact":
            self.current_widget = None
            return

        # Save the currently focused bspwm node BEFORE stealing keyboard input.
        # This ensures _restore_x11_focus() can return focus to the exact window
        # that was active when DI opened, regardless of bspwm's 'last' history.
        if WindowManagerContext.is_x11() and widget != "notification":
            node_id = self._get_focused_node_id()
            if node_id:
                self._focused_node_before_open = node_id
                logger.debug(f"[X11] Saved focused node before open: {node_id}")

        if self.hidden:
            self.di_box.remove_style_class("hidden")
            self.di_box.add_style_class("hideshow")

        for style, w in self.widgets.items():
            self.stack.remove_style_class(style)
            w.remove_style_class("open")

        if widget not in self.widgets:
            widget = "date-notification"

        self.current_widget = widget

        # On X11: always try to grab keyboard focus when DI opens any widget.
        # steal_input_soft() uses XSetInputFocus which bypasses bspwm's
        # focus-stealing prevention. For focuse_kb widgets we additionally
        # do a full Gdk.keyboard_grab so all key events arrive even when
        # another X window nominally holds WM focus.
        if WindowManagerContext.is_x11() and widget != "notification":
            if self.widgets[widget].focuse_kb:
                # Full grab: routes ALL keyboard events to us
                self.set_keyboard_mode("exclusive")
            else:
                # Soft grab: X11 focus only, no global event interception
                try:
                    if hasattr(self.window, "steal_input_soft"):
                        self.window.steal_input_soft(can_release=True)
                        logger.debug("[X11] steal_input_soft() on open (non-focuse_kb)")
                except Exception as e:
                    logger.warning(f"[X11] steal_input_soft failed on open: {e}")
        elif self.widgets[widget].focuse_kb:
            self.set_keyboard_mode("exclusive")

        self.stack.add_style_class(widget)
        self.stack.set_visible_child(self.widgets[widget])

        # Enforce X11 geometry constraints for the new widget
        self._update_x11_constraints(widget)

        self.widgets[widget].add_style_class("open")

        # Sync inline container styling with current widget to mirror width constraints
        for style in self.widgets:
            self.inline_notification_container.remove_style_class(style)

        self.inline_notification_container.add_style_class(widget)

        self.call_module_method_if_exists(
            self.widgets[self.current_widget], "open_widget_from_di"
        )

        # Ensure all children have pointer events hooked (some widgets change on open)
        self._hook_pointer_events_recursively(self.di_root_column)

        if widget == "notification":
            self.set_keyboard_mode("none")
        else:
            # When opening DI to another widget,
            # move dedicated notifications to inline capsule
            try:
                for box in list(getattr(self.notification, "_view_items", [])):
                    # Detach from current dedicated parent first
                    # (stack in multi or simple_container in single)
                    with contextlib.suppress(Exception):
                        parent = box.get_parent()
                        if parent == self.notification.view_stack:
                            self.notification.view_stack.remove(box)
                        elif parent == self.notification.simple_container:
                            self.notification.simple_container.remove(box)
                    # Mark as inline and add to inline capsule
                    with contextlib.suppress(Exception):
                        box._inline = True
                    self.show_inline_notification(box)
                # Clear dedicated list
                with contextlib.suppress(Exception):
                    self.notification._view_items.clear()
                    self.notification._view_index = 0
                    self.notification._update_view_nav()
            except Exception:
                ...
