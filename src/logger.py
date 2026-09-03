import os
import sys
import threading
import logging
import logging.handlers

from src.app_paths import resolve_base_dir

DEBUG_LOG_FOLDER = os.path.join(resolve_base_dir(), "Debug")
DEBUG_LOG_FILE = os.path.join(DEBUG_LOG_FOLDER, "debug.log")
DEBUG_LOGGER_NAME = "debug_log"


class CustomFormatter(logging.Formatter):
    """ """

    def __init__(
        self,
        fmt="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="<%m/%d/%Y %H:%M:%S>",
    ):
        logging.Formatter.__init__(self, fmt=fmt, datefmt=datefmt)

    def format(self, record):

        # Remember the original format
        format_orig = self._style._fmt

        if record.levelno == logging.ERROR:
            self._style._fmt = (
                "%(asctime)s - %(levelname)s - %(module)s.%(funcName)s - %(message)s"
            )

        # Calling the original formatter once the style has changed
        result = logging.Formatter.format(self, record)

        # Restore the original format
        self._style._fmt = format_orig

        return result


class _DeferredFileHandler(logging.Handler):
    """File handler that builds the real rotating handler on the first
    emitted record, so importing this module performs no filesystem writes
    (no Debug/ directory, no open file handle). Tests and tools that merely
    import src.logger stay side-effect free; the first real log record
    materializes the log file exactly as before.
    """

    def __init__(self, file_path):
        super().__init__()
        self._file_path = file_path
        self._real_handler = None
        self._setup_lock = threading.Lock()

    def _real(self):
        handler = self._real_handler
        if handler is None:
            with self._setup_lock:
                handler = self._real_handler
                if handler is None:
                    folder = os.path.dirname(self._file_path)
                    if not os.path.exists(folder):
                        try:
                            os.makedirs(folder)
                        except Exception:
                            pass
                    handler = logging.handlers.TimedRotatingFileHandler(
                        self._file_path, when="D", interval=1, backupCount=7, utc=True
                    )
                    handler.setFormatter(CustomFormatter())
                    self._real_handler = handler
        return handler

    def close(self):
        # Close and release the underlying file handler so logging.shutdown
        # (or an explicit close) does not leak its file descriptor.
        with self._setup_lock:
            handler = self._real_handler
            self._real_handler = None
        if handler is not None:
            handler.close()
        super().close()

    def emit(self, record):
        # Dispatch under the real handler's own lock; formats once, writes once.
        self._real().handle(record)


# Create the shared logger. Only a stdout handler is attached at import time;
# the rotating file handler attaches lazily on the first emitted record.
shared_logger = logging.getLogger(DEBUG_LOGGER_NAME)
shared_logger.setLevel(logging.DEBUG)
shared_logger.addHandler(_DeferredFileHandler(DEBUG_LOG_FILE))
shared_logger.addHandler(logging.StreamHandler(sys.stdout))


def create_logger():
    logger = logging.getLogger(DEBUG_LOGGER_NAME)
    return logger
