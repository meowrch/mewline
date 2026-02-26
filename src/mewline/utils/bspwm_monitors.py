"""Monitor management for bspwm/X11."""

import subprocess
import warnings

import gi
from gi.repository import Gdk
from loguru import logger

gi.require_version("Gdk", "3.0")

# IDC, Gdk.Screen.get_monitor_plug_name is deprecated
warnings.filterwarnings("ignore", category=DeprecationWarning)


class BspwmMonitors:
    """A class for managing monitors in bspwm/X11 environment."""

    def __init__(self):
        self.display: Gdk.Display | None = None
        # Don't get display in __init__ - it may not be ready yet
        # We'll get it lazily in methods that need it

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _get_display(self) -> Gdk.Display | None:
        """Lazily get Gdk.Display, caching it after first successful retrieval."""
        if self.display is None:
            self.display = Gdk.Display.get_default()
            if self.display is None:
                logger.debug("Gdk.Display not available yet")
        return self.display

    def get_gdk_monitor_id_from_name(self, plug_name: str) -> int | None:
        """Return the GDK monitor index that matches *plug_name*.

        Args:
            plug_name: The connector name (e.g. "DP-1", "HDMI-1")

        Returns:
            The GDK monitor index, or None if not found
        """
        display = self._get_display()
        if not display:
            return None

        for i in range(display.get_n_monitors()):
            try:
                monitor_plug = display.get_default_screen().get_monitor_plug_name(i)
                if monitor_plug == plug_name:
                    return i
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------
    # Monitor information via xrandr
    # ------------------------------------------------------------------

    def get_all_monitors(self) -> list[dict]:
        """Return information about all connected monitors via xrandr.

        Returns:
            List of dicts with keys: name, x, y, width, height, primary
        """
        try:
            result = subprocess.run(
                ["xrandr", "--query"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if result.returncode != 0:
                logger.warning(f"xrandr failed with code {result.returncode}")
                return []

            monitors = []
            for line in result.stdout.split("\n"):
                # Look for lines like: "DP-1 connected primary 1920x1080+0+0 ..."
                if " connected " in line:
                    parts = line.split()
                    name = parts[0]

                    # Find geometry (WIDTHxHEIGHT+X+Y)
                    geometry = None
                    primary = "primary" in parts

                    for part in parts:
                        if "x" in part and "+" in part:
                            geometry = part
                            break

                    if geometry:
                        try:
                            # Parse "1920x1080+0+0"
                            size_pos = geometry.split("+")
                            width, height = map(int, size_pos[0].split("x"))
                            x = int(size_pos[1])
                            y = int(size_pos[2])

                            monitors.append({
                                "name": name,
                                "x": x,
                                "y": y,
                                "width": width,
                                "height": height,
                                "primary": primary,
                            })
                        except (ValueError, IndexError) as e:
                            logger.warning(f"Failed to parse geometry for {name}: {e}")
                            continue

            return monitors
        except FileNotFoundError:
            logger.error("xrandr not found - cannot detect monitors")
            return []
        except subprocess.TimeoutExpired:
            logger.error("xrandr timed out")
            return []
        except Exception as e:
            logger.error(f"Error getting monitors via xrandr: {e}")
            return []

    def get_all_gdk_monitor_ids(self) -> list[int]:
        """Return GDK IDs for **all** connected monitors.

        Returns:
            List of GDK monitor indices
        """
        display = self._get_display()
        if not display:
            return []

        ids: list[int] = []
        for mon in self.get_all_monitors():
            gdk_id = self.get_gdk_monitor_id_from_name(mon["name"])
            if gdk_id is not None:
                ids.append(gdk_id)

        # Fallback: if xrandr parsing failed, use all available GDK monitors
        if not ids:
            return list(range(display.get_n_monitors()))

        return ids

    # ------------------------------------------------------------------
    # Active monitor (focused desktop)
    # ------------------------------------------------------------------

    def get_active_monitor_name(self) -> str | None:
        """Return the name of the monitor that contains the focused desktop.

        Uses bspc query to get the focused desktop's monitor.

        Returns:
            Monitor name (e.g. "DP-1") or None if detection fails
        """
        try:
            # Get focused desktop
            result = subprocess.run(
                ["bspc", "query", "-D", "-d", "focused", "--names"],
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
            if result.returncode != 0:
                return None

            desktop_name = result.stdout.strip()

            # Get monitor for this desktop
            result = subprocess.run(
                ["bspc", "query", "-M", "-d", desktop_name, "--names"],
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
            if result.returncode != 0:
                return None

            return result.stdout.strip() or None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        except Exception as e:
            logger.debug(f"Error getting active monitor: {e}")
            return None

    def get_active_gdk_monitor_id(self) -> int | None:
        """Return the GDK ID of the monitor with the focused desktop.

        Returns:
            GDK monitor index or None
        """
        name = self.get_active_monitor_name()
        if name is None:
            return None
        return self.get_gdk_monitor_id_from_name(name)

    # ------------------------------------------------------------------
    # Cursor monitor
    # ------------------------------------------------------------------

    def get_cursor_position(self) -> tuple[int, int] | None:
        """Get current cursor position via xdotool.

        Returns:
            Tuple of (x, y) coordinates or None if detection fails
        """
        try:
            result = subprocess.run(
                ["xdotool", "getmouselocation", "--shell"],
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
            if result.returncode != 0:
                return None

            # Parse output: "X=123\nY=456\n..."
            x = y = None
            for line in result.stdout.split("\n"):
                if line.startswith("X="):
                    x = int(line.split("=")[1])
                elif line.startswith("Y="):
                    y = int(line.split("=")[1])

            if x is not None and y is not None:
                return (x, y)
        except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
            pass
        except Exception as e:
            logger.debug(f"Error getting cursor position: {e}")

        return None

    def get_cursor_monitor_name(self) -> str | None:
        """Return the name of the monitor that currently holds the pointer.

        Returns:
            Monitor name or None if detection fails
        """
        pos = self.get_cursor_position()
        if pos is None:
            return None

        x, y = pos
        for mon in self.get_all_monitors():
            mx, my = mon["x"], mon["y"]
            mw, mh = mon["width"], mon["height"]
            if mx <= x < mx + mw and my <= y < my + mh:
                return mon["name"]

        return None

    def get_cursor_gdk_monitor_id(self) -> int | None:
        """Return the GDK ID of the monitor under the pointer.

        Returns:
            GDK monitor index or None
        """
        name = self.get_cursor_monitor_name()
        if name is None:
            return None
        return self.get_gdk_monitor_id_from_name(name)

    # ------------------------------------------------------------------
    # Config-driven selector
    # ------------------------------------------------------------------

    def get_configured_gdk_monitor_ids(self, cfg) -> list[int]:
        """Return monitor GDK IDs according to *cfg.monitors*.

        Parameters:
        ----------
        cfg:
            The loaded :class:`~mewline.utils.config_structure.Config` object.

        Returns:
        -------
        list[int]
            Ordered list of GDK monitor indices to create widgets on.
            Falls back to all monitors if nothing matches.
        """
        mode = cfg.monitors.mode

        if mode == "cursor":
            mid = self.get_active_gdk_monitor_id()
            return [mid] if mid is not None else self.get_all_gdk_monitor_ids()

        if mode == "list":
            ids: list[int] = []
            for name in cfg.monitors.monitors_list:
                gdk_id = self.get_gdk_monitor_id_from_name(name)
                if gdk_id is not None:
                    ids.append(gdk_id)
            # If the list is empty or none matched, fall back to all monitors.
            return ids if ids else self.get_all_gdk_monitor_ids()

        # mode == "all" (default)
        return self.get_all_gdk_monitor_ids()

    def get_notifications_gdk_monitor_ids(self, cfg) -> list[int]:
        """Return monitor GDK IDs according to *cfg.notifications_monitors*.

        Parameters:
        ----------
        cfg:
            The loaded :class:`~mewline.utils.config_structure.Config` object.

        Returns:
        -------
        list[int]
            Ordered list of GDK monitor indices to show notifications on.
            Falls back to all monitors if nothing matches.
        """
        mode = cfg.notifications_monitors.mode

        if mode == "cursor":
            mid = self.get_cursor_gdk_monitor_id()
            return [mid] if mid is not None else self.get_all_gdk_monitor_ids()

        if mode == "list":
            ids: list[int] = []
            for name in cfg.notifications_monitors.monitors_list:
                gdk_id = self.get_gdk_monitor_id_from_name(name)
                if gdk_id is not None:
                    ids.append(gdk_id)
            # If the list is empty or none matched, fall back to all monitors.
            return ids if ids else self.get_all_gdk_monitor_ids()

        # mode == "all" (default)
        return self.get_all_gdk_monitor_ids()
