import subprocess
from typing import Dict
from typing import List
from typing import Optional

from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.entry import Entry
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from fabric.widgets.scrolledwindow import ScrolledWindow
from loguru import logger

from mewline.utils.widget_utils import setup_cursor_hover
from mewline.widgets.dynamic_island.base import BaseDiWidget


class WifiNetworkSlot(CenterBox):
    SIGNAL_ICONS = ["󰤟", "󰤢", "󰤥", "󰤨"]
    SECURED_SIGNAL_ICONS = ["󰤡", "󰤤", "󰤧", "󰤪"]
    WIFI_CONNECTED_ICON = ""

    def __init__(self, ap_info: Dict, **kwargs):
        super().__init__(
            orientation="horizontal", spacing=8, name="network-slot", **kwargs
        )
        self.ap_info = ap_info
        self.is_expanded = False
        self.password_entry = None
        self.is_saved = self._is_saved_connection()

        self.start_children = Box(
            orientation="horizontal",
            spacing=8,
            children=[
                Image(icon_name=self._get_icon_name(), size=24),
                Label(label=ap_info["ssid"], h_expand=True),
            ],
        )
        self.end_children = self._create_buttons()

    def _is_saved_connection(self) -> bool:
        try:
            result = subprocess.run(
                ["nmcli", "-g", "NAME", "connection", "show"],
                capture_output=True,
                text=True,
                check=True,
            )
            return self.ap_info["ssid"] in result.stdout.splitlines()
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to check saved connections: {e.stderr}")
            return False

    def _get_icon_name(self) -> str:
        if self.ap_info.get("in_use"):
            return self.WIFI_CONNECTED_ICON

        signal_level = min(int(self.ap_info["signal"]) // 25, 3)
        if self.ap_info.get("security"):
            return self.SECURED_SIGNAL_ICONS[signal_level]
        return self.SIGNAL_ICONS[signal_level]

    def _create_buttons(self):
        if hasattr(self, "buttons_box"):
            self.end_children.remove(self.buttons_box)

        self.buttons_box = Box(spacing=4, h_align="end")

        if self.is_saved:
            self.forget_button = Button(
                label="󰧧",
                name="network-forget-btn",
                tooltip_text="Forget network",
            )
            setup_cursor_hover(self.forget_button)
            self.forget_button.connect("clicked", self._forget_network)
            self.buttons_box.add(self.forget_button)

        self.connect_button = self._create_connect_button()
        self.buttons_box.add(self.connect_button)

        return self.buttons_box

    def is_connected(self) -> bool:
        try:
            # Получаем активные соединения
            result = subprocess.run(
                ["nmcli", "-t", "-f", "NAME,DEVICE,TYPE", "connection", "show", "--active"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Проверяем, есть ли активное соединение с текущим SSID
            active_connections = result.stdout.splitlines()
            for conn in active_connections:
                if not conn:
                    continue
                name, device, conn_type = conn.split(":", 2)
                if conn_type == "802-11-wireless" and name == self.ap_info["ssid"]:
                    return True
                    
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to check active connections: {e.stderr}")
            return False


    def _create_connect_button(self):
        is_connected = self.is_connected()
        label = "󰌙" if is_connected else "󱘖"

        button = Button(
            label=label,
            name="network-connection-toggle-btn",
            h_align="end",
        )
        button.add_style_class("connect" if is_connected else "disconnect")
        setup_cursor_hover(button)
        button.connect("clicked", self.on_connect_clicked)
        return button

    def _forget_network(self, button):
        try:
            subprocess.run(
                ["nmcli", "connection", "delete", "id", self.ap_info["ssid"]],
                check=True,
                capture_output=True,
                text=True,
            )
            self.is_saved = False
            self._create_buttons()
            self.show_all()
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to forget network: {e.stderr}")

    def on_connect_clicked(self, button):
        if self.is_connected():
            self._disconnect()
        elif self.is_saved:
            self._connect()
        elif self.ap_info.get("security"):
            self.toggle_password_field()
        else:
            self._connect()

    def _connect(self, password: Optional[str] = None):
        try:
            if self.is_saved:
                subprocess.run(
                    ["nmcli", "connection", "up", "id", self.ap_info["ssid"]],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            elif password:
                subprocess.run(
                    [
                        "nmcli",
                        "device",
                        "wifi",
                        "connect",
                        self.ap_info["ssid"],
                        "password",
                        password,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.is_saved = True
            else:
                subprocess.run(
                    ["nmcli", "device", "wifi", "connect", self.ap_info["ssid"]],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.is_saved = True

            self._update_ui()
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to connect: {e.stderr}")

    def _disconnect(self):
        try:
            subprocess.run(
                ["nmcli", "device", "disconnect", "wlan0"],
                check=True,
                capture_output=True,
                text=True,
            )
            self._update_ui()
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to disconnect: {e.stderr}")

    def toggle_password_field(self):
        if self.password_entry is None:
            self._create_password_fields()
        else:
            self._remove_password_fields()

        self.is_expanded = not self.is_expanded
        self.show_all()

    def _create_password_fields(self):
        self.password_entry = Entry(
            placeholder="Enter password",
            visibility=False,
            name="wifi-password-entry",
            margin_start=32,
            h_align="fill",
            h_expand=True,
        )
        confirm_button = Button(
            label="Confirm",
            name="wifi-confirm-btn",
            on_clicked=lambda _: self._connect(self.password_entry.get_text()),
        )
        setup_cursor_hover(confirm_button)

        self.controls_box = Box(
            spacing=8, children=[self.password_entry, confirm_button]
        )
        self.add(self.controls_box)

    def _remove_password_fields(self):
        if hasattr(self, "controls_box"):
            self.remove(self.controls_box)
            self.password_entry = None

    def _update_ui(self):
        self._create_buttons()
        if self.password_entry:
            self._remove_password_fields()
        self.show_all()


class NetworkConnections(BaseDiWidget, Box):
    focuse_kb = True

    def __init__(self, **kwargs):
        Box.__init__(
            self,
            orientation="vertical",
            spacing=8,
            name="network",
            **kwargs,
        )

        self.scan_button = Button(
            name="network-scan-btn",
            label="Scan",
            sensitive=self._is_wifi_enabled(),
        )
        setup_cursor_hover(self.scan_button)

        self.toggle_button = Button(
            name="network-toggle-btn",
            label="Enabled" if self._is_wifi_enabled() else "Disabled",
        )
        setup_cursor_hover(self.toggle_button)
        self._update_toggle_button_style()

        self.networks_box = Box(orientation="vertical", spacing=4)
        self.scrolled_window = ScrolledWindow(
            child=self.networks_box,
            min_content_height=200,
            propagate_natural_height=True,
        )

        self.scan_button.connect("clicked", self.start_scan)
        self.toggle_button.connect("clicked", self.toggle_wifi)

        self.children = [
            CenterBox(
                name="controls",
                start_children=self.scan_button,
                center_children=Label(style_classes="title", label="Wi-Fi"),
                end_children=self.toggle_button,
            ),
            self.scrolled_window,
        ]

        self.update_networks()

    def _is_wifi_enabled(self) -> bool:
        try:
            result = subprocess.run(
                ["nmcli", "-f", "WIFI", "radio"],
                capture_output=True,
                text=True,
                check=True,
            )
            return "enabled" in result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to check WiFi status: {e.stderr}")
            return False

    def _update_toggle_button_style(self):
        if self._is_wifi_enabled():
            self.toggle_button.set_label("Enabled")
            self.toggle_button.add_style_class("enabled")
            self.toggle_button.remove_style_class("disabled")
            self.scan_button.set_sensitive(True)
        else:
            self.toggle_button.set_label("Disabled")
            self.toggle_button.add_style_class("disabled")
            self.toggle_button.remove_style_class("enabled")
            self.scan_button.set_sensitive(False)

    def _get_wifi_networks(self) -> List[Dict]:
        try:
            result = subprocess.run(
                ["nmcli", "--terse", "--fields", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list"],
                capture_output=True,
                text=True,
                check=True
            )
            
            networks = []
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                    
                parts = line.split(":")
                if len(parts) < 4:
                    continue
                    
                in_use, ssid, signal, security = parts[0], parts[1], parts[2], parts[3]
                if not ssid or ssid == "--":
                    continue
                    
                networks.append({
                    "ssid": ssid,
                    "signal": signal,
                    "security": security,
                    "in_use": in_use == "*",
                    "icon-name": self._get_network_icon(in_use, signal, security)
                })
                
            return networks
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get WiFi networks: {e.stderr}")
            return []


    def _get_network_icon(self, in_use: str, signal: str, security: str) -> str:
        if in_use == "*":
            return "network-wireless-connected-symbolic"

        signal_level = min(int(signal) // 25, 3)
        if security and security != "none":
            return "network-wireless-encrypted-symbolic"
        return "network-wireless-signal-good-symbolic"

    def start_scan(self, btn):
        logger.info("Starting scan")
        btn.set_label("Scanning...")

        try:
            subprocess.run(
                ["nmcli", "device", "wifi", "rescan"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.update_networks()
            btn.set_label("Scan")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to scan networks: {e.stderr}")
            btn.set_label("Scan Failed")

    def toggle_wifi(self, btn):
        try:
            if self._is_wifi_enabled():
                subprocess.run(
                    ["nmcli", "radio", "wifi", "off"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            else:
                subprocess.run(
                    ["nmcli", "radio", "wifi", "on"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            self._update_toggle_button_style()
            self.update_networks()
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to toggle WiFi: {e.stderr}")

    def update_networks(self, *_):
        for child in self.networks_box.get_children():
            child.destroy()

        if not self._is_wifi_enabled():
            self.scrolled_window.hide()
            return

        networks = self._get_wifi_networks()
        if not networks:
            self.scrolled_window.hide()
            return

        self.scrolled_window.show()
        for network in networks:
            self.networks_box.add(WifiNetworkSlot(network))

        self.show_all()
