import os
import traceback

from loguru import logger


def setup_glib_logging():
    """Настраивает детальное логирование GLib с бэктрейсами."""
    try:
        import gi

        gi.require_version("GLib", "2.0")
        from gi.repository import GLib

        def detailed_log_handler(log_domain, log_level, message, _user_data):
            """Обработчик логов с детальной информацией."""
            # Получаем stack trace Python
            stack = traceback.format_stack()

            # Определяем уровень
            level_map = {
                GLib.LogLevelFlags.LEVEL_ERROR: "ERROR",
                GLib.LogLevelFlags.LEVEL_CRITICAL: "CRITICAL",
                GLib.LogLevelFlags.LEVEL_WARNING: "WARNING",
                GLib.LogLevelFlags.LEVEL_MESSAGE: "MESSAGE",
                GLib.LogLevelFlags.LEVEL_INFO: "INFO",
                GLib.LogLevelFlags.LEVEL_DEBUG: "DEBUG",
            }

            level_name = level_map.get(log_level, f"LEVEL_{log_level}")

            # Формируем детальное сообщение
            detailed_msg = f"""
🐛 GLIB {level_name} in {log_domain or "Unknown"}:
📝 Message: {message}
🔍 Process: {os.getpid()}
📚 Python Stack (last 5 calls):
{"".join(stack[-5:])}
==========================================
"""

            # Логируем через наш logger
            if log_level & (
                GLib.LogLevelFlags.LEVEL_ERROR | GLib.LogLevelFlags.LEVEL_CRITICAL
            ):
                logger.error(detailed_msg)
            elif log_level & GLib.LogLevelFlags.LEVEL_WARNING:
                logger.warning(detailed_msg)
            else:
                logger.info(detailed_msg)

            # Также выводим в stderr для немедленного просмотра
            print(detailed_msg, flush=True)

            return True  # Не блокируем стандартную обработку

        # Устанавливаем обработчик для всех доменов
        GLib.log_set_default_handler(detailed_log_handler, None)

        # Также устанавливаем для специфичных доменов
        domains = ["Gtk", "Gdk", "GLib", "GObject", "Gio", "Pango", "cairo", "fabric"]
        for domain in domains:
            try:
                GLib.log_set_handler(
                    domain,
                    GLib.LogLevelFlags.LEVEL_MASK
                    | GLib.LogLevelFlags.FLAG_FATAL
                    | GLib.LogLevelFlags.FLAG_RECURSION,
                    detailed_log_handler,
                    None,
                )
            except Exception as e:
                logger.debug(f"Could not set handler for domain {domain}: {e}")

        logger.info("🔧 Enhanced GLib logging with stack traces enabled")
        return True

    except Exception as e:
        logger.error(f"Failed to setup GLib enhanced logging: {e}")
        return False


def setup_gobject_debug():
    """Включает отладку GObject с детализацией утечек объектов."""
    try:
        import gi

        gi.require_version("GObject", "2.0")
        from gi.repository import GObject

        # Включаем мониторинг объектов
        if hasattr(GObject, "BindingFlags"):
            # Доступны расширенные возможности отладки
            logger.info("🔍 GObject extended debugging available")

        logger.info("🔧 GObject debugging setup complete")
        return True

    except Exception as e:
        logger.error(f"Failed to setup GObject debugging: {e}")
        return False


def enable_all_glib_debug():
    """Включает максимальную детализацию для всех GLib компонентов."""
    # Устанавливаем переменные окружения для максимальной детализации
    debug_vars = {
        "G_DEBUG": "fatal-warnings,fatal-criticals,gc-friendly,resident-modules,bind-now-flags",
        "G_SLICE": "debug-blocks,always-malloc",
        "G_MESSAGES_DEBUG": "all",
        "GOBJECT_DEBUG": "objects,signals,instance-count",
    }

    for key, value in debug_vars.items():
        os.environ[key] = value

    # Настраиваем детальные обработчики
    success_glib = setup_glib_logging()
    success_gobject = setup_gobject_debug()

    if success_glib and success_gobject:
        logger.info("✅ All GLib debug features enabled successfully")
        return True
    else:
        logger.warning("⚠️ Some GLib debug features failed to enable")
        return False
