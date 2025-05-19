from loguru import logger
from systemd import journal

LOGURU_TO_JOURNALD: dict[str, int] = {
    "TRACE": journal.Priority.DEBUG,
    "DEBUG": journal.Priority.DEBUG,
    "INFO": journal.Priority.INFO,
    "SUCCESS": journal.Priority.NOTICE,
    "WARNING": journal.Priority.WARNING,
    "ERROR": journal.Priority.ERROR,
    "CRITICAL": journal.Priority.CRITICAL,
}


def disable_logging():
    for log in [
        "fabric.hyprland.widgets",
        "fabric.audio.service",
        "fabric.bluetooth.service",
    ]:
        logger.disable(log)


def journald_sink(message):
    record = message.record

    fields = {
        "MESSAGE": message,
        "PRIORITY": LOGURU_TO_JOURNALD.get(record["level"].name, journal.Priority.INFO),
        "CODE_FILE": record["file"].name,
        "CODE_LINE": record["line"],
        "CODE_FUNC": record["function"],
        "LOGGER": record["name"],
        "THREAD": f"{record['thread'].name} ({record['thread'].id})",
    }

    if record["exception"]:
        fields["EXCEPTION"] = str(record["exception"])

    journal.send(**fields)


def setup_loguru() -> None:
    disable_logging()

    # кастомный обработчик для systemd
    logger.add(
        journald_sink,
        level="INFO",
        format="{message}",
        filter=lambda record: "SUCCESS"
        not in record["message"],
    )
