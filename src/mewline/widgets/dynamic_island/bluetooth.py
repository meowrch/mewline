from fabric.bluetooth import BluetoothClient
from fabric.bluetooth import BluetoothDevice
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from fabric.widgets.scrolledwindow import ScrolledWindow

from mewline import constants as cnst
from mewline.services import bluetooth_client
from mewline.utils.widget_utils import setup_cursor_hover
from mewline.utils.widget_utils import text_icon
from mewline.widgets.dynamic_island.base import BaseDiWidget


class BluetoothDeviceSlot(CenterBox):
    def __init__(self, device: BluetoothDevice, **kwargs):
        super().__init__(name="bluetooth-device", **kwargs)
        self.device = device

        if not device.name or device.name.strip() == "":
            self.device.close()
            self.destroy()
            del self
            return

        self.device.connect("changed", self.on_changed)
        self.device.connect(
            "notify::closed", lambda *_: self.device.closed and self.destroy()
        )

        self.connect_button = Button(
            name="bluetooth-connect",
            label="Connect",
            on_clicked=lambda *_: self.device.set_connecting(not self.device.connected),
        )
        setup_cursor_hover(self.connect_button)

        icons = [
            Image(icon_name=device.icon_name + "-symbolic", size=32),
        ]

        if device.paired:
            icons.append(
                text_icon(
                    icon=cnst.icons["bluetooth"]["paired"],
                    size="24px",
                    props={"style_classes": "paired"},
                )
            )

        self.start_children = [
            Box(
                spacing=8,
                children=[*icons, Label(label=device.name)],
            )
        ]
        self.end_children = self.connect_button

        self.device.emit("changed")  # to update display status

    def on_changed(self, *_):
        if self.device.connecting:
            self.connect_button.set_label(
                "Connecting..." if not self.device.connecting else "Disconnecting..."
            )
        else:
            self.connect_button.set_label(
                "Connect" if not self.device.connected else "Disconnect"
            )
        return


class BluetoothConnections(BaseDiWidget, Box):
    """Widget to display connected and available Bluetooth devices."""

    focuse_kb: bool = True

    def __init__(self):
        Box.__init__(self, name="bluetooth", spacing=8, orientation="vertical")

        bluetooth_client.connect("device-added", self.on_device_added)
        bluetooth_client.connect("notify::enabled", self.on_enabled)
        bluetooth_client.connect("notify::scanning", self.on_scanning)

        self.scan_button = Button(
            name="bluetooth-scan",
            label="Scan",
            on_clicked=lambda *_: bluetooth_client.toggle_scan(),
        )
        setup_cursor_hover(self.scan_button)
        self.toggle_button = Button(
            name="bluetooth-toggle",
            label="OFF",
            on_clicked=lambda *_: bluetooth_client.toggle_power(),
        )
        setup_cursor_hover(self.toggle_button)

        self.paired_box = Box(spacing=2, orientation="vertical")
        self.available_box = Box(spacing=2, orientation="vertical")

        self.children = [
            CenterBox(
                name="bluetooth-controls",
                start_children=self.scan_button,
                center_children=Label(name="bluetooth-text", label="Bluetooth Devices"),
                end_children=self.toggle_button,
            ),
            ScrolledWindow(min_content_size=(-1, -1), child=self.paired_box),
            ScrolledWindow(min_content_size=(-1, -1), child=self.available_box),
        ]

    def on_enabled(self, *_):
        if bluetooth_client.enabled:
            self.toggle_button.set_label("Enabled")
            self.toggle_button.add_style_class("enabled")
            self.toggle_button.remove_style_class("disabled")
        else:
            self.toggle_button.set_label("Disabled")
            self.toggle_button.add_style_class("disabled")
            self.toggle_button.remove_style_class("enabled")

    def on_scanning(self, *_):
        if bluetooth_client.scanning:
            self.scan_button.set_label("Stop scanning")
        else:
            self.scan_button.set_label("Scan")

    def on_device_added(self, client: BluetoothClient, address: str):
        if not (device := client.get_device(address)):
            return

        slot = BluetoothDeviceSlot(device)

        if device.paired:
            return self.paired_box.add(slot)

        return self.available_box.add(slot)
