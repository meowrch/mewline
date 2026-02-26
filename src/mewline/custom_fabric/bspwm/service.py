import json
import subprocess
from dataclasses import dataclass
from enum import Enum

from fabric.core.service import Property
from fabric.core.service import Service
from fabric.core.service import Signal
from fabric.utils.helpers import exec_shell_command
from fabric.utils.helpers import idle_add
from gi.repository import GLib
from loguru import logger


class BspwmError(Exception):
    """Base exception for Bspwm errors."""



class BspwmEventType(Enum):
    """Event types from bspc subscribe."""

    REPORT = "report"
    NODE_ADD = "node_add"
    NODE_REMOVE = "node_remove"
    NODE_SWAP = "node_swap"
    NODE_TRANSFER = "node_transfer"
    NODE_FOCUS = "node_focus"
    NODE_ACTIVATE = "node_activate"
    NODE_PRESEL = "node_presel"
    NODE_STACK = "node_stack"
    NODE_GEOMETRY = "node_geometry"
    NODE_STATE = "node_state"
    NODE_FLAG = "node_flag"
    NODE_LAYER = "node_layer"
    NODE_LOCKED = "node_locked"
    NODE_MARKED = "node_marked"
    NODE_HIDDEN = "node_hidden"
    NODE_STICKY = "node_sticky"
    NODE_PRIVATE = "node_private"
    NODE_URGENT = "node_urgent"
    DESKTOP_ADD = "desktop_add"
    DESKTOP_RENAME = "desktop_rename"
    DESKTOP_REMOVE = "desktop_remove"
    DESKTOP_SWAP = "desktop_swap"
    DESKTOP_TRANSFER = "desktop_transfer"
    DESKTOP_FOCUS = "desktop_focus"
    DESKTOP_ACTIVATE = "desktop_activate"
    DESKTOP_LAYOUT = "desktop_layout"
    MONITOR_ADD = "monitor_add"
    MONITOR_RENAME = "monitor_rename"
    MONITOR_REMOVE = "monitor_remove"
    MONITOR_SWAP = "monitor_swap"
    MONITOR_FOCUS = "monitor_focus"
    MONITOR_GEOMETRY = "monitor_geometry"
    POINTER_ACTION = "pointer_action"


@dataclass(frozen=True)
class BspwmEvent:
    """Represents a bspwm event."""

    name: str
    """The name of the received event."""
    data: dict
    """The parsed data from the event."""
    raw_data: str
    """The raw event data."""


@dataclass(frozen=True)
class BspwmReply:
    """Represents a reply from a bspwm command."""

    command: str
    """The executed command."""
    output: str
    """The raw output from the command."""
    is_ok: bool
    """Whether the command executed successfully."""


class Bspwm(Service):
    """A service for interacting with bspwm window manager.

    This service provides command execution and event monitoring.
    """

    @Property(bool, "readable", "is-ready", default_value=False)
    def ready(self) -> bool:
        return self._ready

    @Signal("event", flags="detailed")
    def event(self, event: object):
        """Emitted when a bspwm event is received."""
        ...

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ready = False

        # Check if bspwm is running
        if not self.is_bspwm_running():
            raise BspwmError("bspwm is not running")

        # Start event listener thread
        self.event_thread = GLib.Thread.new(
            "bspwm-event-service",
            self.event_listener_task,  # type: ignore
        )

        self._ready = True
        self.notify("ready")
        logger.info("[BspwmService] Initialized and ready")

    @staticmethod
    def is_bspwm_running() -> bool:
        """Check if bspwm is currently running."""
        try:
            result = exec_shell_command("pgrep -x bspwm")
            return bool(result and result.strip())
        except Exception:
            return False

    @staticmethod
    def send_command(command: str, silent: bool = False) -> "BspwmReply":
        """Execute a bspc command.

        Example:
        ```python
        # Switch to desktop 1
        Bspwm.send_command("desktop -f 1")
        ```

        :param command: The bspc command to execute (without 'bspc' prefix).
        :type command: str
        :param silent: If True, do not log a WARNING on non-zero exit code.
            Use this for queries that are expected to fail transiently
            (e.g. ``query -N -n focused`` while DI holds keyboard grab).
        :type silent: bool
        :return: A reply object containing the command output.
        :rtype: BspwmReply
        """
        is_ok = False
        output = ""

        try:
            full_command = f"bspc {command}"
            result = subprocess.run(  # noqa: S602
                full_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = result.stdout.strip()
            is_ok = result.returncode == 0

            if not is_ok:
                if silent:
                    logger.debug(
                        f"[BspwmService] Command returned non-zero (silent): "
                        f"{full_command}, stderr: {result.stderr.strip()!r}"
                    )
                else:
                    logger.warning(
                        f"[BspwmService] Command failed: {full_command}, "
                        f"error: {result.stderr}"
                    )
        except subprocess.TimeoutExpired:
            logger.error(f"[BspwmService] Command timeout: {command}")
        except Exception as e:
            logger.error(f"[BspwmService] Error executing command: {e}")

        return BspwmReply(command=command, output=output, is_ok=is_ok)

    @staticmethod
    def get_state() -> dict | None:
        """Get the current window manager state.

        :return: The parsed JSON state or None on error.
        :rtype: dict | None
        """
        reply = Bspwm.send_command("wm --dump-state")
        if not reply.is_ok or not reply.output:
            return None

        try:
            return json.loads(reply.output)
        except json.JSONDecodeError as e:
            logger.error(f"[BspwmService] Failed to parse state JSON: {e}")
            return None

    def event_listener_task(self) -> bool:
        """Background task that listens to bspwm events.
        This runs in a separate thread.
        """  # noqa: D205
        try:
            process = subprocess.Popen(
                ["bspc", "subscribe", "report"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            logger.info("[BspwmService] Event listener started")

            while True:
                line = process.stdout.readline()
                if not line:
                    break

                line = line.strip()
                if line:
                    idle_add(self.handle_raw_event, line)

        except Exception as e:
            logger.error(f"[BspwmService] Event listener thread error: {e}")

        return False

    def handle_raw_event(self, raw_data: str):
        """Parse and emit bspwm events.

        :param raw_data: Raw event string from bspc subscribe.
        :type raw_data: str
        """
        try:
            # Parse the report format
            # Example: WMHDMI-0:o1:O2:o3:f4:F5:LT:TT:G
            parts = raw_data.split(":")
            if not parts or len(parts) < 2:
                return

            # Create event data dictionary
            event_data = {
                "raw": raw_data,
                "parts": parts,
            }

            # Parse monitors and desktops
            monitors = []
            current_monitor = None

            i = 0
            while i < len(parts):
                part = parts[i]

                if not part:
                    i += 1
                    continue

                # First part should be "WM" + monitor name
                if i == 0 and part.startswith("WM"):
                    # Extract monitor name from "WMHDMI-0" or "WmHDMI-0"
                    monitor_focused = part[
                        1
                    ].isupper()  # Second char: M=focused, m=unfocused
                    monitor_name = part[2:]  # Everything after "WM"/"Wm"

                    current_monitor = {
                        "name": monitor_name,
                        "focused": monitor_focused,
                        "desktops": [],
                    }
                    i += 1
                    continue

                # Check for new monitor (format: "M" or "m" followed by name)
                if (
                    part[0] in ["M", "m"]
                    and len(part) > 1
                    and part[1:].replace("-", "").replace("_", "").isalnum()
                ):
                    # This is a new monitor
                    if current_monitor:
                        monitors.append(current_monitor)

                    monitor_focused = part[0] == "M"
                    monitor_name = part[1:]

                    current_monitor = {
                        "name": monitor_name,
                        "focused": monitor_focused,
                        "desktops": [],
                    }
                    i += 1
                    continue

                # Desktop item
                if part[0] in ["O", "o", "F", "f", "U", "u"] and current_monitor:
                    prefix = part[0]
                    desktop_name = part[1:] if len(part) > 1 else ""

                    # Uppercase = focused, lowercase = unfocused
                    is_focused = prefix.isupper()
                    is_occupied = prefix in ["O", "o", "U", "u"]
                    is_urgent = prefix in ["U", "u"]

                    current_monitor["desktops"].append(
                        {
                            "name": desktop_name,
                            "focused": is_focused,
                            "occupied": is_occupied,
                            "urgent": is_urgent,
                            "monitor_focused": current_monitor["focused"],
                        }
                    )
                    i += 1
                    continue

                # Layout indicator (LT = tiled, LM = monocle)
                if part[0] == "L" and current_monitor:
                    layout = part[1:] if len(part) > 1 else ""
                    layout_map = {"T": "tiled", "M": "monocle"}
                    current_monitor["layout"] = layout_map.get(layout, layout)
                    i += 1
                    continue

                # Other flags (T, G) - ignore for now
                i += 1

            # Add last monitor
            if current_monitor:
                monitors.append(current_monitor)

            event_data["monitors"] = monitors

            # Emit report event
            event = BspwmEvent(
                name="report",
                data=event_data,
                raw_data=raw_data,
            )

            self.emit("event::report", event)

        except Exception as e:
            logger.error(f"[BspwmService] Error parsing event: {e}, raw: {raw_data}")
