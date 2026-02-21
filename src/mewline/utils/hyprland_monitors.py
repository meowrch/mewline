import json
import warnings

import gi
from fabric.hyprland import Hyprland
from gi.repository import Gdk

gi.require_version("Gdk", "3.0")


# IDC,  Gdk.Screen.get_monitor_plug_name is deprecated
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Another idea is to use Gdk.Monitor.get_model() however,
#       there is no  guarantee that this will be unique
#       Example: both monitors have the same model number
#       (quite common in multi monitor setups)


# Also, using Gdk.Display.get_monitor_at_point(x,y)
#       does not work correctly on all wayland setups


# Annoyingly, Gdk 4.0 has a solution to this with
#       Gdk.Monitor.get_description() or Gdk.Monitor.get_connector()
#       which both can be used to uniquely identify a monitor


class HyprlandMonitors(Hyprland):
    """A Hyprland class with additional monitor functions."""

    def __init__(self, commands_only: bool = False, **kwargs):
        self.display: Gdk.Display = Gdk.Display.get_default()
        super().__init__(commands_only, **kwargs)

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def get_gdk_monitor_id_from_name(self, plug_name: str) -> int | None:
        """Return the GDK monitor index that matches *plug_name*."""
        for i in range(self.display.get_n_monitors()):
            if (
                self.display.get_default_screen().get_monitor_plug_name(i)
                == plug_name
            ):
                return i
        return None

    # ------------------------------------------------------------------
    # Hyprland monitor list
    # ------------------------------------------------------------------

    def get_all_monitors(self) -> list[dict]:
        """Return the raw list of monitors from Hyprland IPC (j/monitors)."""
        return json.loads(self.send_command("j/monitors").reply)

    def get_all_gdk_monitor_ids(self) -> list[int]:
        """Return GDK IDs for **all** connected monitors."""
        ids: list[int] = []
        for mon in self.get_all_monitors():
            gdk_id = self.get_gdk_monitor_id_from_name(mon["name"])
            if gdk_id is not None:
                ids.append(gdk_id)
        return ids

    # ------------------------------------------------------------------
    # Active-workspace monitor (legacy + new name)
    # ------------------------------------------------------------------

    def get_active_hypr_monitor_name(self) -> str:
        """Return the Hyprland name of the monitor that owns the active workspace."""
        active_workspace = json.loads(
            self.send_command("j/activeworkspace").reply
        )
        return active_workspace["monitor"]

    def get_active_gdk_monitor_id(self) -> int | None:
        """Return the GDK ID of the monitor that owns the active workspace."""
        return self.get_gdk_monitor_id_from_name(
            self.get_active_hypr_monitor_name()
        )

    # Keep the old name around so nothing else breaks.
    def get_current_gdk_monitor_id(self) -> int | None:
        """Alias for get_active_gdk_monitor_id (backwards-compat)."""
        return self.get_active_gdk_monitor_id()

    # ------------------------------------------------------------------
    # Cursor monitor
    # ------------------------------------------------------------------

    def get_cursor_monitor_name(self) -> str | None:
        """Return the Hyprland name of the monitor that currently holds the pointer."""
        try:
            data = json.loads(self.send_command("j/cursorpos").reply)
            x, y = data["x"], data["y"]
            for mon in self.get_all_monitors():
                mx, my = mon["x"], mon["y"]
                mw, mh = mon["width"], mon["height"]
                if mx <= x < mx + mw and my <= y < my + mh:
                    return mon["name"]
        except Exception:  # noqa: S110
            pass
        return None

    def get_cursor_gdk_monitor_id(self) -> int | None:
        """Return the GDK ID of the monitor under the pointer."""
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

        if mode == "active":
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

        # mode == "all"  (default)
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

        # mode == "all"  (default)
        return self.get_all_gdk_monitor_ids()
