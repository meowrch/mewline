import uuid
from typing import Any
from typing import Literal

import gi
from fabric.core.service import Property
from fabric.core.service import Service
from fabric.core.service import Signal
from fabric.utils import bulk_connect
from fabric.utils import exec_shell_command_async
from gi.repository import Gio
from gi.repository import GLib
from loguru import logger

try:
    gi.require_version("NM", "1.0")
    from gi.repository import NM  # type: ignore
except ValueError:
    logger.error("Failed to start network manager")


class Wifi(Service):
    """A service to manage wifi devices."""

    @Signal
    def changed(self) -> None: ...

    @Signal
    def enabled(self) -> bool: ...

    def __init__(self, client: NM.Client, device: NM.DeviceWifi, **kwargs):
        self._client: NM.Client = client
        self._device: NM.DeviceWifi = device
        self._ap: NM.AccessPoint | None = None
        self._ap_signal: int | None = None
        super().__init__(**kwargs)

        self._client.connect(
            "notify::wireless-enabled",
            lambda *args: self.notifier("enabled", args),
        )
        if self._device:
            bulk_connect(
                self._device,
                {
                    "notify::active-access-point": lambda *args: self._activate_ap(),
                    "access-point-added": lambda *args: self.emit("changed"),
                    "access-point-removed": lambda *args: self.emit("changed"),
                    "state-changed": lambda *args: self.ap_update(),
                },
            )
            self._activate_ap()

    def ap_update(self):
        self.emit("changed")
        for sn in [
            "enabled",
            "internet",
            "strength",
            "frequency",
            "access-points",
            "ssid",
            "state",
            "icon-name",
        ]:
            self.notify(sn)

    def _activate_ap(self):
        if self._ap:
            self._ap.disconnect(self._ap_signal)
        self._ap = self._device.get_active_access_point()
        if not self._ap:
            return

        self._ap_signal = self._ap.connect(
            "notify::strength", lambda *args: self.ap_update()
        )  # type: ignore

    def toggle_wifi(self):
        self._client.wireless_set_enabled(not self._client.wireless_get_enabled())

    def scan(self):
        self._device.request_scan_async(
            None,
            lambda device, result: [
                device.request_scan_finish(result),
                self.emit("changed"),
            ],
        )

    def notifier(self, name: str, *args):
        self.notify(name)
        self.emit("changed")
        return

    @Property(bool, "read-write", default_value=False)
    def enabled(self) -> bool:  # type: ignore  # noqa: F811
        return bool(self._client.wireless_get_enabled())

    @enabled.setter
    def enabled(self, value: bool):
        self._client.wireless_set_enabled(value)

    @Property(int, "readable")
    def strength(self):
        return self._ap.get_strength() if self._ap else -1

    @Property(str, "readable")
    def icon_name(self):
        if not self._ap:
            return "network-wireless-disabled-symbolic"

        if self.internet == "activated":
            return {
                80: "network-wireless-signal-excellent-symbolic",
                60: "network-wireless-signal-good-symbolic",
                40: "network-wireless-signal-ok-symbolic",
                20: "network-wireless-signal-weak-symbolic",
                00: "network-wireless-signal-none-symbolic",
            }.get(
                min(80, 20 * round(self._ap.get_strength() / 20)),
                "network-wireless-no-route-symbolic",
            )
        if self.internet == "activating":
            return "network-wireless-acquiring-symbolic"

        return "network-wireless-offline-symbolic"

    @Property(int, "readable")
    def frequency(self):
        return self._ap.get_frequency() if self._ap else -1

    @Property(int, "readable")
    def internet(self):
        return {
            NM.ActiveConnectionState.ACTIVATED: "activated",
            NM.ActiveConnectionState.ACTIVATING: "activating",
            NM.ActiveConnectionState.DEACTIVATING: "deactivating",
            NM.ActiveConnectionState.DEACTIVATED: "deactivated",
        }.get(
            self._device.get_active_connection().get_state(),
            "unknown",
        )

    @Property(object, "readable")
    def access_points(self) -> list[object]:
        points: list[NM.AccessPoint] = self._device.get_access_points()

        def make_ap_dict(ap: NM.AccessPoint):
            return {
                "bssid": ap.get_bssid(),
                "last_seen": ap.get_last_seen(),
                "wpa_flags": ap.get_wpa_flags(),
                "flags": ap.get_flags(),
                "rsn_flags": ap.get_rsn_flags(),
                "ssid": NM.utils_ssid_to_utf8(ap.get_ssid().get_data())
                if ap.get_ssid()
                else "Unknown",
                "active-ap": self._ap,
                "strength": ap.get_strength(),
                "frequency": ap.get_frequency(),
                "icon-name": {
                    80: "network-wireless-signal-excellent-symbolic",
                    60: "network-wireless-signal-good-symbolic",
                    40: "network-wireless-signal-ok-symbolic",
                    20: "network-wireless-signal-weak-symbolic",
                    00: "network-wireless-signal-none-symbolic",
                }.get(
                    min(80, 20 * round(ap.get_strength() / 20)),
                    "network-wireless-no-route-symbolic",
                ),
            }

        return list(map(make_ap_dict, points))

    @Property(str, "readable")
    def ssid(self):
        if not self._ap:
            return "Disconnected"
        ssid = self._ap.get_ssid().get_data()
        return NM.utils_ssid_to_utf8(ssid) if ssid else "Unknown"

    @Property(int, "readable")
    def state(self):
        return {
            NM.DeviceState.UNMANAGED: "unmanaged",
            NM.DeviceState.UNAVAILABLE: "unavailable",
            NM.DeviceState.DISCONNECTED: "disconnected",
            NM.DeviceState.PREPARE: "prepare",
            NM.DeviceState.CONFIG: "config",
            NM.DeviceState.NEED_AUTH: "need_auth",
            NM.DeviceState.IP_CONFIG: "ip_config",
            NM.DeviceState.IP_CHECK: "ip_check",
            NM.DeviceState.SECONDARIES: "secondaries",
            NM.DeviceState.ACTIVATED: "activated",
            NM.DeviceState.DEACTIVATING: "deactivating",
            NM.DeviceState.FAILED: "failed",
        }.get(self._device.get_state(), "unknown")

    @Property(str, "readable")
    def active_bssid(self):
        return self._ap.get_bssid() if self._ap else None

    def connect_to_ap(self, ap: dict, password: str | None = None):
        """Новый метод для подключения к точке доступа."""
        if not self._client:
            return

        ssid = ap.get("ssid")
        bssid = ap.get("bssid")

        # Пытаемся использовать родной метод подключения
        try:
            connection = NM.SimpleConnection.new()

            # Настройки WiFi
            s_wifi = NM.SettingWireless.new()
            s_wifi.props.ssid = GLib.Bytes.new(ssid.encode("utf-8"))
            s_wifi.props.mode = "infrastructure"
            s_wifi.props.bssid = bssid

            # Настройки подключения
            s_conn = NM.SettingConnection.new()
            s_conn.props.uuid = NM.utils_uuid_generate()
            s_conn.props.id = ssid

            # Настройки безопасности
            s_wsec = NM.SettingWirelessSecurity.new()
            if ap.get("wpa_flags", 0) > 0:
                s_wsec.props.key_mgmt = "wpa-psk"
                s_wsec.props.psk = password

            connection.add_setting(s_wifi)
            connection.add_setting(s_conn)
            if ap.get("wpa_flags", 0) > 0:
                connection.add_setting(s_wsec)

            self._client.add_and_activate_connection_async(
                connection,
                self._device,
                None,
                None,
                self._on_connection_activated,
            )
        except Exception as e:
            logger.error(f"Native connection failed: {e}")
            # Fallback на nmcli
            self._client.connect_wifi_bssid(bssid, password)

    def _on_connection_activated(self, client, result):
        try:
            client.add_and_activate_connection_finish(result)
            logger.info("Connection activated successfully")
        except Exception as e:
            logger.error(f"Connection activation failed: {e}")


class Ethernet(Service):
    """A service to manage ethernet devices."""

    @Signal
    def changed(self) -> None: ...

    @Signal
    def enabled(self) -> bool: ...

    @Property(int, "readable")
    def speed(self) -> int:
        return self._device.get_speed()

    @Property(str, "readable")
    def internet(self) -> str:
        return {
            NM.ActiveConnectionState.ACTIVATED: "activated",
            NM.ActiveConnectionState.ACTIVATING: "activating",
            NM.ActiveConnectionState.DEACTIVATING: "deactivating",
            NM.ActiveConnectionState.DEACTIVATED: "deactivated",
        }.get(
            self._device.get_active_connection().get_state(),
            "disconnected",
        )

    @Property(str, "readable")
    def icon_name(self) -> str:
        network = self.internet
        if network == "activated":
            return "network-wired-symbolic"

        elif network == "activating":
            return "network-wired-acquiring-symbolic"

        elif self._device.get_connectivity != NM.ConnectivityState.FULL:
            return "network-wired-no-route-symbolic"

        return "network-wired-disconnected-symbolic"

    def __init__(self, client: NM.Client, device: NM.DeviceEthernet, **kwargs) -> None:
        super().__init__(**kwargs)
        self._client: NM.Client = client
        self._device: NM.DeviceEthernet = device

        for name in (
            "active-connection",
            "icon-name",
            "internet",
            "speed",
            "state",
        ):
            self._device.connect(f"notify::{name}", lambda *_: self.notifier(name))  # noqa: B023

    def notifier(self, name: str) -> None:
        self.notify(name)
        self.emit("changed")


class NetworkClient(Service):
    """A service to manage network devices."""

    @Signal
    def device_ready(self) -> None: ...

    def __init__(self, **kwargs):
        self._client: NM.Client | None = None
        self.wifi_device: Wifi | None = None
        self.ethernet_device: Ethernet | None = None
        self._pending_connections = {}
        self._active_connections = {}
        super().__init__(**kwargs)
        NM.Client.new_async(
            cancellable=None,
            callback=self._init_network_client,
            **kwargs,
        )

    def _init_network_client(self, client: NM.Client, task: Gio.Task, **kwargs):
        self._client = client
        wifi_device: NM.DeviceWifi | None = self._get_device(NM.DeviceType.WIFI)
        ethernet_device: NM.DeviceEthernet | None = self._get_device(
            NM.DeviceType.ETHERNET
        )

        if wifi_device:
            self.wifi_device = Wifi(self._client, wifi_device)
            self.emit("device-ready")

        if ethernet_device:
            self.ethernet_device = Ethernet(client=self._client, device=ethernet_device)
            self.emit("device-ready")

        self.notify("primary-device")

    def _get_device(self, device_type) -> Any:
        devices: list[NM.Device] = self._client.get_devices()
        return next(
            (
                x
                for x in devices
                if x.get_device_type() == device_type
                and x.get_active_connection() is not None
            ),
            None,
        )

    def _get_primary_device(self) -> Literal["wifi", "wired"] | None:
        if not self._client:
            return None

        if self._client.get_primary_connection() is None:
            return "wifi"
        return (
            "wifi"
            if "wireless"
            in str(self._client.get_primary_connection().get_connection_type())
            else "wired"
            if "ethernet"
            in str(self._client.get_primary_connection().get_connection_type())
            else None
        )

    @Property(str, "readable")
    def primary_device(self) -> Literal["wifi", "wired"] | None:
        return self._get_primary_device()

    def connect_wifi(self, ssid: str, password: str | None = None):
        """Подключается к WiFi сети с указанными параметрами."""  # noqa: RUF002
        if not self._client:
            logger.error("Network client not initialized")
            return

        # Сохраняем ссылки на объекты
        connection = NM.SimpleConnection.new()
        connection_ref = connection  # Сохраняем ссылку

        # Настройка беспроводного устройства
        s_wifi = NM.SettingWireless.new()
        s_wifi.props.ssid = GLib.Bytes.new(ssid.encode("utf-8"))
        s_wifi.props.mode = "infrastructure"

        # Настройка подключения
        s_conn = NM.SettingConnection.new()
        s_conn.props.uuid = str(uuid.uuid4())
        s_conn.props.id = ssid
        s_conn.props.type = "802-11-wireless"

        # Настройка безопасности
        s_wsec = None
        if password:
            s_wsec = NM.SettingWirelessSecurity.new()
            s_wsec.props.key_mgmt = "wpa-psk"
            s_wsec.props.psk = password

        # Собираем все настройки
        connection.add_setting(s_wifi)
        connection.add_setting(s_conn)
        if s_wsec:
            connection.add_setting(s_wsec)

        # Находим устройство
        device = next(
            (
                d
                for d in self._client.get_devices()
                if isinstance(d, NM.DeviceWifi)
                and d.get_state() != NM.DeviceState.UNKNOWN
            ),
            None,
        )

        if not device:
            logger.error("No suitable WiFi device found")
            return

        def add_activate_callback(client, result, data):
            try:
                # Получаем активное соединение
                active_conn = client.add_and_activate_connection_finish(result)
                logger.info(f"Successfully connected to {ssid}")
                # Сохраняем ссылку на активное соединение
                self._active_connections[ssid] = active_conn
            except GLib.Error as e:
                logger.error(f"Connection failed: {e.message}")

        # Используем единый метод для добавления и активации
        self._client.add_and_activate_connection_async(
            connection,
            device,
            None,  # specific_object
            None,  # cancellable
            add_activate_callback,
            None,  # user_data
        )

        # Явно сохраняем объекты
        self._pending_connections[ssid] = {
            "connection": connection_ref,
            "device": device,
        }

    def connect_wifi_bssid(self, bssid: str, password: str | None = None):
        """Альтернативный метод подключения через BSSID."""
        command = ["nmcli", "device", "wifi", "connect", bssid]
        if password:
            command += ["password", password]

        exec_shell_command_async(command)

    def _on_connection_activated(self, client, result):
        try:
            client.add_and_activate_connection_finish(result)
            logger.info("Successfully activated connection")
        except GLib.Error as e:
            logger.error(f"Activation failed: {e.message}")
            # Fallback на nmcli
            self._fallback_nmcli_connection()

    def get_saved_connections(self) -> list[str]:
        """Возвращает список SSID сохраненных сетей."""
        if not self._client:
            return []
        return [
            conn.get_id()
            for conn in self._client.get_connections()
            if isinstance(conn.get_setting_wireless(), NM.SettingWireless)
        ]

    def forget_network(self, ssid: str):
        """Удаляет сохраненную сеть."""
        conn = next(
            (c for c in self._client.get_connections() if c.get_id() == ssid), None
        )
        if conn:
            conn.delete_async(
                None, lambda src, res: logger.info(f"Network {ssid} deleted")
            )
