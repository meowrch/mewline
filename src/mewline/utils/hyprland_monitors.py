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

    def get_gdk_monitor_id_from_name(
        self, plug_name: str
    ) -> int | None:
        for i in range(self.display.get_n_monitors()):
            if (
                self.display.get_default_screen().get_monitor_plug_name(
                    i
                )
                == plug_name
            ):
                return i
        return None

    def get_current_gdk_monitor_id(self) -> int | None:
        active_workspace = json.loads(
            self.send_command("j/activeworkspace").reply
        )
        return self.get_gdk_monitor_id_from_name(
            active_workspace["monitor"]
        )
