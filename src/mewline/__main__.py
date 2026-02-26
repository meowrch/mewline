import argparse
import os
import sys

import setproctitle
from fabric import Application
from fabric.utils import monitor_file
from loguru import logger

from mewline import constants as cnst
from mewline.config import cfg
from mewline.config import change_hypr_config
from mewline.config import generate_default_config
from mewline.config import load_config
from mewline.utils.capture_output import start_output_capture
from mewline.utils.glib_debug import enable_all_glib_debug
from mewline.utils.setup_loguru import setup_loguru
from mewline.utils.temporary_fixes import *  # noqa: F403
from mewline.utils.theming import copy_theme
from mewline.utils.theming import process_and_apply_css
from mewline.utils.window_manager import WindowManagerContext
from mewline.utils.window_manager import create_monitor_manager
from mewline.utils.window_manager import detect_window_manager
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

    ##===> Detect and set window manager context
    ##############################
    wm = detect_window_manager()
    WindowManagerContext.set_wm(wm)
    logger.info(f"Window manager detected and context set to: {wm.value}")

    ##===> Creating App
    ##############################
    widgets = []
    osd_widget = None

    if cfg.options.screen_corners:
        widgets.append(ScreenCorners())

    if cfg.options.osd_enabled:
        osd_widget = OSDContainer()
        widgets.append(osd_widget.window)

    ##=> Multi-monitor: create one StatusBar + one DynamicIsland per output
    ###########################################################################
    monitors = create_monitor_manager()
    monitor_ids = monitors.get_configured_gdk_monitor_ids(cfg)

    if not monitor_ids:
        # Fallback: let the compositor/WM decide (show on all outputs)
        logger.warning(
            "[monitors] Could not resolve any monitor IDs - "
            "falling back to monitor=None (compositor/WM default)."
        )
        monitor_ids = [None]

    logger.info(f"[monitors] mode={cfg.monitors.mode!r}  ids={monitor_ids}")

    ##=> Build (monitor_id -> DynamicIsland) map so the dispatcher can route
    # open/close actions to the island that lives on the cursor's monitor.
    ##########################################################################
    islands: dict[int | None, DynamicIsland] = {}
    for mid in monitor_ids:
        bar = StatusBar(monitor=mid)
        if osd_widget:
            bar.set_osd_widget(osd_widget)
        island = DynamicIsland(monitor=mid)
        widgets.append(bar)
        widgets.append(island.window)
        islands[mid] = island

    ##==>
    # Register application-level DI actions ONCE as a cursor-aware
    # dispatcher.  Each DynamicIsland no longer registers these actions
    # itself to avoid "already registered" errors in multi-monitor mode.
    ##########################################################################
    def _get_active_island() -> DynamicIsland:
        """Return the island whose monitor currently holds the pointer."""
        cursor_mid = monitors.get_cursor_gdk_monitor_id()
        # Exact match -> fallback to first island if cursor monitor is unknown
        return islands.get(cursor_mid) or next(iter(islands.values()))

    Application.action("dynamic-island-open")(
        lambda widget="date-notification": _get_active_island().open(widget)
    )
    Application.action("dynamic-island-close")(
        lambda: _get_active_island().close()
    )

    app = Application(cnst.APPLICATION_NAME, *widgets)

    setproctitle.setproctitle(cnst.APPLICATION_NAME)
    cnst.APP_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    cnst.DIST_FOLDER.mkdir(parents=True, exist_ok=True)

    ##==> Theming
    ##############################
    copy_theme(path=cnst.APP_THEMES_FOLDER / (cfg.theme.name + ".scss"))

    # Recompile and apply CSS whenever style files change
    main_css_file = monitor_file(str(cnst.STYLES_FOLDER))
    main_css_file.connect("changed", lambda *_: process_and_apply_css(app))

    # Monitor config.json to hot-swap theme on change
    current_theme = cfg.theme.name
    config_file = monitor_file(str(cnst.APP_CONFIG_PATH))

    def _on_config_changed(*_):
        nonlocal current_theme
        try:
            new_cfg = load_config(cnst.APP_CONFIG_PATH)
            new_theme = new_cfg.theme.name
        except Exception:
            return

        if new_theme != current_theme:
            current_theme = new_theme
            copy_theme(path=cnst.APP_THEMES_FOLDER / (new_theme + ".scss"))
            # CSS will be recompiled by the styles monitor above

    config_file.connect("changed", _on_config_changed)

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
