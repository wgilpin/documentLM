"""Structured logging configuration."""

import logging


LEVEL_COLORS = {
    "DEBUG": "\033[36m",     # cyan
    "INFO": "\033[32m",      # green
    "WARNING": "\033[33m",   # yellow
    "ERROR": "\033[31m",     # red
    "CRITICAL": "\033[35m",  # magenta
}
RESET = "\033[0m"


class ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = LEVEL_COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{RESET}"
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        ColorFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler],
        force=True,
    )
    # Re-enable any writer.* loggers disabled by a third-party
    # dictConfig(disable_existing_loggers=True) call during import.
    for name, obj in logging.Logger.manager.loggerDict.items():
        if name.startswith("writer") and isinstance(obj, logging.Logger):
            obj.disabled = False
