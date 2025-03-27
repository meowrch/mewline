import subprocess
from threading import Lock

from fabric.utils import exec_shell_command_async
from gi.repository import GLib
from loguru import logger

import mewline.constants as cnst
from mewline.config import cfg
from mewline.shared.widget_container import ButtonWidget
from mewline.utils.widget_utils import text_icon


class NetworkStatus(ButtonWidget):
    """Виджет для отображения статуса Wi-Fi соединения."""

    def __init__(self, **kwargs):
        super().__init__(name="wifi-status", **kwargs)
        self.config = cfg.modules.power
        self._update_lock = Lock()

        self.set_tooltip_text("Wi-Fi Status")
        self._set_loading_icon()  # Временная иконка загрузки

        # Первоначальное обновление
        self._async_update_icon()

        # Обновляем статус при клике
        self.connect(
            "clicked",
            lambda *_: exec_shell_command_async(
                cnst.kb_di_open.format(module="network")
            ),
        )

        # Автообновление
        GLib.timeout_add_seconds(3, self._async_update_icon)

    def _set_loading_icon(self):
        """Устанавливает временную иконку загрузки."""
        self.children = text_icon(
            "󱛄",
            "16px",
            style_classes="panel-text-icon",
        )

    def _async_update_icon(self):
        """Запускает асинхронное обновление иконки."""
        if self._update_lock.locked():
            return False

        with self._update_lock:
            GLib.Thread.new(None, self._update_icon_thread)

        return True

    def _update_icon_thread(self):
        """Поток для получения состояния сети и обновления иконки."""
        try:
            state = self._get_wifi_state()
            signal = self._get_signal_strength() if state == "connected" else 0

            GLib.idle_add(self._apply_icon_update, state, signal)
        except Exception as e:
            logger.error(f"Failed to update wifi status: {e}")
            GLib.idle_add(self._set_error_icon)

    def _apply_icon_update(self, state: str, signal: int):
        """Применяет обновление иконки в основном потоке."""
        if state == "connected":
            if signal > 75:
                icon = "󰤨"
            elif signal > 50:
                icon = "󰤥"
            elif signal > 25:
                icon = "󰤢"
            else:
                icon = "󰤟"
        elif state == "ethernet":
            icon = "󰈀"
        else:
            icon = "󰤮"

        self.children = text_icon(
            icon,
            "16px",
            style_classes="panel-text-icon",
        )

    def _set_error_icon(self):
        """Устанавливает иконку ошибки."""
        self.children = text_icon(
            "󱚼",
            "16px",
            style_classes="panel-text-icon error",
        )

    def _get_wifi_state(self) -> str:
        """Возвращает текущее состояние сети (в отдельном потоке)."""
        try:
            # Проверяем состояние Wi-Fi радио
            radio_result = subprocess.run(
                ["nmcli", "-f", "WIFI", "radio"],
                capture_output=True,
                text=True,
                check=True,
            )
            radio_state = radio_result.stdout.strip()

            if "enabled" not in radio_state:
                return "disabled"

            # Проверяем активное соединение
            device_result = subprocess.run(
                ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"],
                capture_output=True,
                text=True,
                check=True,
            )
            active_connection = device_result.stdout

            for line in active_connection.splitlines():
                if not line.strip():
                    continue

                device, dev_type, state = line.split(":")
                if dev_type == "wifi" and state == "connected":
                    return "connected"
                elif dev_type == "ethernet" and state == "connected":
                    return "ethernet"

            return "disconnected"

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get wifi state: {e.stderr}")
            raise

    def _get_signal_strength(self) -> int:
        """Возвращает уровень сигнала текущей Wi-Fi сети (в отдельном потоке)."""
        try:
            wifi_result = subprocess.run(
                ["nmcli", "-t", "-f", "ACTIVE,SIGNAL", "device", "wifi"],
                capture_output=True,
                text=True,
                check=True,
            )
            output = wifi_result.stdout

            for line in output.splitlines():
                if not line.strip():
                    continue

                active, signal = line.split(":")
                if active == "yes":
                    return int(signal)

            return 0
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get signal strength: {e.stderr}")
            raise
