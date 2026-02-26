import subprocess
from collections.abc import Callable
from collections.abc import Iterable

from fabric.core.widgets import ActiveWindow
from fabric.core.widgets import Language
from fabric.core.widgets import WorkspaceButton
from fabric.core.widgets import Workspaces
from fabric.utils.helpers import FormattedString
from fabric.utils.helpers import truncate
from gi.repository import GLib
from loguru import logger

from mewline.custom_fabric.bspwm.service import Bspwm
from mewline.custom_fabric.bspwm.service import BspwmEvent

connection: Bspwm | None = None


def get_bspwm_connection() -> Bspwm:
    """Get or create a global Bspwm connection."""
    global connection
    if not connection:
        connection = Bspwm()
    return connection


class BspwmWorkspaces(Workspaces):
    """A workspace widget for bspwm window manager.

    This widget displays workspaces and their states (active, occupied, urgent).
    It automatically updates when workspace state changes.
    """

    def __init__(
        self,
        buttons: Iterable[WorkspaceButton] | None = None,
        buttons_factory: Callable[[int], WorkspaceButton | None]
        | None = Workspaces.default_buttons_factory,
        invert_scroll: bool = False,
        **kwargs,
    ):
        super().__init__(buttons, buttons_factory, invert_scroll, **kwargs)
        self.connection = get_bspwm_connection()

        # Subscribe to bspwm events
        self.connection.connect("event::report", self.on_report_event)

        if self.connection.ready:
            self.on_ready()
        else:
            self.connection.connect("notify::ready", self.on_ready)

        self.connect("scroll-event", self.do_handle_scroll)

    def on_ready(self, *args):
        """Initialize workspaces when connection is ready."""
        state = self.connection.get_state()
        if not state:
            return logger.error("[BspwmWorkspaces] Failed to get initial state")

        # Parse initial state
        for monitor in state.get("monitors", []):
            for desktop in monitor.get("desktops", []):
                desktop_name = desktop.get("name", "")
                if not desktop_name:
                    continue

                # Try to parse desktop name as int for button ID
                try:
                    ws_id = int(desktop_name)
                except ValueError:
                    # Use hash of name if not numeric
                    ws_id = hash(desktop_name) % 1000

                # Create workspace button
                self.workspace_created(ws_id)

                # Set initial state
                if desktop.get("root") is not None:  # noqa: SIM102
                    # Desktop has windows, mark as occupied by setting empty=False
                    if btn := self._buttons.get(ws_id):
                        btn.empty = False

                # Check if focused
                if desktop.get("id") == monitor.get("focusedDesktopId"):
                    self.workspace_activated(ws_id)

        logger.info("[BspwmWorkspaces] Initialized with current state")

    def on_report_event(self, _, event: BspwmEvent):
        """Handle bspwm report events."""
        try:
            monitors = event.data.get("monitors", [])

            # Track which workspaces exist and their states
            active_workspaces = set()

            for monitor in monitors:
                for desktop in monitor["desktops"]:
                    desktop_name = desktop["name"]

                    # Try to parse as int
                    try:
                        ws_id = int(desktop_name)
                    except ValueError:
                        ws_id = hash(desktop_name) % 1000

                    active_workspaces.add(ws_id)

                    # Create workspace if it doesn't exist
                    if ws_id not in self._buttons:
                        self.workspace_created(ws_id)

                    # Update workspace state
                    btn = self._buttons.get(ws_id)
                    if not btn:
                        continue

                    # Update occupied state
                    btn.empty = not desktop["occupied"]

                    # Update urgent state
                    if desktop["urgent"]:
                        self.urgent(ws_id)
                    else:
                        btn.urgent = False

                    # Update focused state
                    if desktop["focused"] and desktop["monitor_focused"]:
                        self.workspace_activated(ws_id)

        except Exception as e:
            logger.error(f"[BspwmWorkspaces] Error handling report event: {e}")

    def do_action_next(self):
        """Switch to next desktop."""
        return self.connection.send_command("desktop -f next.local")

    def do_action_previous(self):
        """Switch to previous desktop."""
        return self.connection.send_command("desktop -f prev.local")

    def do_button_clicked(self, button: WorkspaceButton):
        """Handle workspace button clicks."""
        return self.connection.send_command(f"desktop -f {button.id}")


class BspwmActiveWindow(ActiveWindow):
    """A widget that displays the title of the active window in bspwm.

    The widget automatically updates when window focus changes.
    """

    def __init__(
        self,
        formatter: FormattedString = FormattedString(  # noqa: B008
            "{'Desktop' if not win_title else truncate(win_title, 42)}",
            truncate=truncate,
        ),
        **kwargs,
    ):
        super().__init__(formatter, **kwargs)
        self.connection = get_bspwm_connection()

        # Subscribe to events
        self.connection.connect("event::report", self.on_report_event)

        if self.connection.ready:
            self.on_ready()
        else:
            self.connection.connect("notify::ready", self.on_ready)

        # Poll for title changes since bspwm doesn't emit title change events
        GLib.timeout_add(500, self.poll_active_window)

    def on_ready(self, *args):
        """Initialize active window when connection is ready."""
        self.update_active_window()
        logger.info("[BspwmActiveWindow] Initialized")

    def on_report_event(self, _, event: BspwmEvent):
        """Handle report events (focus changes)."""
        # Update on any report event as focus might have changed
        GLib.idle_add(self.update_active_window)

    def poll_active_window(self) -> bool:
        """Periodically check active window title."""
        self.update_active_window()
        return True  # Continue polling

    def update_active_window(self):
        """Update the active window title."""
        try:
            # Get focused node ID
            reply = self.connection.send_command("query -N -n focused", silent=True)
            if not reply.is_ok or not reply.output:
                self.window_activated("", "Desktop")
                return

            node_id = reply.output.strip()

            # Get window class
            class_reply = self.connection.send_command(
                f"query -T -n {node_id} | head -1"
            )
            win_class = class_reply.output.strip() if class_reply.is_ok else "unknown"

            # Get window title using xtitle or xdotool
            title_result = subprocess.run(  # noqa: S602
                f"xtitle {node_id}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=1,
            )

            if title_result.returncode == 0 and title_result.stdout:
                win_title = title_result.stdout.strip()
            else:
                # Fallback to xdotool
                title_result = subprocess.run(  # noqa: S602
                    f"xdotool getwindowname {node_id}",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                win_title = (
                    title_result.stdout.strip()
                    if title_result.returncode == 0
                    else win_class
                )

            self.window_activated(win_class, win_title)

        except subprocess.TimeoutExpired:
            logger.warning("[BspwmActiveWindow] Timeout getting window title")
        except Exception as e:
            logger.debug(f"[BspwmActiveWindow] Error updating window: {e}")
            self.window_activated("", "Desktop")


class BspwmLanguage(Language):
    """A widget that displays the current keyboard layout.

    Note: This widget requires setxkbmap or xkb-switch to be installed.
    It polls the keyboard layout periodically since bspwm doesn't provide
    layout change events directly.
    """

    def __init__(
        self,
        keyboard: str = ".*",
        formatter: FormattedString = FormattedString("{language}"),  # noqa: B008
        poll_interval: int = 1000,
        **kwargs,
    ):
        super().__init__(keyboard, formatter, **kwargs)
        self.connection = get_bspwm_connection()
        self.poll_interval = poll_interval

        if self.connection.ready:
            self.on_ready()
        else:
            self.connection.connect("notify::ready", self.on_ready)

        # Start polling for layout changes
        GLib.timeout_add(self.poll_interval, self.poll_keyboard_layout)

    def on_ready(self, *args):
        """Initialize language widget when connection is ready."""
        self.update_keyboard_layout()
        logger.info("[BspwmLanguage] Initialized")

    def poll_keyboard_layout(self) -> bool:
        """Periodically check keyboard layout."""
        self.update_keyboard_layout()
        return True  # Continue polling

    def update_keyboard_layout(self):
        """Update the current keyboard layout."""
        try:
            # Try xkb-switch first (more reliable)
            result = subprocess.run(
                ["xkb-switch", "-p"],
                capture_output=True,
                text=True,
                timeout=1,
            )

            if result.returncode == 0 and result.stdout:
                layout = result.stdout.strip()
                self.layout_changed(layout, "keyboard")
                return

            # Fallback to setxkbmap
            result = subprocess.run(
                ["setxkbmap", "-query"],
                capture_output=True,
                text=True,
                timeout=1,
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if line.startswith("layout:"):
                        layout = line.split(":", 1)[1].strip()
                        self.layout_changed(layout, "keyboard")
                        return

        except FileNotFoundError:
            logger.warning(
                "[BspwmLanguage] xkb-switch or setxkbmap not found. "
                "Please install one of them."
            )
        except subprocess.TimeoutExpired:
            logger.warning("[BspwmLanguage] Timeout getting keyboard layout")
        except Exception as e:
            logger.debug(f"[BspwmLanguage] Error getting layout: {e}")


__all__ = [
    "BspwmActiveWindow",
    "BspwmLanguage",
    "BspwmWorkspaces",
    "WorkspaceButton",
    "get_bspwm_connection",
]
