"""
Logging configuration for Job Search Automation System.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional

# Log directory
LOG_DIR = Path.home() / "workapps" / "job-search-automation" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


class ColorFormatter(logging.Formatter):
    """Colored formatter for console output."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(
    name: str = "job_search",
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Setup logging configuration.

    Args:
        name: Logger name
        level: Logging level
        log_to_file: Whether to log to file
        log_to_console: Whether to log to console
        log_file: Custom log file path

    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Clear existing handlers
    logger.handlers = []

    # File format (no colors)
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console format (with colors)
    console_formatter = ColorFormatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )

    if log_to_file:
        # Main log file (rotates daily)
        log_path = log_file or LOG_DIR / f"{name}.log"
        file_handler = TimedRotatingFileHandler(
            log_path,
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Error log file (separate)
        error_path = LOG_DIR / f"{name}_errors.log"
        error_handler = RotatingFileHandler(
            error_path,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        logger.addHandler(error_handler)

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger(name: str = None) -> logging.Logger:
    """Get a logger instance."""
    if name:
        return logging.getLogger(f"job_search.{name}")
    return logging.getLogger("job_search")


# Module-level logger
logger = setup_logging()
