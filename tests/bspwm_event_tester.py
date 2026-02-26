#!/usr/bin/env python3
"""Тестовый скрипт для проверки событий bspwm.
Запускает сервис, подписывается на события и генерирует их через bspc команды.
"""  # noqa: D205

import sys
import time

from gi.repository import GLib
from loguru import logger

from mewline.custom_fabric.bspwm.service import Bspwm
from mewline.custom_fabric.bspwm.service import BspwmEvent


class BspwmEventTester:
    """Класс для тестирования событий bspwm."""

    def __init__(self):
        self.received_events = []
        self.connection = None
        self.test_desktop_name = "test_fabric_999"

    def on_report_event(self, service, event: BspwmEvent):
        """Обработчик события report."""
        logger.info(f"Event received: {event.name}")
        logger.info(f"   Raw data: {event.raw_data}")
        logger.info(f"   Parsed monitors: {len(event.data.get('monitors', []))}")

        for monitor in event.data.get("monitors", []):
            logger.info(
                f"   Monitor: {monitor['name']} (focused: {monitor['focused']})"
            )
            for desktop in monitor["desktops"]:
                status = []
                if desktop["focused"]:
                    status.append("FOCUSED")
                if desktop["occupied"]:
                    status.append("OCCUPIED")
                if desktop["urgent"]:
                    status.append("URGENT")
                status_str = ", ".join(status) if status else "EMPTY"
                logger.info(f"      Desktop: {desktop['name']} [{status_str}]")

        self.received_events.append(event)
        logger.success(
            f"Event #{len(self.received_events)} processed successfully\n"
        )

    def run_command(self, cmd: str, description: str):
        """Выполняет bspc команду и ждет обработки события."""
        logger.info(f"\n{description}")
        logger.info(f"   Command: bspc {cmd}")

        result = self.connection.send_command(cmd)
        if result.is_ok:
            logger.success("   Command executed successfully")
        else:
            logger.error(f"   Command failed: {result.output}")

        # Даем время на обработку события
        time.sleep(0.5)
        return result.is_ok

    def test_desktop_focus(self):
        """Тест переключения между рабочими столами."""
        logger.warning("\n" + "=" * 60)
        logger.warning("TEST 1: Desktop Focus Events")
        logger.warning("=" * 60)

        # Получаем список текущих десктопов
        state = self.connection.get_state()
        if not state or not state.get("monitors"):
            logger.error("Failed to get state")
            return False

        desktops = []
        for monitor in state["monitors"]:
            for desktop in monitor["desktops"]:
                desktops.append(desktop["name"])

        if len(desktops) < 2:
            logger.warning("Not enough desktops for focus test, need at least 2")
            return False

        # Переключаемся между первыми двумя десктопами
        self.run_command(
            f"desktop -f {desktops[0]}", f"Switching to desktop {desktops[0]}"
        )
        self.run_command(
            f"desktop -f {desktops[1]}", f"Switching to desktop {desktops[1]}"
        )
        self.run_command(
            f"desktop -f {desktops[0]}", f"Switching back to desktop {desktops[0]}"
        )

        return True

    def test_desktop_add_remove(self):
        """Тест добавления и удаления рабочего стола."""
        logger.warning("\n" + "=" * 60)
        logger.warning("TEST 2: Desktop Add/Remove Events")
        logger.warning("=" * 60)

        # Добавляем тестовый десктоп
        self.run_command(
            f"monitor -a {self.test_desktop_name}",
            f"Adding test desktop '{self.test_desktop_name}'",
        )

        # Переключаемся на него
        self.run_command(
            f"desktop -f {self.test_desktop_name}", "Focusing test desktop"
        )

        # Переключаемся обратно на первый десктоп перед удалением
        state = self.connection.get_state()
        if state and state.get("monitors"):
            first_desktop = state["monitors"][0]["desktops"][0]["name"]
            self.run_command(
                f"desktop -f {first_desktop}", "Switching away from test desktop"
            )

        # Удаляем тестовый десктоп
        self.run_command(
            f"desktop {self.test_desktop_name} -r", "Removing test desktop"
        )

        return True

    def test_window_operations(self):
        """Тест операций с окнами."""
        logger.warning("\n" + "=" * 60)
        logger.warning("TEST 3: Window Events (Manual)")
        logger.warning("=" * 60)

        logger.info("\nManual test instructions:")
        logger.info("   1. Open a new terminal window (should trigger node_add)")
        logger.info("   2. Switch focus between windows (should trigger node_focus)")
        logger.info("   3. Close the window (should trigger node_remove)")
        logger.info("   4. These events will be logged automatically")
        logger.info("\n   Waiting 10 seconds for manual window operations...")

        # Ждем пока пользователь выполнит действия
        time.sleep(10)

        return True

    def test_urgent_flag(self):
        """Тест urgent флага."""
        logger.warning("\n" + "=" * 60)
        logger.warning("TEST 4: Urgent Flag Events")
        logger.warning("=" * 60)

        # Получаем текущий desktop
        state = self.connection.get_state()
        if state and state.get("monitors"):
            focused_desktop = None
            for monitor in state["monitors"]:
                for desktop in monitor["desktops"]:
                    if desktop.get("focused"):
                        focused_desktop = desktop.get("name")
                        break
                if focused_desktop:
                    break

            if focused_desktop:
                # В bspwm urgent это флаг desktop, а не node
                # Проверяем есть ли окно
                result = self.connection.send_command("query -N -n focused")
                if result.is_ok and result.output.strip():
                    node_id = result.output.strip()

                    # Устанавливаем urgent через node state
                    self.run_command(
                        f"node {node_id} -g urgent",
                        "Setting urgent state on focused window",
                    )

                    # Снимаем urgent
                    self.run_command(
                        f"node {node_id} -g urgent=off", "Clearing urgent state"
                    )
                else:
                    logger.warning("No focused window found for urgent test")
                    logger.info("Try opening a window first")
            else:
                logger.warning("No focused desktop found")
        else:
            logger.warning("Failed to get state for urgent test")

        return True

    def run_all_tests(self):
        """Запускает все тесты."""
        try:
            logger.info("\n" + "=" * 60)
            logger.info("Starting Bspwm Event Tester")
            logger.info("=" * 60)

            # Инициализируем подключение
            logger.info("\nInitializing Bspwm connection...")
            self.connection = Bspwm()

            # Подписываемся на события
            self.connection.connect("event::report", self.on_report_event)

            logger.success("Connected to bspwm")
            logger.info(f"   Ready: {self.connection.ready}")

            # Получаем начальное состояние
            state = self.connection.get_state()
            if state:
                logger.info(f"   Monitors: {len(state.get('monitors', []))}")
                total_desktops = sum(
                    len(m["desktops"]) for m in state.get("monitors", [])
                )
                logger.info(f"   Total desktops: {total_desktops}")

            # Ждем немного для инициализации
            time.sleep(1)

            # Запускаем тесты
            self.test_desktop_focus()
            self.test_desktop_add_remove()
            self.test_window_operations()
            self.test_urgent_flag()

            # Итоговая статистика
            logger.warning("\n" + "=" * 60)
            logger.warning("Test Summary")
            logger.warning("=" * 60)
            logger.info(f"Total events received: {len(self.received_events)}")

            # Показываем все raw события
            logger.info("\nAll received raw events:")
            for i, event in enumerate(self.received_events, 1):
                logger.info(f"   {i}. {event.raw_data}")

            logger.success("\nAll tests completed!")
            logger.info("\nPress Ctrl+C to exit...")

            # Продолжаем слушать события
            GLib.MainLoop().run()

        except KeyboardInterrupt:
            logger.info("\n\nExiting...")
        except Exception as e:
            logger.error(f"Error during testing: {e}")
            import traceback

            traceback.print_exc()
            return False

        return True


if __name__ == "__main__":
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="DEBUG",
    )

    tester = BspwmEventTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
