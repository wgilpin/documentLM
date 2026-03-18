"""Structured logging configuration."""

import logging


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )
    # Re-enable any writer.* loggers disabled by a third-party
    # dictConfig(disable_existing_loggers=True) call during import.
    for name, obj in logging.Logger.manager.loggerDict.items():
        if name.startswith("writer") and isinstance(obj, logging.Logger):
            obj.disabled = False
