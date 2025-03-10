from fabric.widgets.box import Box
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.wayland import WaylandWindow

from mewline.utils.hyprland_monitors import HyprlandMonitors
from mewline.widgets.battery import Battery
from mewline.widgets.bluetooth import Bluetooth
from mewline.widgets.brightness import BrightnessWidget
from mewline.widgets.datetime import DateTimeWidget
from mewline.widgets.language import LanguageWidget
from mewline.widgets.microphone import MicrophoneWidget
from mewline.widgets.ocr import OCRWidget
from mewline.widgets.power import PowerButton
from mewline.widgets.system_tray import SystemTray
from mewline.widgets.volume import VolumeWidget
from mewline.widgets.workspaces import HyprlandWorkSpacesWidget


class StatusBar(WaylandWindow):
    """A widget to display the status bar panel."""

    widgets_list: dict

    def __init__(self, **kwargs):
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
                    OCRWidget(),
                    BrightnessWidget(),
                    Battery(),
                    VolumeWidget(),
                    MicrophoneWidget(),
                    LanguageWidget(),
                    DateTimeWidget(),
                    Bluetooth(),
                    PowerButton(),
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
