from fabric.widgets.box import Box
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.wayland import WaylandWindow

from utils.hyprland_monitors import HyprlandMonitors
from widgets.battery import Battery
from widgets.brightness import BrightnessWidget
from widgets.datetime import DateTimeWidget
from widgets.dynamic_island import DynamicIsland
from widgets.power import PowerButton
from widgets.system_tray import SystemTray
from widgets.volume import VolumeWidget
from widgets.workspaces import HyprlandWorkSpacesWidget


class StatusBar(WaylandWindow):
    """A widget to display the status bar panel."""

    widgets_list: dict

    def __init__(self, di: DynamicIsland, **kwargs):
        box = CenterBox(
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
                    BrightnessWidget(),
                    Battery(),
                    VolumeWidget(),
                    DateTimeWidget(),
                    PowerButton(di=di),
                ],
            ),
        )

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

    def pr(self):
        print("hello!")
