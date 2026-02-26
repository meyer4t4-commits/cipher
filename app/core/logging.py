"""
Structured logging configuration for Cipher.
Uses rich for beautiful console output during development.
"""

import logging
import sys

from rich.console import Console
from rich.logging import RichHandler

from app.core.config import settings

console = Console()


def setup_logging() -> logging.Logger:
    level = logging.DEBUG if settings.app_debug else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=console,
                rich_tracebacks=True,
                show_path=settings.app_debug,
            )
        ],
    )

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)

    logger = logging.getLogger("cipher")
    logger.setLevel(level)
    return logger


logger = setup_logging()
