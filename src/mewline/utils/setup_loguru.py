from loguru import logger
from systemd import journal


def disable_logging():
    for log in [
        "fabric.hyprland.widgets",
        "fabric.audio.service",
        "fabric.bluetooth.service",
    ]:
        logger.disable(log)


def setup_loguru() -> None:
    disable_logging()
    logger.add(journal.JournaldLogHandler("mewline"), level="INFO", format="{message}")
