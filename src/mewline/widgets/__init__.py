from fabric.widgets.box import Box
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.wayland import WaylandWindow

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


class StatusBar(WaylandWindow):
    """A widget to display the status bar panel."""

    def __init__(self, **kwargs):
        self.combined_controls = CombinedControlsButton()

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

    def set_osd_widget(self, osd_widget):
        """Set OSD widget reference for combined controls."""
        if hasattr(self, 'combined_controls'):
            self.combined_controls.set_osd_widget(osd_widget)
