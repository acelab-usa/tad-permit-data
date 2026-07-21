"""Central logging configuration shared by every module in the pipeline.

Import `get_logger(__name__)` instead of using `print()` so that ingestion
failures are captured to disk (pipeline.log) as well as the console, and can
be filtered by level/module when debugging a bad run.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline.log")
_CONFIGURED = False


def _configure_root():
    global _CONFIGURED
    if _CONFIGURED:
        return
    root = logging.getLogger("permit_pipeline")
    root.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    file_handler = RotatingFileHandler(_LOG_PATH, maxBytes=5_000_000, backupCount=3)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure_root()
    return logging.getLogger(f"permit_pipeline.{name}")
