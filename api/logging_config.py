import atexit
import logging
import os
import queue
import sys
from logging.handlers import QueueHandler, QueueListener

import loguru
from axiom_py import Client
from axiom_py.logging import AxiomHandler
from pipecat.utils.context import run_id_var, turn_var

from api.enums import Environment
from api.utils.worker import get_worker_id, is_worker_process

# ----- NEW CODE START -----
# Helper to map string log level to Python logging level, adding support for "TRACE"
TRACE_LEVEL_NUM = 5  # Below DEBUG (10)


def _get_logging_level(level_name: str) -> int:
    """Return numeric logging level for a given level name.

    Supports the standard logging levels as well as the custom ``TRACE`` level
    used by *loguru*. If ``TRACE`` is requested and not yet defined in the
    ``logging`` module, it will be registered dynamically.
    """
    level_name = level_name.upper()

    # Standard levels are present on the ``logging`` module.
    if hasattr(logging, level_name):
        return getattr(logging, level_name)

    # Add support for TRACE (finer-grained than DEBUG)
    if level_name == "TRACE":
        if not hasattr(logging, "TRACE"):
            logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")

            def trace(self, message, *args, **kwargs):  # type: ignore[override]
                if self.isEnabledFor(TRACE_LEVEL_NUM):
                    self._log(TRACE_LEVEL_NUM, message, args, **kwargs)

            logging.Logger.trace = trace  # type: ignore[attr-defined]
        return TRACE_LEVEL_NUM

    # Fallback to DEBUG if an unknown level is provided
    return logging.DEBUG


# ----- NEW CODE END -----

ENVIRONMENT = os.getenv("ENVIRONMENT", Environment.LOCAL.value)
ENABLE_TURN_LOGGING = os.getenv("ENABLE_TURN_LOGGING", "false").lower() == "true"

# Log rotation settings from environment
LOG_ROTATION_SIZE = os.getenv("LOG_ROTATION_SIZE", "100 MB")  # e.g., "100 MB", "1 GB"
LOG_ROTATION_TIME = os.getenv("LOG_ROTATION_TIME", None)  # e.g., "00:00", "12:00"
LOG_RETENTION = os.getenv(
    "LOG_RETENTION", "7 days"
)  # e.g., "7 days", "1 week", "10 files"
LOG_COMPRESSION = os.getenv(
    "LOG_COMPRESSION", "gz"
)  # "gz", "bz2", "xz", "tar", "tar.gz", "tar.bz2", "tar.xz", "zip"
LOG_FILE_PATH = os.getenv(
    "LOG_FILE_PATH", None
)  # If set, write to file instead of stdout

# Track if logging has been initialized
_logging_initialized = False
_axiom_listener = None


def inject_run_id(record):
    """Inject run_id from context variable into log record"""
    record["extra"]["run_id"] = run_id_var.get()

    # Only handle turn logging if enabled
    if ENABLE_TURN_LOGGING:
        # Get turn number with fallback mechanism
        turn = turn_var.get()

        # If turn is still 0, try the turn context manager
        if turn == 0:
            try:
                from api.services.pipecat.turn_context import get_turn_context_manager

                turn = get_turn_context_manager().get_turn()
            except ImportError:
                # Turn context manager not available
                pass

        record["extra"]["turn"] = turn
    else:
        # Turn logging disabled, use default value
        record["extra"]["turn"] = 0


def setup_logging():
    """Set up logging for the main application"""
    global _logging_initialized, _axiom_listener

    # Return early if already initialized
    if _logging_initialized:
        return _axiom_listener

    log_level = os.getenv("LOG_LEVEL", "DEBUG").upper()

    # Don't setup logging in test environment
    if ENVIRONMENT == Environment.TEST.value:
        return

    # Remove default loguru handler
    try:
        loguru.logger.remove(0)
    except ValueError:
        # Handler might already be removed
        pass

    # Patch loguru to inject run_id
    patched = loguru.logger.patch(inject_run_id)

    # Determine log format
    if ENABLE_TURN_LOGGING:
        log_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | <level>{level}</level> | [run_id={extra[run_id]}] [turn={extra[turn]}] | {file.name}:{line} | {message}"
    else:
        log_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | <level>{level}</level> | [run_id={extra[run_id]}] | {file.name}:{line} | {message}"

    # Add handler - either file with rotation or console
    if LOG_FILE_PATH:
        # File handler with rotation
        rotation_config = {}

        # Size-based rotation (e.g., "100 MB", "1 GB")
        if LOG_ROTATION_SIZE:
            rotation_config["rotation"] = LOG_ROTATION_SIZE

        # Time-based rotation (e.g., "00:00" for daily at midnight)
        if LOG_ROTATION_TIME:
            rotation_config["rotation"] = LOG_ROTATION_TIME

        # If no rotation specified, default to 100 MB
        if not rotation_config:
            rotation_config["rotation"] = "100 MB"

        # Retention policy (e.g., "7 days", "10 files")
        if LOG_RETENTION:
            rotation_config["retention"] = LOG_RETENTION

        # Compression format
        if LOG_COMPRESSION and LOG_COMPRESSION.lower() != "none":
            rotation_config["compression"] = LOG_COMPRESSION

        # Determine the actual log file path
        actual_log_path = LOG_FILE_PATH

        # If we're in a worker process, append worker ID to the filename
        if is_worker_process():
            worker_id = get_worker_id()
            # Split the path to insert worker ID before extension
            base_path, ext = os.path.splitext(LOG_FILE_PATH)
            actual_log_path = f"{base_path}-worker-{worker_id}{ext}"
            loguru.logger.info(f"Worker {worker_id} will log to: {actual_log_path}")

        patched.add(
            actual_log_path,
            format=log_format,
            level=log_level,
            colorize=False,  # No colors in file logs
            enqueue=True,  # Thread-safe writing
            **rotation_config,
        )
    else:
        # Console handler (existing behavior)
        patched.add(
            sys.stdout,
            format=log_format,
            level=log_level,
            colorize=True,
        )

    # Set up queue-based logging for Axiom
    log_q = queue.Queue(-1)  # infinite size (tweak if needed)
    queue_handler = QueueHandler(log_q)  # puts LogRecord on the queue
    queue_handler.setLevel(_get_logging_level(log_level))

    # Set up Axiom handler if credentials are available
    axiom_token = os.environ.get("AXIOM_TOKEN")
    axiom_org = os.environ.get("AXIOM_ORG")
    axiom_dataset = os.getenv("AXIOM_LOG_DATASET")

    if axiom_token and axiom_org and axiom_dataset:
        client = Client(token=axiom_token, org_id=axiom_org)
        axiom_handler = AxiomHandler(client, axiom_dataset)
        axiom_handler.setLevel(_get_logging_level(log_level))

        listener = QueueListener(
            log_q,
            axiom_handler,
            respect_handler_level=True,
        )
        listener.start()

        patched.add(queue_handler, level=log_level, enqueue=False)

        # Register cleanup
        atexit.register(listener.stop)

        # Return the listener for manual cleanup if needed
        loguru.logger = patched
        _logging_initialized = True
        _axiom_listener = listener
        return listener
    else:
        # No Axiom logging available
        loguru.logger = patched
        _logging_initialized = True
        return None
