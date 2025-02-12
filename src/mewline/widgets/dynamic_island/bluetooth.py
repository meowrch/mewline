import shlex
import subprocess

from fabric.bluetooth import BluetoothClient
from fabric.bluetooth import BluetoothDevice
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from fabric.widgets.scrolledwindow import ScrolledWindow
from loguru import logger

from mewline import constants as cnst
from mewline.services import bluetooth_client
from mewline.utils.widget_utils import setup_cursor_hover
from mewline.utils.widget_utils import text_icon
from mewline.widgets.dynamic_island.base import BaseDiWidget


class BluetoothDeviceSlot(CenterBox):
    def __init__(
        self, device: BluetoothDevice, paired_box: Box, available_box: Box, **kwargs
    ):
        super().__init__(name="bluetooth-device", **kwargs)
        self.device = device
        self.paired_box = paired_box
        self.available_box = available_box
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
        self.remove_button = Button(
            name="bluetooth-connect",
            child=text_icon("󰧧"),
            on_clicked=lambda *_: self.remove_bluetooth_device(self.device.address),
        )
        setup_cursor_hover(self.remove_button)

        self.device_icon = Image(icon_name=self.device.icon_name + "-symbolic", size=32)
        self.paired_icon = text_icon(
            icon=cnst.icons["bluetooth"]["paired"],
            size="24px",
            style_classes="paired",
            visible=False
        )
        self.start_children = [
            Box(
                spacing=8,
                children=[
                    self.device_icon,
                    self.paired_icon,
                    Label(label=self.device.name),
                ],
            )
        ]
        self.end_children = [
            Box(spacing=8, children=[self.remove_button, self.connect_button])
        ]
        self.device.emit("changed")  # to update display status

    @staticmethod
    def remove_bluetooth_device(mac_address):
        try:
            command = shlex.split(f"bluetoothctl remove {shlex.quote(mac_address)}")

            result = subprocess.run(  # noqa: S603
                command,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                logger.info(f'Device "{mac_address}" removed successfully!')
            else:
                logger.error(f"Error while device removing: {result.stderr}")

        except Exception as e:
            print(f"Error occured: {e}")

    def on_changed(self, *_):
        if self.device.connecting:
            self.connect_button.set_label(
                "Connecting..." if self.device.connecting else "Disconnecting..."
            )
        else:
            self.connect_button.set_label(
                "Connect" if not self.device.connected else "Disconnect"
            )

        if self.device.connected:
            self.paired_icon.set_visible(True)
        if self.device.connected and self in self.available_box:
            self.available_box.remove(self)
            self.paired_box.add(self)

        return


class BluetoothConnections(BaseDiWidget, Box):
    """Widget to display connected and available Bluetooth devices."""

    focuse_kb: bool = True

    def __init__(self):
        Box.__init__(
            self,
            name="bluetooth",
            spacing=8,
            orientation="vertical",
            v_expand=True,
            v_align="start",
        )

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
        self.paired_scroll_box = ScrolledWindow(
            min_content_size=(-1, -1), child=self.paired_box, visible=False
        )
        self.available_box = Box(spacing=2, orientation="vertical")
        self.available_scroll_box = ScrolledWindow(
            min_content_size=(-1, -1), child=self.available_box, visible=False
        )

        self.children = [
            CenterBox(
                orientation="horizontal",
                name="bluetooth-controls",
                start_children=self.scan_button,
                center_children=Label(name="bluetooth-text", label="Bluetooth Devices"),
                end_children=self.toggle_button,
            ),
            self.paired_scroll_box,
            self.available_scroll_box,
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

        logger.info(f'Device "{device.name}" ({device.address}) added.')
        slot = BluetoothDeviceSlot(device, self.paired_box, self.available_box)

        if device.paired:
            self.paired_scroll_box.set_visible(True)
            return self.paired_box.add(slot)

        self.available_scroll_box.set_visible(True)
        return self.available_box.add(slot)
