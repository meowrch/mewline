import subprocess
from collections.abc import Callable
from threading import Lock
from typing import Literal

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


class BaseNetworkSlot(CenterBox):
    """Базовый класс для сетевых слотов (WiFi и Ethernet)."""

    def __init__(self, network_info: dict, parent, **kwargs):
        super().__init__(
            orientation="horizontal", spacing=8, name="network-slot", **kwargs
        )
        self.network_info = network_info
        self.parent = parent
        self.interface = self._get_interface()
        self.is_expanded = False
        self.password_entry = None
        self.is_saved = self._is_saved_connection()

        # Основные элементы
        self.icon = text_icon(self._get_icon_name(), size="16px")
        self.name_label = Label(label=self._get_display_name(), h_expand=True)
        self.connect_button = self._create_connect_button()

        # Главный контейнер
        self.main_box = Box(
            orientation="horizontal", spacing=10, children=[self.icon, self.name_label]
        )

        # Контейнер для кнопок
        self.buttons_box = Box(spacing=4, h_align="end")
        if self.is_saved:
            self._add_forget_button()
        self.buttons_box.add(self.connect_button)

        self.add_end(self.buttons_box)
        self.add_start(self.main_box)

        if self.is_connected():
            self.set_style_classes("connected")

    def _get_display_name(self) -> str:
        """Возвращает отображаемое имя сети."""
        raise NotImplementedError

    def _get_icon_name(self) -> str:
        """Возвращает имя иконки для сети."""
        raise NotImplementedError

    def _get_interface(self) -> str:
        """Определяет имя интерфейса."""
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
                if dev_type.lower() == self._get_interface_type():
                    return device
            return self._get_fallback_interface()
        except subprocess.CalledProcessError:
            return self._get_fallback_interface()

    def _get_interface_type(self) -> str:
        """Тип интерфейса (wifi/ethernet)."""
        raise NotImplementedError

    def _get_fallback_interface(self) -> str:
        """Интерфейс по умолчанию, если не удалось определить."""
        raise NotImplementedError

    def _is_saved_connection(self) -> bool:
        """Проверяет, сохранено ли соединение."""
        try:
            result = subprocess.run(
                ["nmcli", "-g", "NAME", "connection", "show"],
                capture_output=True,
                text=True,
                check=True,
            )
            return self._get_connection_name() in result.stdout.splitlines()
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to check saved connections: {e.stderr}")
            return False

    def _get_connection_name(self) -> str:
        """Имя соединения для проверки."""
        return self.network_info.get("ssid") or self.network_info.get("name")

    def is_connected(self) -> bool:
        """Проверяет, активно ли соединение."""
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
                    return line.split(":", 1)[1].strip() == self._get_connection_name()
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to check active connections: {e.stderr}")
            return False

    def _create_connect_button(self) -> Button:
        """Создает кнопку подключения/отключения."""
        is_connected = self.is_connected()
        label = "󰌙" if is_connected else "󱘖"

        button = Button(
            label=label,
            name="network-connection-toggle-btn",
            h_align="end",
        )
        button.add_style_class("disconnect" if is_connected else "connect")
        setup_cursor_hover(button)
        button.connect("clicked", self.on_connect_clicked)
        return button

    def on_connect_clicked(self, button):
        """Обработчик клика на кнопку подключения."""
        if self.is_connected():
            self._disconnect()
        elif self.is_saved:
            self._connect()
        elif self._requires_password():
            self._handle_password_connection()
        else:
            self._connect()

    def _requires_password(self) -> bool:
        """Требуется ли пароль для подключения."""
        security = self.network_info.get("security", "")
        return bool(security and security not in ["", "none"])

    def _handle_password_connection(self):
        """Обрабатывает подключение с паролем."""
        if self.password_entry:
            self._hide_password_field()
        else:
            self._show_password_field()

    def _show_password_field(self):
        """Показывает поле для ввода пароля."""
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
        """Скрывает поле для ввода пароля."""
        if hasattr(self, "password_box") and self.password_box.get_parent():
            self.remove(self.password_box)
            del self.password_box
            self.password_entry = None

    def _connect(self, password: str | None = None):
        """Подключается к сети."""
        self.parent._show_temporary_status("Connecting...")

        def run_connect():
            try:
                cmd = self._build_connect_command(password)
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

    def _build_connect_command(self, password: str | None) -> list[str]:
        """Строит команду для подключения."""
        if self.is_saved:
            return ["nmcli", "connection", "up", "id", self._get_connection_name()]
        elif password:
            return [
                "nmcli",
                "device",
                "wifi",
                "connect",
                self._get_connection_name(),
                "password",
                password,
            ]
        return ["nmcli", "device", "wifi", "connect", self._get_connection_name()]

    def _on_connect_success(self):
        """Обработчик успешного подключения."""
        self._hide_password_field()
        self.parent._show_temporary_status("Connected!", 2000)
        self.parent.queue_refresh()

    def _on_connect_error(self, error):
        """Обработчик ошибки подключения."""
        logger.error(f"Failed to connect: {error.stderr}")
        self.parent._show_temporary_status("Connection failed!", 2000)
        subprocess.run(
            [
                "notify-send",
                "Connection Failed",
                f"Failed to connect to {self._get_connection_name()}",
            ]
        )

    def _disconnect(self):
        """Отключается от сети."""
        self.parent._show_temporary_status("Disconnecting...")

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
        """Обработчик успешного отключения."""
        self.parent._show_temporary_status("Disconnected", 2000)
        self.parent.queue_refresh()

    def _on_disconnect_error(self, error):
        """Обработчик ошибки отключения."""
        logger.error(f"Failed to disconnect: {error.stderr}")
        self.parent._show_temporary_status("Disconnect failed!", 2000)

    def _add_forget_button(self):
        """Добавляет кнопку 'Забыть сеть'."""
        self.forget_button = Button(
            label="󰧧",
            name="network-forget-btn",
            tooltip_text="Forget network",
        )
        setup_cursor_hover(self.forget_button)
        self.forget_button.connect("clicked", self._forget_network)
        self.buttons_box.add(self.forget_button)

    def _forget_network(self, _):
        """Забывает сохраненную сеть."""
        self.parent._show_temporary_status("Forgetting...")

        def run_forget():
            try:
                subprocess.run(
                    [
                        "nmcli",
                        "connection",
                        "delete",
                        "id",
                        self._get_connection_name(),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                GLib.idle_add(self._on_forget_success)
            except subprocess.CalledProcessError as e:
                GLib.idle_add(self._on_forget_error, e)

        GLib.Thread.new(None, run_forget)

    def _on_forget_success(self):
        """Обработчик успешного забытия сети."""
        self.parent._show_temporary_status("Network forgotten", 2000)
        self.is_saved = False
        self.parent.queue_refresh()

    def _on_forget_error(self, error):
        """Обработчик ошибки забытия сети."""
        logger.error(f"Failed to forget network: {error.stderr}")
        self.parent._show_temporary_status("Failed to forget!", 2000)


class WifiNetworkSlot(BaseNetworkSlot):
    """Слот для WiFi сети."""

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

    def _get_display_name(self) -> str:
        return self.network_info["ssid"]

    def _get_icon_name(self) -> str:
        signal_level = min(int(self.network_info["signal"]) // 25, 3)
        if self._requires_password():
            return self.SECURED_SIGNAL_ICONS[signal_level]
        return self.SIGNAL_ICONS[signal_level]

    def _get_interface_type(self) -> str:
        return "wifi"

    def _get_fallback_interface(self) -> str:
        return "wlan0"


class EthernetNetworkSlot(BaseNetworkSlot):
    """Слот для Ethernet сети."""

    def _get_display_name(self) -> str:
        return self.network_info["name"]

    def _get_icon_name(self) -> str:
        return "󰈀"

    def _get_interface_type(self) -> str:
        return "ethernet"

    def _get_fallback_interface(self) -> str:
        return "eth0"


class NetworkConnections(BaseDiWidget, Box):
    """Виджет для управления сетевыми подключениями."""

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
        self._slots_lock = Lock()
        # Инициализируем кэши с пустыми контейнерами
        self._cached_wifi_slots = Box(orientation="vertical", spacing=4)
        self._cached_ethernet_slots = Box(orientation="vertical", spacing=4)

        self._initialize_ui()
        self._load_both_networks()

    def _initialize_ui(self):
        """Инициализирует UI виджета."""
        self.title_label = Label(style_classes="title", label="Wi-Fi")

        self.view_toggle_button = Button(
            name="network-view-toggle-btn",
            label="󰈀",  # Ethernet icon
            tooltip_text="Switch to Ethernet",
        )
        setup_cursor_hover(self.view_toggle_button)
        self.view_toggle_button.connect("clicked", self._toggle_view)

        self.refresh_button = Button(
            name="network-refresh-btn",
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

    def _execute_network_command(
        self,
        command: str,
        success_msg: str,
        error_msg: str,
        success_callback: Callable | None = None,
        error_callback: Callable | None = None,
    ):
        """Общий метод для выполнения сетевых команд с обработкой статусов."""
        self._show_persistent_status(f"Executing {command}...")

        def run_command():
            try:
                subprocess.run(
                    command.split(), check=True, capture_output=True, text=True
                )
                GLib.idle_add(self._show_temporary_status, success_msg)
                if success_callback:
                    success_callback()
            except subprocess.CalledProcessError as e:
                logger.error(f"{error_msg}: {e.stderr}")
                GLib.idle_add(self._show_temporary_status, f"{error_msg}!", 2000)
                if error_callback:
                    error_callback()
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
            except Exception as e:
                logger.error(f"Initial load failed: {e}")
                GLib.idle_add(self._show_temporary_status, "Load failed!", 2000)

        GLib.Thread.new(None, load_networks)

    def _toggle_view(self, button):
        """Переключает между WiFi и Ethernet видами."""
        if self._current_view == "wifi":
            self._current_view = "ethernet"
            button.set_label("󰖩")  # WiFi icon
            button.set_tooltip_text("Switch to Wi-Fi")
            self.title_label.set_label("Ethernet")
        else:
            self._current_view = "wifi"
            button.set_label("󰈀")  # Ethernet icon
            button.set_tooltip_text("Switch to Ethernet")
            self.title_label.set_label("Wi-Fi")

        self._switch_cached_slots()

    def _switch_cached_slots(self):
        """Переключает между кэшированными слотами."""
        current_child = self.scrolled_window.get_child()
        new_child = (
            self._cached_wifi_slots
            if self._current_view == "wifi"
            else self._cached_ethernet_slots
        )

        if current_child == new_child:
            return

        if current_child:
            self.scrolled_window.remove(current_child)

        if self._is_wifi_enabled():
            self.scrolled_window.add(new_child)
            self.scrolled_window.show_all()

    def _clear_wifi_cache(self):
        """Очищает кэш Wi-Fi сетей и обновляет отображение."""
        with self._slots_lock:
            self._cached_wifi_slots = Box(orientation="vertical", spacing=4)
            if self._current_view == "wifi":
                GLib.idle_add(self._switch_cached_slots)

    def queue_refresh(self, callback: Callable | None = None):
        """Ставит в очередь обновление сетей."""
        if self._pending_refresh:
            if callback:
                GLib.idle_add(callback)
            return

        self._pending_refresh = True
        GLib.Thread.new(None, self._perform_refresh, callback)

    def _perform_refresh(self, callback: Callable | None = None):
        """Выполняет обновление списка сетей."""
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
            GLib.idle_add(self._show_temporary_status, "Refresh failed!", 2000)
        finally:
            GLib.idle_add(self._finish_refresh, callback)

    def _update_slots_cache(self, networks: list[dict], is_wifi: bool):
        """Асинхронное обновление кэша слотов с пошаговым добавлением."""

        def create_slots():
            with self._slots_lock:
                # Создаем новый пустой контейнер
                new_cache = Box(orientation="vertical", spacing=4)

                if is_wifi:
                    self._cached_wifi_slots = new_cache
                else:
                    self._cached_ethernet_slots = new_cache

                # Сразу показываем пустой контейнер
                if (is_wifi and self._current_view == "wifi") or (
                    not is_wifi and self._current_view == "ethernet"
                ):
                    GLib.idle_add(self._switch_cached_slots)

                if not networks:
                    GLib.idle_add(self._hide_status)
                    return

                # Сортируем сети: сначала подключенные, затем остальные
                connected = [n for n in networks if n.get("in_use")]
                others = [n for n in networks if not n.get("in_use")]
                all_networks = connected + others
                slots = []

                # Создаем все слоты заранее
                for network in all_networks:
                    slot = (
                        WifiNetworkSlot(network, self)
                        if is_wifi
                        else EthernetNetworkSlot(network, self)
                    )
                    slots.append(slot)

                def add_slot_step(index: int):
                    if index < len(slots):
                        new_cache.add(slots[index])
                        new_cache.show_all()

                        GLib.timeout_add(50, add_slot_step, index + 1)
                    else:
                        if (is_wifi and self._current_view == "wifi") or (
                            not is_wifi and self._current_view == "ethernet"
                        ):
                            GLib.idle_add(
                                self._show_temporary_status, "Networks loaded!", 2000
                            )

                GLib.idle_add(add_slot_step, 0)

        GLib.Thread.new(None, create_slots)

    def start_refresh(self, btn):
        """Запускает обновление списка сетей."""
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
            except subprocess.CalledProcessError as e:
                logger.error(f"Load failed: {e.stderr}")
                GLib.idle_add(lambda: self._show_temporary_status("Load failed!"))
            finally:
                GLib.idle_add(lambda: btn.set_sensitive(True))

        GLib.Thread.new(None, run_scan)

    def _get_ethernet_connections(self) -> list[dict]:
        """Получает список Ethernet соединений."""
        try:
            # Получаем все активные Ethernet соединения
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
                            "in_use": bool(device),
                        }
                    )

            # Получаем неактивные Ethernet соединения
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

    def _is_wifi_enabled(self) -> bool:
        """Проверяет, включен ли WiFi."""
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

    def _update_toggle_button_style(self, status: bool | None = None):
        """Обновляет стиль кнопки переключения WiFi."""
        wifi_enabled = self._is_wifi_enabled() if status is None else status

        if wifi_enabled:
            self.toggle_button.set_label("Enabled")
            self.toggle_button.add_style_class("enabled")
            self.toggle_button.remove_style_class("disabled")
            self.refresh_button.set_sensitive(True)
        else:
            self.toggle_button.set_label("Disabled")
            self.toggle_button.add_style_class("disabled")
            self.toggle_button.remove_style_class("enabled")
            self.refresh_button.set_sensitive(False)
            self._clear_wifi_cache()

    def _get_wifi_networks(self) -> list[dict]:
        """Получает список WiFi сетей."""
        if not self._is_wifi_enabled():
            return []

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

    def _finish_refresh(self, callback: Callable | None = None):
        """Завершает процесс обновления."""
        self._pending_refresh = False
        if callback:
            callback()

    def toggle_wifi(self, btn):
        """Переключает состояние WiFi."""
        if self._current_view != "wifi":
            self._show_temporary_status("Not available")
            return

        action = "off" if self._is_wifi_enabled() else "on"

        def if_success():
            # Обновляем интерфейс после успешного переключения
            GLib.idle_add(lambda: self._update_toggle_button_style(action == "on"))
            # Если Wi-Fi был выключен, показываем сообщение
            if action == "off":
                GLib.idle_add(lambda: self._show_temporary_status("Wi-Fi disabled"))

        self._execute_network_command(
            command=f"nmcli radio wifi {action}",
            success_msg=f"Wi-Fi {action}",
            error_msg="Failed to toggle WiFi",
            success_callback=if_success,
        )
