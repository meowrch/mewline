import os
from pathlib import Path

from loguru import logger
from systemd import journal


def ensure_log_directory():
    """Создаем директорию для логов с правильными правами."""
    # Список возможных директорий для логов в порядке приоритета
    log_dirs = [
        "/var/log/mewline",
        f"{Path.home()}/.local/share/mewline/logs",
        "/tmp/mewline",  # noqa: S108
    ]

    for log_dir in log_dirs:
        log_file = f"{log_dir}/app.log"
        try:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            # Проверяем, можем ли мы создать и записать в файл
            test_file = Path(log_file)
            if not test_file.exists():
                test_file.touch(exist_ok=True)

            # Проверяем права на запись
            if not os.access(log_file, os.W_OK):
                raise PermissionError(f"No write access to: {log_file}")

            return log_file
        except (PermissionError, OSError) as e:
            logger.debug(f"Cannot use {log_dir}: {e}")
            continue

    # Если все варианты не удались, используем /tmp
    fallback_file = "/tmp/mewline_app.log"  # noqa: S108
    logger.warning(f"Failed to create log directory, using fallback: {fallback_file}")
    return fallback_file


def disable_logging():
    """Отключаем избыточные логи от сторонних библиотек."""
    for log in [
        "fabric.hyprland.widgets",
        "fabric.audio.service",
        "fabric.bluetooth.service",
    ]:
        logger.disable(log)


def setup_loguru(
    journal_level: str = "INFO",
    file_level: str = "DEBUG",
    console_level: str = "INFO",
    enable_console: bool = True,
    enable_colors: bool = True,
) -> None:
    """Настройка логирования с поддержкой systemd journal, файлов и консоли."""
    # Сначала удаляем все существующие обработчики
    logger.remove()

    disable_logging()

    # Настройка вывода в systemd journal
    try:
        journal_handler = journal.JournaldLogHandler("mewline")
        logger.add(
            journal_handler,
            level=journal_level,
            format="{message}",
        )
        logger.info("Systemd journal logging enabled")
    except Exception as e:
        logger.error(f"Failed to setup systemd journal logging: {e}")

    # Настройка вывода в файл
    try:
        log_file = ensure_log_directory()
        logger.add(
            log_file,
            rotation="10 MB",
            retention="14 days",
            compression="gz",
            level=file_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            enqueue=True,
        )
        logger.info(f"File logging enabled: {log_file}")
    except Exception as e:
        logger.error(f"Failed to setup file logging: {e}")

    # Добавляем вывод в терминал
    if enable_console:
        try:
            logger.add(
                sink=lambda msg: print(msg, end=""),
                level=console_level,
                format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
                colorize=enable_colors,
            )
        except Exception as e:
            logger.error(f"Failed to setup console logging: {e}")
