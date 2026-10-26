"""Configure the desktop app's per-user diagnostic log."""

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys


APP_LOGGER_NAME = 'smi2assF'
MAX_LOG_BYTES = 1_048_576
BACKUP_COUNT = 3


class _BoundedFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        maximum = MAX_LOG_BYTES - len(os.linesep.encode('utf-8'))
        encoded = message.encode('utf-8', errors='backslashreplace')
        if len(encoded) <= maximum:
            return message

        marker = '\n[log record truncated]\n'
        marker_size = len(marker.encode('utf-8'))
        available = maximum - marker_size
        first_size = available // 2
        last_size = available - first_size
        first = encoded[:first_size].decode('utf-8', errors='ignore')
        last = encoded[-last_size:].decode('utf-8', errors='ignore')
        return first + marker + last


class _BoundedRotatingFileHandler(RotatingFileHandler):
    def shouldRollover(self, record):
        if self.maxBytes <= 0:
            return False
        try:
            current_size = os.path.getsize(self.baseFilename)
        except OSError:
            current_size = 0
        message = self.format(record) + self.terminator
        record_size = len(message.encode(self.encoding or 'utf-8', errors='backslashreplace'))
        if os.name == 'nt':
            record_size += message.count('\n')
        return current_size + record_size > self.maxBytes


def get_app_logger():
    return logging.getLogger(APP_LOGGER_NAME)


def get_log_path(*, platform_name=None, environ=None, home=None):
    platform_name = sys.platform if platform_name is None else platform_name
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)

    if platform_name == 'darwin':
        log_directory = home / 'Library' / 'Logs' / 'smi2assF'
    elif platform_name == 'win32':
        local_app_data = environ.get('LOCALAPPDATA')
        base = Path(local_app_data) if local_app_data else home / 'AppData' / 'Local'
        log_directory = base / 'smi2assF' / 'Logs'
    else:
        state_home = environ.get('XDG_STATE_HOME')
        base = Path(state_home) if state_home else home / '.local' / 'state'
        log_directory = base / 'smi2assF'
    return log_directory / 'app.log'


def configure_app_logging(path=None):
    """Set up bounded UTF-8 logging; logging must never block app startup."""
    logger = get_app_logger()
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in tuple(logger.handlers):
        if getattr(handler, '_smi2ass_app_handler', False):
            logger.removeHandler(handler)
            handler.close()

    try:
        log_path = get_log_path() if path is None else Path(path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = _BoundedRotatingFileHandler(
            log_path, maxBytes=MAX_LOG_BYTES, backupCount=BACKUP_COUNT,
            encoding='utf-8', errors='backslashreplace',
        )
    except (OSError, RuntimeError, ValueError):
        handler = logging.NullHandler()

    handler._smi2ass_app_handler = True
    handler.setFormatter(_BoundedFormatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    return logger
