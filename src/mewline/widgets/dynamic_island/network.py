import subprocess

from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.entry import Entry
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from fabric.widgets.scrolledwindow import ScrolledWindow
from loguru import logger

from mewline.services import network_client
from mewline.services.network import NetworkClient
from mewline.utils.widget_utils import setup_cursor_hover
from mewline.widgets.dynamic_island.base import BaseDiWidget


class WifiNetworkSlot(CenterBox):
    def __init__(self, ap_info: dict, client: NetworkClient, **kwargs):
        super().__init__(
            orientation="horizontal", spacing=8, name="network-slot", **kwargs
        )
        self.ap_info = ap_info
        self.client = client
        self.is_expanded = False
        self.password_entry = None
        self.is_saved = ap_info["ssid"] in self.client.get_saved_connections()

        self.start_children = Box(
            orientation="horizontal",
            spacing=8,
            children=[
                Image(icon_name=ap_info["icon-name"], size=24),
                Label(label=ap_info["ssid"], h_expand=True),
            ],
        )
        self.end_children = self._create_buttons()

    def _create_buttons(self):
        # Удаляем старые кнопки
        if hasattr(self, "buttons_box"):
            self.end_children.remove(self.buttons_box)

        # Группировка для кнопок
        self.buttons_box = Box(spacing=4, h_align="end")

        # Кнопка "Забыть" для сохраненных сетей
        if self.is_saved:
            self.forget_button = Button(
                label="󰧧",
                name="network-forget-btn",
                tooltip_text="Forget network",
            )
            setup_cursor_hover(self.forget_button)
            self.forget_button.connect("clicked", self._forget_network)
            self.buttons_box.add(self.forget_button)

        # Кнопка подключения/отключения
        self.connect_button = self._create_connect_button()
        self.buttons_box.add(self.connect_button)

        return self.buttons_box

    def is_connected(self) -> bool:
        return (
            self.client.wifi_device
            and self.client.wifi_device.ssid == self.ap_info["ssid"]
        )

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
        self.client.forget_network(self.ap_info["ssid"])
        self.is_saved = False
        self._create_buttons()
        self.show_all()

    def on_connect_clicked(self, button):
        # Если сеть сохранена - подключаемся без пароля
        is_connected = self.is_connected()
        if self.is_saved and not is_connected:
            logger.info("Connect to saved device...")
            self._connect()
            return

        # Остальная логика подключения
        if is_connected:
            logger.info("Disconnecting device...")
            self._disconnect()
        elif self.ap_info["wpa_flags"] > 0:
            logger.info("Connect to secure device... Input the password...")
            self.toggle_password_field()
        else:
            logger.info("Connect to not secure device...")
            self._connect()

    def _connect(self):
        # Если сеть сохранена - используем автоматическое подключение
        if self.is_saved:
            self.client.connect_wifi_bssid(self.ap_info["bssid"])
            # self.client.connect_wifi(self.ap_info["ssid"]) # работает очень медленно
        else:
            # Логика с вводом пароля  # noqa: RUF003
            password = self.password_entry.get_text() if self.password_entry else None
            self.client.connect_wifi(self.ap_info["ssid"], password)

        self._update_ui()

    def _disconnect(self):
        try:
            # Используем nmcli для отключения
            subprocess.run(  # noqa: S603
                ["nmcli", "device", "disconnect", "wlan0"],  # noqa: S607
                check=True,
                capture_output=True,
                text=True,
            )
            self._update_ui()
        except subprocess.CalledProcessError as e:
            logger.error(f"Disconnect failed: {e.stderr}")

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
        )
        confirm_button = Button(
            label="Confirm",
            name="wifi-confirm-btn",
            on_clicked=lambda _: self._connect(),
        )
        setup_cursor_hover(confirm_button)

        self.controls_box = Box(
            spacing=8,
            children=[self.password_entry, confirm_button],
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
        self.client = network_client

        ##==> Инициализация UI
        ##############################################
        self.scan_button = Button(
            name="network-scan-btn",
            label="Scan",
            sensitive=False,  # выключаем до инициализации network девайса
        )
        setup_cursor_hover(self.scan_button)
        self.toggle_button = Button(
            name="network-toggle-btn",
            label="Disabled",
        )
        setup_cursor_hover(self.toggle_button)
        if self.client.wifi_device:  # Обновляем toggle кнопку
            self.update_toggle_button(self.client.wifi_device.enabled)
        else:
            self.update_toggle_button(False)

        self.networks_box = Box(orientation="vertical", spacing=4)
        self.scrolled_window = ScrolledWindow(
            child=self.networks_box,
            min_content_height=200,
            propagate_natural_height=True,
        )

        ##==> Подписки на сигналы
        ################################################
        self.client.connect("device-ready", self.on_device_ready)
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

    def update_toggle_button(self, wifi_status: bool) -> None:
        if wifi_status:
            self.toggle_button.set_label("Enabled")
            self.toggle_button.add_style_class("enabled")
            self.toggle_button.remove_style_class("disabled")
        else:
            self.toggle_button.set_label("Disabled")
            self.toggle_button.add_style_class("disabled")
            self.toggle_button.remove_style_class("enabled")

    def on_device_ready(self, client: NetworkClient):
        wifi = client.wifi_device
        if not wifi:
            logger.warning("No WiFi device found")
            return

        # Обновляем состояние кнопок
        self.update_toggle_button(wifi.enabled)
        if not wifi.enabled:
            self.scan_button.set_sensitive(False)
        else:
            self.scan_button.set_sensitive(True)

        # Подписываемся на изменения
        wifi.connect("changed", self.update_networks)
        wifi.connect(
            "notify::enabled",
            lambda *args: self.update_toggle_button(wifi.get_property("enabled")),
        )

        self.update_networks()

    def start_scan(self, btn):
        logger.info("Starting scan")
        if self.client.wifi_device:
            self.client.wifi_device.scan()
            self.update_networks()
            btn.set_label("Scanning...")

    def toggle_wifi(self, btn):
        if self.client.wifi_device:
            self.client.wifi_device.toggle_wifi()
            logger.info("Wifi toggled successfully!")
        else:
            logger.warning("Failed to toggle wifi. Wifi device is missing!")

    def update_networks(self, *_):
        # Очищаем текущие элементы
        for child in self.networks_box.get_children():
            child.destroy()

        # Скрываем вывод wifi сетей, если девайс не доступен
        if not self.client.wifi_device or not self.client.wifi_device.enabled:
            self.scrolled_window.hide()
            return

        aps = self.client.wifi_device.access_points
        if not aps:
            self.scrolled_window.hide()
            return

        self.scrolled_window.show()
        for ap in aps:
            if ap["ssid"] == "Unknown":
                continue
            self.networks_box.add(WifiNetworkSlot(ap, self.client))

        self.show_all()
