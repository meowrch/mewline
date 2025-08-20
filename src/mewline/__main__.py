import argparse
import os
import sys

import setproctitle
from fabric import Application
from fabric.utils import monitor_file

from mewline import constants as cnst
from mewline.config import cfg
from mewline.config import change_hypr_config
from mewline.config import generate_default_config
from mewline.utils.capture_output import start_output_capture
from mewline.utils.glib_debug import enable_all_glib_debug
from mewline.utils.setup_loguru import setup_loguru
from mewline.utils.temporary_fixes import *  # noqa: F403
from mewline.utils.theming import copy_theme
from mewline.utils.theming import process_and_apply_css
from mewline.widgets import StatusBar
from mewline.widgets.dynamic_island import DynamicIsland
from mewline.widgets.osd import OSDContainer
from mewline.widgets.screen_corners import ScreenCorners

##==> Настраиваем loguru
################################
setup_loguru(
    journal_level="INFO",
    file_level="DEBUG",
    console_level="INFO",
    enable_console=True,
    enable_colors=True,
)


def _log_system_info():
    """Логируем детальную информацию о системе для отладки."""
    import platform

    from loguru import logger

    try:
        logger.info("=== SYSTEM DEBUG INFO ===")
        logger.info(f"Platform: {platform.platform()}")
        logger.info(f"Python: {platform.python_version()}")
        logger.info(f"Architecture: {platform.architecture()}")

        # GTK версии
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gdk
            from gi.repository import Gtk

            logger.info(
                f"GTK Version: {Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}"
            )
            logger.info(
                f"GDK Backend: {Gdk.Display.get_default().get_name() if Gdk.Display.get_default() else 'Unknown'}"
            )
        except Exception as e:
            logger.warning(f"Could not get GTK version info: {e}")

        # Информация о памяти
        try:
            with open("/proc/meminfo") as f:
                meminfo = f.read()
            for line in meminfo.split("\n")[:3]:  # Первые 3 строки
                if line:
                    logger.info(f"Memory: {line}")
        except Exception as e:
            logger.warning(f"Could not read memory info: {e}")

        # Wayland/X11 информация
        try:
            wayland = os.environ.get("WAYLAND_DISPLAY")
            x11 = os.environ.get("DISPLAY")
            logger.info(f"Wayland Display: {wayland or 'Not set'}")
            logger.info(f"X11 Display: {x11 or 'Not set'}")
        except Exception as e:
            logger.warning(f"Could not get display info: {e}")

        logger.info("=== END SYSTEM INFO ===")
    except Exception as e:
        logger.error(f"Error logging system info: {e}")


def create_keybindings():
    change_hypr_config()


def main(debug_mode=False):
    # Включаем автоматический бэктрейс при падениях в debug режиме
    if debug_mode:
        import faulthandler

        faulthandler.enable()

        # Настраиваем обработчик сигналов для детального вывода
        import signal

        def debug_handler(signum, frame):
            import traceback

            print(f"\n💥 SIGNAL {signum} CAUGHT - STACK TRACE:")
            traceback.print_stack(frame)
            faulthandler.dump_traceback()

        signal.signal(signal.SIGSEGV, debug_handler)
        signal.signal(signal.SIGABRT, debug_handler)

    # Устанавливаем переменные окружения для детальной отладки
    if debug_mode or os.environ.get("MEWLINE_DEBUG", "").lower() in (
        "1",
        "true",
        "yes",
    ):
        debug_env = {
            # МАКСИМАЛЬНАЯ GTK/GLib отладка с stack traces
            "G_DEBUG": "fatal-warnings,fatal-criticals,gc-friendly,resident-modules,bind-now-flags",
            "G_SLICE": "debug-blocks,always-malloc",
            "G_MESSAGES_DEBUG": "all",
            # Полная отладка памяти
            "MALLOC_CHECK_": "3",  # максимальные glibc проверки
            "MALLOC_PERTURB_": "42",  # заполнение памяти мусором
            # МАКСИМАЛЬНЫЙ GTK DEBUG со всеми категориями
            "GTK_DEBUG": "all",  # включаем ВСЕ категории отладки GTK
            "GDK_DEBUG": "all",  # включаем ВСЕ категории отладки GDK
            # CSS и стили
            "GTK_CSS_DEBUG": "1",
            # GObject отладка
            "GOBJECT_DEBUG": "objects,signals,instance-count",
            "G_ENABLE_DIAGNOSTIC": "1",
            # Дополнительные переменные для детальной диагностики
            "G_FILENAME_ENCODING": "UTF-8",
            "GSETTINGS_BACKEND": "dconf",
            # Для лучшего stack trace при падениях
            "PYTHONFAULTHANDLER": "1",
            "PYTHONMALLOC": "debug",
        }

        print("🐛 DEBUG MODE ENABLED - Detailed GTK/memory debugging active")
        for key, value in debug_env.items():
            os.environ[key] = value

        # Логируем информацию о системе в debug режиме
        _log_system_info()

        # Включаем детальное GLib логирование с stack traces
        enable_all_glib_debug()
    else:
        # Минимальные настройки для обычного режима
        minimal_debug = {
            "G_DEBUG": "fatal-warnings",  # Оставляем только критичные ошибки
        }
        for key, value in minimal_debug.items():
            os.environ[key] = value

    # Запускаем захват всего вывода (включая GTK сообщения)
    start_output_capture()

    ##===> Creating App
    ##############################
    widgets = []

    if cfg.options.screen_corners:
        widgets.append(ScreenCorners())

    if cfg.options.osd_enabled:
        widgets.append(OSDContainer())

    widgets.extend((StatusBar(), DynamicIsland()))
    app = Application(cnst.APPLICATION_NAME, *widgets, open_inspector=True)

    setproctitle.setproctitle(cnst.APPLICATION_NAME)
    cnst.APP_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    cnst.DIST_FOLDER.mkdir(parents=True, exist_ok=True)

    ##==> Theming
    ##############################
    copy_theme(path=cnst.APP_THEMES_FOLDER / (cfg.theme.name + ".scss"))

    main_css_file = monitor_file(str(cnst.STYLES_FOLDER))
    main_css_file.connect("changed", lambda *_: process_and_apply_css(app))

    process_and_apply_css(app)

    ##==> Run the application
    ##############################
    app.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Mewline: A minimalist status bar for meowrch."
    )
    parser.add_argument(
        "--generate-default-config",
        action="store_true",
        help="Generate a default configuration for mewline",
    )
    parser.add_argument(
        "--create-keybindings",
        action="store_true",
        help="Generating a config for hyprland to use keyboard shortcuts",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable detailed debugging for GTK and memory issues",
    )

    args = parser.parse_args()

    if args.generate_default_config:
        generate_default_config()
        sys.exit(0)
    elif args.create_keybindings:
        create_keybindings()
        sys.exit(0)
    else:
        main(debug_mode=args.debug)
