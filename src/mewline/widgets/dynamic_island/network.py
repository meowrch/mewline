import subprocess

from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.entry import Entry
from fabric.widgets.label import Label
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import GLib
from loguru import logger

from mewline.utils.widget_utils import setup_cursor_hover
from mewline.utils.widget_utils import text_icon
from mewline.widgets.dynamic_island.base import BaseDiWidget


class WifiNetworkSlot(CenterBox):
    SIGNAL_ICONS = [  # noqa: RUF012
        "󰤟",  # Уровень 0
        "󰤢",  # Уровень 1
        "󰤥",  # Уровень 2
        "󰤨",  # Уровень 3 (максимальный)
    ]
    SECURED_SIGNAL_ICONS = [  # noqa: RUF012
        "󰤡",  # Уровень 0 с защитой
        "󰤤",  # Уровень 1 с защитой
        "󰤧",  # Уровень 2 с защитой
        "󰤪",  # Уровень 3 с защитой
    ]

    def __init__(self, ap_info: dict, parent, **kwargs):
        super().__init__(
            orientation="horizontal", spacing=8, name="network-slot", **kwargs
        )
        self.ap_info = ap_info
        self.parent = parent
        self.is_expanded = False
        self.password_entry = None
        self.is_saved = self._is_saved_connection()

        # Основные элементы интерфейса
        self.icon = text_icon(self._get_icon_name(), size="16px")
        self.ssid_label = Label(label=self.ap_info["ssid"], h_expand=True)
        self.connect_button = self._create_connect_button()

        # Собираем основной интерфейс
        self.start_box = Box(
            orientation="horizontal",
            spacing=10,
            children=[self.icon, self.ssid_label],
        )

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
        self.buttons_box.add(self.connect_button)

        self.add_start(self.start_box)
        self.add_end(self.buttons_box)

        # Поле для пароля (создается при необходимости)
        self.password_box = None

        if self.is_connected():
            self.set_style_classes("connected")

    def _get_icon_name(self) -> str:
        """Возвращает иконку в зависимости от состояния сети."""
        signal_level = min(int(self.ap_info["signal"]) // 25, 3)
        if self.ap_info.get("security") and self.ap_info["security"] not in [
            "",
            "none",
        ]:
            return self.SECURED_SIGNAL_ICONS[signal_level]
        return self.SIGNAL_ICONS[signal_level]

    def _is_saved_connection(self) -> bool:
        try:
            result = subprocess.run(  # noqa: S603
                ["nmcli", "-g", "NAME", "connection", "show"],  # noqa: S607
                capture_output=True,
                text=True,
                check=True,
            )
            return self.ap_info["ssid"] in result.stdout.splitlines()
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to check saved connections: {e.stderr}")
            return False

    def is_connected(self) -> bool:
        try:
            result = subprocess.run(  # noqa: S603
                ["nmcli", "-t", "-f", "GENERAL.CONNECTION", "device", "show", "wlan0"],  # noqa: S607
                capture_output=True,
                text=True,
                check=True,
            )
            current_connection = None
            for line in result.stdout.splitlines():
                if line.startswith("GENERAL.CONNECTION:"):
                    current_connection = line.split(":", 1)[1].strip()
                    break
            return current_connection == self.ap_info["ssid"]
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to check active connections: {e.stderr}")
            return False

    def _create_connect_button(self) -> Button:
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

    def on_connect_clicked(self, button):
        if self.is_connected():
            self._disconnect()
        elif self.is_saved:
            self._connect()
        elif self.ap_info.get("security") and self.ap_info["security"] not in [
            "",
            "none",
        ]:
            self._show_password_field()
        else:
            self._connect()

    def _show_password_field(self):
        if self.password_box is not None:
            return

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
        )
        setup_cursor_hover(confirm_button)
        confirm_button.connect(
            "clicked", lambda _: self._connect(self.password_entry.get_text())
        )

        self.password_box = Box(
            orientation="horizontal",
            spacing=8,
            children=[self.password_entry, confirm_button],
        )

        # Добавляем поле пароля под основным блоком
        parent = self.get_parent()
        if parent:
            index = parent.get_children().index(self)
            parent.add(self.password_box, index + 1)
            parent.show_all()

    def _hide_password_field(self):
        if self.password_box is None:
            return

        parent = self.password_box.get_parent()
        if parent:
            parent.remove(self.password_box)

        self.password_box = None
        self.password_entry = None

    def _connect(self, password: str | None = None):
        try:
            if self.is_saved:
                subprocess.run(  # noqa: S603
                    ["nmcli", "connection", "up", "id", self.ap_info["ssid"]],  # noqa: S607
                    check=True,
                    capture_output=True,
                    text=True,
                )
            elif password:
                subprocess.run(  # noqa: S603
                    [  # noqa: S607
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
                subprocess.run(  # noqa: S603
                    ["nmcli", "device", "wifi", "connect", self.ap_info["ssid"]],  # noqa: S607
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.is_saved = True

            self._hide_password_field()
            GLib.timeout_add(1000, self.parent.refresh_all_networks)

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to connect: {e.stderr}")
            subprocess.run(  # noqa: S603
                [  # noqa: S607
                    "notify-send",
                    "Connection Failed",
                    f"Failed to connect to {self.ap_info['ssid']}",
                ]
            )

    def _disconnect(self):
        try:
            subprocess.run(  # noqa: S603
                ["nmcli", "device", "disconnect", "wlan0"],  # noqa: S607
                check=True,
                capture_output=True,
                text=True,
            )
            GLib.timeout_add(1000, self.parent.refresh_all_networks)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to disconnect: {e.stderr}")
            subprocess.run(  # noqa: S603
                [  # noqa: S607
                    "notify-send",
                    "Disconnect Failed",
                    "Failed to disconnect from current network",
                ]
            )

    def _forget_network(self, _):
        try:
            subprocess.run(  # noqa: S603
                ["nmcli", "connection", "delete", "id", self.ap_info["ssid"]],  # noqa: S607
                check=True,
                capture_output=True,
                text=True,
            )
            self.is_saved = False
            self.parent.refresh_all_networks()
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to forget network: {e.stderr}")


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

        self.title_label = Label(style_classes="title", label="Wi-Fi")

        # Кнопки управления
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

        # Контейнер для заголовка
        self.header_box = CenterBox(
            name="controls",
            start_children=self.scan_button,
            center_children=self.title_label,
            end_children=self.toggle_button,
        )

        # Контейнер для списка сетей
        self.networks_box = Box(orientation="vertical", spacing=4)
        self.scrolled_window = ScrolledWindow(
            child=self.networks_box,
            min_content_height=200,
            propagate_natural_height=True,
        )

        # Подключаем обработчики
        self.scan_button.connect("clicked", self.start_scan)
        self.toggle_button.connect("clicked", self.toggle_wifi)

        # Собираем основной интерфейс
        self.add(self.header_box)
        self.add(self.scrolled_window)

        # Первоначальное обновление списка сетей
        self.update_networks()

    def _show_status(self, message: str, timeout: int = 3000):
        """Показывает временный статус в заголовке."""
        self.title_label.set_label(message)

        if hasattr(self, "_status_timeout"):
            GLib.source_remove(self._status_timeout)

        self._status_timeout = GLib.timeout_add(timeout, self._hide_status)

    def _hide_status(self):
        """Скрывает статус в заголовке."""
        self.title_label.set_label("Wi-Fi")
        return False

    def _is_wifi_enabled(self) -> bool:
        try:
            result = subprocess.run(  # noqa: S603
                ["nmcli", "-f", "WIFI", "radio"],  # noqa: S607
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

    def _get_wifi_networks(self) -> list[dict]:
        try:
            result = subprocess.run(  # noqa: S603
                [  # noqa: S607
                    "nmcli",
                    "--terse",
                    "--fields",
                    "IN-USE,SSID,SIGNAL,SECURITY",
                    "device",
                    "wifi",
                    "list",
                ],
                capture_output=True,
                text=True,
                check=True,
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

                networks.append(
                    {
                        "ssid": ssid,
                        "signal": signal,
                        "security": security,
                        "in_use": in_use == "*",
                    }
                )

            return networks
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get WiFi networks: {e.stderr}")
            return []

    def start_scan(self, btn):
        """Запускает сканирование сетей с отображением статуса."""
        self._show_status("Scanning networks...")
        btn.set_label("Scanning...")
        btn.set_sensitive(False)

        try:
            subprocess.run(  # noqa: S603
                ["nmcli", "device", "wifi", "rescan"],  # noqa: S607
                check=True,
                capture_output=True,
                text=True,
            )
            GLib.timeout_add(2000, self._complete_scan, btn)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to scan networks: {e.stderr}")
            self._show_status("Scan failed!", 2000)
            btn.set_label("Scan")
            btn.set_sensitive(True)

    def _complete_scan(self, btn):
        """Завершает процесс сканирования."""
        self.update_networks()
        self._show_status("Scan completed", 2000)
        btn.set_label("Scan")
        btn.set_sensitive(True)
        return False

    def toggle_wifi(self, btn):
        """Переключает состояние WiFi с отображением статуса."""
        if self._is_wifi_enabled():
            self._show_status("Disabling Wi-Fi...")
            action = "off"
            success_msg = "Wi-Fi disabled"
        else:
            self._show_status("Enabling Wi-Fi...")
            action = "on"
            success_msg = "Wi-Fi enabled"

        try:
            subprocess.run(  # noqa: S603
                ["nmcli", "radio", "wifi", action],  # noqa: S607
                check=True,
                capture_output=True,
                text=True,
            )
            self._show_status(success_msg, 2000)
            GLib.timeout_add(1000, self._after_toggle)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to toggle WiFi: {e.stderr}")
            self._show_status("Operation failed!", 2000)

    def _after_toggle(self):
        self._update_toggle_button_style()
        self.update_networks()
        return False

    def refresh_all_networks(self):
        """Полностью перезагружает список сетей."""
        self.update_networks()

    def update_networks(self, *_):
        """Обновляет список сетей с сортировкой и разделителем."""
        # Очищаем текущие элементы
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

        # Сортируем сети: подключенная - первая, затем по силе сигнала
        connected_network = None
        other_networks = []

        for network in networks:
            if network.get("in_use"):
                connected_network = network
            else:
                other_networks.append(network)

        # Сортируем по силе сигнала (от сильного к слабому)
        other_networks.sort(key=lambda x: int(x["signal"]), reverse=True)

        # Добавляем подключенную сеть (если есть)
        if connected_network:
            self.networks_box.add(WifiNetworkSlot(connected_network, self))

        # Добавляем остальные сети
        for network in other_networks:
            self.networks_box.add(WifiNetworkSlot(network, self))

        self.show_all()
