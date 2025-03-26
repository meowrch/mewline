import subprocess
from typing import Callable
from typing import Dict
from typing import List
from typing import Literal
from typing import Optional

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
        self.interface = self._get_wifi_interface()
        self.is_expanded = False
        self.password_entry = None
        self.is_saved = self._is_saved_connection()

        # Основные элементы
        self.icon = text_icon(self._get_icon_name(), size="16px")
        self.ssid_label = Label(label=self.ap_info["ssid"], h_expand=True)
        self.connect_button = self._create_connect_button()

        # Главный контейнер
        self.main_box = Box(
            orientation="horizontal", spacing=10, children=[self.icon, self.ssid_label]
        )

        # Контейнер для кнопок
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

        self.add_end(self.buttons_box)
        self.add_start(self.main_box)

        if self.is_connected():
            self.set_style_classes("connected")

    def _get_wifi_interface(self) -> str:
        """Определяет имя wifi интерфейса"""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "DEVICE,TYPE", "device", "status"],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                device, dev_type = line.split(":", 1)
                if dev_type.lower() == "wifi":
                    return device
            return "wlan0"  # fallback
        except subprocess.CalledProcessError:
            return "wlan0"  # fallback

    def _get_icon_name(self) -> str:
        signal_level = min(int(self.ap_info["signal"]) // 25, 3)
        if self.ap_info.get("security") and self.ap_info["security"] not in [
            "",
            "none",
        ]:
            return self.SECURED_SIGNAL_ICONS[signal_level]
        return self.SIGNAL_ICONS[signal_level]

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

    def is_connected(self) -> bool:
        if not self.interface:
            return False

        try:
            result = subprocess.run(
                [
                    "nmcli",
                    "-t",
                    "-f",
                    "GENERAL.CONNECTION",
                    "device",
                    "show",
                    self.interface,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in result.stdout.splitlines():
                if line.startswith("GENERAL.CONNECTION:"):
                    return line.split(":", 1)[1].strip() == self.ap_info["ssid"]
            return False
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
            if self.password_entry:
                self._hide_password_field()
            else:
                self._show_password_field()
        else:
            self._connect()

    def _show_password_field(self):
        if hasattr(self, "password_box") and self.password_box is not None:
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

        self.add(self.password_box)
        self.show_all()

    def _hide_password_field(self):
        if hasattr(self, "password_box") and self.password_box.get_parent():
            self.remove(self.password_box)
            del self.password_box
            self.password_entry = None

    def _connect(self, password: str | None = None):
        self.parent._show_status("Connecting...")

        def run_connect():
            try:
                if self.is_saved:
                    cmd = ["nmcli", "connection", "up", "id", self.ap_info["ssid"]]
                elif password:
                    cmd = [
                        "nmcli",
                        "device",
                        "wifi",
                        "connect",
                        self.ap_info["ssid"],
                        "password",
                        password,
                    ]
                else:
                    cmd = ["nmcli", "device", "wifi", "connect", self.ap_info["ssid"]]

                subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                GLib.idle_add(self._on_connect_success)
            except subprocess.CalledProcessError as e:
                GLib.idle_add(self._on_connect_error, e)

        GLib.Thread.new(None, run_connect)

    def _on_connect_success(self):
        self._hide_password_field()
        self.parent._show_status("Connected!", 2000)
        self.parent.queue_refresh()

    def _on_connect_error(self, error):
        logger.error(f"Failed to connect: {error.stderr}")
        self.parent._show_status("Connection failed!", 2000)
        subprocess.run(
            [
                "notify-send",
                "Connection Failed",
                f"Failed to connect to {self.ap_info['ssid']}",
            ]
        )

    def _disconnect(self):
        self.parent._show_status("Disconnecting...")

        def run_disconnect():
            try:
                subprocess.run(
                    ["nmcli", "device", "disconnect", "wlan0"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                GLib.idle_add(self._on_disconnect_success)
            except subprocess.CalledProcessError as e:
                GLib.idle_add(self._on_disconnect_error, e)

        GLib.Thread.new(None, run_disconnect)

    def _on_disconnect_success(self):
        self.parent._show_status("Disconnected", 2000)
        self.parent.queue_refresh()

    def _on_disconnect_error(self, error):
        logger.error(f"Failed to disconnect: {error.stderr}")
        self.parent._show_status("Disconnect failed!", 2000)

    def _forget_network(self, _):
        self.parent._show_status("Forgetting...")

        def run_forget():
            try:
                subprocess.run(
                    ["nmcli", "connection", "delete", "id", self.ap_info["ssid"]],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                GLib.idle_add(self._on_forget_success)
            except subprocess.CalledProcessError as e:
                GLib.idle_add(self._on_forget_error, e)

        GLib.Thread.new(None, run_forget)

    def _on_forget_success(self):
        self.parent._show_status("Network forgotten", 2000)
        self.is_saved = False
        self.parent.queue_refresh()

    def _on_forget_error(self, error):
        logger.error(f"Failed to forget network: {error.stderr}")
        self.parent._show_status("Failed to forget!", 2000)


class EthernetNetworkSlot(CenterBox):
    def __init__(self, conn_info: dict, parent, **kwargs):
        super().__init__(
            orientation="horizontal", spacing=8, name="network-slot", **kwargs
        )
        self.conn_info = conn_info
        self.parent = parent
        self.interface = self._get_ethernet_interface()

        # Основные элементы
        self.icon = text_icon("󰈁", size="16px")
        self.name_label = Label(label=self.conn_info["name"], h_expand=True)
        self.connect_button = self._create_connect_button()

        # Главный контейнер
        self.main_box = Box(
            orientation="horizontal", spacing=10, children=[self.icon, self.name_label]
        )

        # Контейнер для кнопок
        self.buttons_box = Box(spacing=4, h_align="end")
        self.buttons_box.add(self.connect_button)

        self.add_end(self.buttons_box)
        self.add_start(self.main_box)

        if self.is_connected():
            self.set_style_classes("connected")

    def _get_ethernet_interface(self) -> str:
        """Определяет имя ethernet интерфейса."""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "DEVICE,TYPE", "device", "status"],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                device, dev_type = line.split(":", 1)
                if dev_type.lower() == "ethernet":
                    return device
            return "eth0"
        except subprocess.CalledProcessError:
            return "eth0"

    def is_connected(self) -> bool:
        if not self.interface:
            return False

        try:
            result = subprocess.run(
                [
                    "nmcli",
                    "-t",
                    "-f",
                    "GENERAL.CONNECTION",
                    "device",
                    "show",
                    self.interface,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in result.stdout.splitlines():
                if line.startswith("GENERAL.CONNECTION:"):
                    return line.split(":", 1)[1].strip() == self.conn_info["name"]
            return False
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
        else:
            self._connect()

    def _connect(self):
        self.parent._show_status("Connecting...")

        def run_connect():
            try:
                subprocess.run(
                    ["nmcli", "connection", "up", "id", self.conn_info["name"]],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                GLib.idle_add(self._on_connect_success)
            except subprocess.CalledProcessError as e:
                GLib.idle_add(self._on_connect_error, e)

        GLib.Thread.new(None, run_connect)

    def _on_connect_success(self):
        self.parent._show_status("Connected!", 2000)
        self.parent.queue_refresh()

    def _on_connect_error(self, error):
        logger.error(f"Failed to connect: {error.stderr}")
        self.parent._show_status("Connection failed!", 2000)

    def _disconnect(self):
        self.parent._show_status("Disconnecting...")

        def run_disconnect():
            try:
                subprocess.run(
                    ["nmcli", "device", "disconnect", self.interface],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                GLib.idle_add(self._on_disconnect_success)
            except subprocess.CalledProcessError as e:
                GLib.idle_add(self._on_disconnect_error, e)

        GLib.Thread.new(None, run_disconnect)

    def _on_disconnect_success(self):
        self.parent._show_status("Disconnected", 2000)
        self.parent.queue_refresh()

    def _on_disconnect_error(self, error):
        logger.error(f"Failed to disconnect: {error.stderr}")
        self.parent._show_status("Disconnect failed!", 2000)


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

        self._pending_refresh = False
        self._current_view: Literal["wifi", "ethernet"] = "wifi"
        # Инициализируем кэши с пустыми контейнерами
        self._cached_wifi_slots = Box(orientation="vertical", spacing=4)
        self._cached_ethernet_slots = Box(orientation="vertical", spacing=4)

        self._initialize_ui()
        self._load_both_networks()

    def _show_persistent_status(self, message: str):
        """Показывает статус, который не исчезнет автоматически."""
        self.title_label.set_label(message)
        if hasattr(self, "_status_timeout"):
            GLib.source_remove(self._status_timeout)
            del self._status_timeout

    def _show_temporary_status(self, message: str, timeout: int = 2000):
        """Показывает временный статус с таймаутом."""
        self._show_persistent_status(message)
        self._status_timeout = GLib.timeout_add(timeout, self._hide_status)

    def _hide_status(self):
        """Скрывает статус, восстанавливая заголовок по умолчанию."""
        default_title = "Wi-Fi" if self._current_view == "wifi" else "Ethernet"
        self.title_label.set_label(default_title)
        return False

    def _execute_network_command(self, command: str, success_msg: str, error_msg: str):
        """Общий метод для выполнения сетевых команд с обработкой статусов."""
        self._show_persistent_status(f"Executing {command}...")

        def run_command():
            try:
                subprocess.run(
                    command.split(), check=True, capture_output=True, text=True
                )
                GLib.idle_add(self._show_temporary_status, success_msg)
            except subprocess.CalledProcessError as e:
                logger.error(f"{error_msg}: {e.stderr}")
                GLib.idle_add(self._show_temporary_status, f"{error_msg}!", 2000)
            finally:
                GLib.idle_add(self.queue_refresh)

        GLib.Thread.new(None, run_command)

    def _load_both_networks(self):
        """Загружает WiFi и Ethernet сети при инициализации."""
        self._show_persistent_status("Loading networks...")

        def load_networks():
            try:
                wifi_networks = self._get_wifi_networks()
                ethernet_networks = self._get_ethernet_connections()

                GLib.idle_add(self._update_slots_cache, wifi_networks, True)
                GLib.idle_add(self._update_slots_cache, ethernet_networks, False)
                GLib.idle_add(self._show_temporary_status, "Networks loaded!", 2000)
            except Exception as e:
                logger.error(f"Initial load failed: {e}")
                GLib.idle_add(self._show_temporary_status, "Load failed!", 2000)

        GLib.Thread.new(None, load_networks)

    def _initialize_ui(self):
        self.title_label = Label(style_classes="title", label="Wi-Fi")

        self.view_toggle_button = Button(
            name="network-view-toggle-btn",
            label="󰈁",  # Ethernet icon
            tooltip_text="Switch to Ethernet",
        )
        setup_cursor_hover(self.view_toggle_button)
        self.view_toggle_button.connect("clicked", self._toggle_view)

        self.refresh_button = Button(
            name="network-scan-btn",
            child=text_icon("󰑓"),
            sensitive=self._is_wifi_enabled(),
        )
        self.toggle_button = Button(
            name="network-toggle-btn",
            label="Enabled" if self._is_wifi_enabled() else "Disabled",
        )
        setup_cursor_hover(self.refresh_button)
        setup_cursor_hover(self.toggle_button)
        self._update_toggle_button_style()

        self.header_box = CenterBox(
            name="controls",
            start_children=Box(
                spacing=10,
                children=[self.view_toggle_button, self.refresh_button],
            ),
            center_children=self.title_label,
            end_children=self.toggle_button,
        )

        self.scrolled_window = ScrolledWindow(
            child=self._cached_wifi_slots,  # По умолчанию показываем WiFi
            min_content_height=200,
            propagate_natural_height=True,
        )

        self.refresh_button.connect("clicked", self.start_refresh)
        self.toggle_button.connect("clicked", self.toggle_wifi)

        self.add(self.header_box)
        self.add(self.scrolled_window)

    def _toggle_view(self, button):
        """Switch between WiFi and Ethernet views."""
        if self._current_view == "wifi":
            self._current_view = "ethernet"
            button.set_label("󰖩")  # WiFi icon
            button.set_tooltip_text("Switch to Wi-Fi")
            self.title_label.set_label("Ethernet")
        else:
            self._current_view = "wifi"
            button.set_label("󰈁")  # Ethernet icon
            button.set_tooltip_text("Switch to Ethernet")
            self.title_label.set_label("Wi-Fi")

        # Мгновенное переключение между кэшированными слотами
        self._switch_cached_slots()

    def _switch_cached_slots(self):
        """Переключает между кэшированными слотами."""
        current_child = self.scrolled_window.get_child()
        new_child = (
            self._cached_wifi_slots
            if self._current_view == "wifi"
            else self._cached_ethernet_slots
        )

        # Если пытаемся установить тот же child - ничего не делаем
        if current_child == new_child:
            return

        # Удаляем текущий child если он есть
        if current_child:
            self.scrolled_window.remove(current_child)

        # Добавляем новый child
        self.scrolled_window.add(new_child)
        self.scrolled_window.show_all()

    def _update_ui_from_cache(self):
        """Обновляет UI из кэшированных данных без нового запроса."""
        networks = (
            self._cached_ethernet_connections
            if self._current_view == "ethernet"
            else self._cached_wifi_networks
        )
        self._update_ui(networks, None)

    def queue_refresh(self, callback: Callable | None = None):
        if self._pending_refresh:
            if callback:
                GLib.idle_add(callback)
            return

        self._pending_refresh = True
        GLib.Thread.new(None, self._perform_refresh, callback)

    def _perform_refresh(self, callback: Callable | None = None):
        try:
            if self._current_view == "wifi":
                networks = self._get_wifi_networks()
                self._update_slots_cache(networks, is_wifi=True)
            else:
                networks = self._get_ethernet_connections()
                self._update_slots_cache(networks, is_wifi=False)

            GLib.idle_add(self._switch_cached_slots)
            if callback:
                GLib.idle_add(callback)
        except Exception as e:
            logger.error(f"Refresh failed: {e!s}")
            GLib.idle_add(self._show_status, "Refresh failed!", 2000)
        finally:
            GLib.idle_add(self._finish_refresh, callback)

    def _update_slots_cache(self, networks: list[dict], is_wifi: bool):
        """Обновляет кэш слотов для указанного типа сетей."""
        new_cache = Box(orientation="vertical", spacing=4)

        if networks:
            connected = [n for n in networks if n.get("in_use")]
            others = [n for n in networks if not n.get("in_use")]

            for network in connected + others:
                slot = (
                    WifiNetworkSlot(network, self)
                    if is_wifi
                    else EthernetNetworkSlot(network, self)
                )
                new_cache.add(slot)

        # Заменяем старый кэш новым
        if is_wifi:
            self._cached_wifi_slots = new_cache
        else:
            self._cached_ethernet_slots = new_cache

        # Если это текущий вид - обновляем отображение
        if (is_wifi and self._current_view == "wifi") or (
            not is_wifi and self._current_view == "ethernet"
        ):
            GLib.idle_add(self._switch_cached_slots)

    def _update_ui(self, networks: list[dict], callback: Callable | None):
        new_networks_box = Box(orientation="vertical", spacing=4)

        if not networks:
            self.scrolled_window.hide()
        else:
            self.scrolled_window.show()
            connected = [n for n in networks if n.get("in_use")]
            others = [n for n in networks if not n.get("in_use")]

            for network in connected + others:
                if self._current_view == "wifi":
                    slot = WifiNetworkSlot(network, self)
                else:
                    slot = EthernetNetworkSlot(network, self)
                new_networks_box.add(slot)

        self.scrolled_window.children = new_networks_box
        self.networks_box = new_networks_box
        self.show_all()
        self._finish_refresh(callback)

    def _get_ethernet_connections(self) -> list[dict]:
        try:
            # Получаем все Ethernet коннекты.
            result = subprocess.run(
                [
                    "nmcli",
                    "-t",
                    "-f",
                    "NAME,DEVICE,TYPE",
                    "connection",
                    "show",
                    "--active",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            connections = []
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue

                name, device, conn_type = line.split(":", 2)
                if conn_type.lower() == "802-3-ethernet":
                    connections.append(
                        {
                            "name": name,
                            "device": device,
                            "in_use": bool(
                                device
                            ),  # Если устройство не пусто, - оно активно
                        }
                    )

            # Также получаем доступные, но неактивные Ethernet-соединения
            result = subprocess.run(
                [
                    "nmcli",
                    "-t",
                    "-f",
                    "NAME,TYPE",
                    "connection",
                    "show",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            # Добавляем только те Ethernet-соединения, которых еще нет в списке.
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue

                name, conn_type = line.split(":", 1)
                if conn_type.lower() == "802-3-ethernet" and not any(
                    c["name"] == name for c in connections
                ):
                    connections.append(
                        {
                            "name": name,
                            "device": "",
                            "in_use": False,
                        }
                    )

            return connections
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get Ethernet connections: {e.stderr}")
            return []

    def _show_status(self, message: str, timeout: int = 3000):
        """Показывает временный статус в заголовке."""
        self.title_label.set_label(message)

        if hasattr(self, "_status_timeout"):
            GLib.source_remove(self._status_timeout)

        self._status_timeout = GLib.timeout_add(timeout, self._hide_status)

    def _hide_status(self):
        """Скрывает статус в заголовке."""
        if self._current_view == "wifi":
            self.title_label.set_label("Wi-Fi")
        else:
            self.title_label.set_label("Ethernet")
        return False

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
            self.refresh_button.set_sensitive(True)
        else:
            self.toggle_button.set_label("Disabled")
            self.toggle_button.add_style_class("disabled")
            self.toggle_button.remove_style_class("enabled")
            self.refresh_button.set_sensitive(False)

    def _get_wifi_networks(self) -> list[dict]:
        try:
            result = subprocess.run(
                [
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

    def _finish_refresh(self, callback: Callable | None):
        self._pending_refresh = False
        if callback:
            callback()

    def start_refresh(self, btn):
        """Обновляет список сетей"""
        self._show_persistent_status("Loading networks...")
        btn.set_sensitive(False)

        def run_scan():
            try:
                if self._current_view == "wifi":
                    subprocess.run(
                        ["nmcli", "device", "wifi", "rescan"],
                        check=True,
                        capture_output=True,
                        text=True,
                    )

                wifi_networks = self._get_wifi_networks()
                ethernet_networks = self._get_ethernet_connections()

                GLib.idle_add(self._update_slots_cache, wifi_networks, True)
                GLib.idle_add(self._update_slots_cache, ethernet_networks, False)
                GLib.idle_add(lambda: self._show_temporary_status("Networks loaded!"))
            except subprocess.CalledProcessError as e:
                logger.error(f"Load failed: {e.stderr}")
                GLib.idle_add(lambda: self._show_temporary_status("Load failed!"))
            finally:
                GLib.idle_add(lambda: btn.set_sensitive(True))

        GLib.Thread.new(None, run_scan)

    def _on_refresh_success(self, btn):
        btn.set_sensitive(True)
        self._show_status("Networks loaded!!", 2000)

    def _on_refresh_error(self, btn, error):
        logger.error(f"Refresh failed: {error.stderr}")
        btn.set_sensitive(True)
        self._show_status("Load failed!", 2000)

    def toggle_wifi(self, btn):
        """Переключает состояние WiFi"""
        if self._current_view != "wifi":
            self._show_temporary_status("Not available in this view")
            return

        action = "off" if self._is_wifi_enabled() else "on"
        self._execute_network_command(
            command=f"nmcli radio wifi {action}",
            success_msg=f"Wi-Fi {action}",
            error_msg="Failed to toggle WiFi",
        )

    def _on_toggle_success(self, message):
        """Обработчик успешного переключения WiFi."""
        self._show_status(message, 2000)
        self._update_toggle_button_style()
        self.queue_refresh()

    def _on_toggle_error(self, error):
        """Обработчик ошибки переключения WiFi."""
        logger.error(f"Failed to toggle WiFi: {error.stderr}")
        self._show_status("Operation failed!", 2000)

    def refresh_all_networks(self):
        """Триггерит обновление списка сетей."""
        self.queue_refresh()
