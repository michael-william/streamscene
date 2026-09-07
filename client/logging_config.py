"""
StreamScene Client Logging Configuration

Centralized logging setup for all client components.
Logs to both console and rotating file handlers.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from datetime import datetime


# Log file locations
LOG_DIR = Path("/var/log/streamscene")
CLIENT_LOG = LOG_DIR / "streamscene-client.log"
HOTSPOT_LOG = LOG_DIR / "streamscene-hotspot.log"
WIFI_LOG = LOG_DIR / "streamscene-wifi.log"
REGISTRATION_LOG = LOG_DIR / "streamscene-registration.log"
OTA_LOG = LOG_DIR / "streamscene-ota.log"

# Fallback to local directory if /var/log/streamscene doesn't exist or isn't writable
if not LOG_DIR.exists() or not os.access(LOG_DIR, os.W_OK):
    LOG_DIR = Path.home() / "streamscene-client" / "logs"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CLIENT_LOG = LOG_DIR / "streamscene-client.log"
    HOTSPOT_LOG = LOG_DIR / "streamscene-hotspot.log"
    WIFI_LOG = LOG_DIR / "streamscene-wifi.log"
    REGISTRATION_LOG = LOG_DIR / "streamscene-registration.log"
    OTA_LOG = LOG_DIR / "streamscene-ota.log"


class ComponentFormatter(logging.Formatter):
    """Custom formatter that includes component name in structured format"""

    def format(self, record):
        # Add component name if not present
        if not hasattr(record, 'component'):
            record.component = 'UNKNOWN'

        # Format: [TIMESTAMP] [LEVEL] [COMPONENT] message
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        level = record.levelname
        component = record.component
        message = record.getMessage()

        formatted = f"[{timestamp}] [{level}] [{component}] {message}"

        # Add exception info if present
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)

        return formatted


def setup_logger(name: str, log_file: Path, level=logging.INFO) -> logging.Logger:
    """
    Create a logger with both console and file handlers

    Args:
        name: Logger name (e.g., 'streamscene.main')
        log_file: Path to log file
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Create formatters
    formatter = ComponentFormatter()

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (rotating, max 10MB, keep 7 files)
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=7
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        # If we can't write to file, just use console
        logger.warning(f"Could not create file handler for {log_file}: {e}")

    return logger


def get_logger(component: str, log_file: Path = CLIENT_LOG) -> logging.LoggerAdapter:
    """
    Get a logger for a specific component

    Args:
        component: Component name (e.g., 'MAIN', 'HOTSPOT', 'WIFI')
        log_file: Path to log file (default: CLIENT_LOG)

    Returns:
        LoggerAdapter that automatically adds component name to all log records
    """
    logger = setup_logger(f"streamscene.{component.lower()}", log_file)

    # Return adapter that automatically adds component to extra dict
    return logging.LoggerAdapter(logger, {'component': component})


# Pre-configured loggers for common components
main_logger = get_logger('MAIN', CLIENT_LOG)
hotspot_logger = get_logger('HOTSPOT', HOTSPOT_LOG)
wifi_logger = get_logger('WIFI', WIFI_LOG)
registration_logger = get_logger('REGISTRATION', REGISTRATION_LOG)
network_logger = get_logger('NETWORK', WIFI_LOG)
api_logger = get_logger('API', CLIENT_LOG)
display_logger = get_logger('DISPLAY', CLIENT_LOG)
state_logger = get_logger('STATE', CLIENT_LOG)
ota_logger = get_logger('OTA', OTA_LOG)


def log_subprocess_output(logger, process_result, command: str):
    """
    Log subprocess output (stdout and stderr)

    Args:
        logger: Logger instance to use
        process_result: subprocess.CompletedProcess or subprocess.Popen result
        command: Command that was executed (for context)
    """
    if hasattr(process_result, 'returncode'):
        logger.debug(f"Command: {command}")
        logger.debug(f"Return code: {process_result.returncode}")

        if hasattr(process_result, 'stdout') and process_result.stdout:
            stdout = process_result.stdout.decode() if isinstance(process_result.stdout, bytes) else process_result.stdout
            if stdout.strip():
                logger.debug(f"stdout:\n{stdout}")

        if hasattr(process_result, 'stderr') and process_result.stderr:
            stderr = process_result.stderr.decode() if isinstance(process_result.stderr, bytes) else process_result.stderr
            if stderr.strip():
                if process_result.returncode != 0:
                    logger.error(f"stderr:\n{stderr}")
                else:
                    logger.debug(f"stderr:\n{stderr}")


def log_startup_info():
    """Log startup information and system details"""
    main_logger.info("=" * 60)
    main_logger.info("StreamScene Client Starting")
    main_logger.info("=" * 60)
    main_logger.info(f"Python version: {sys.version}")
    main_logger.info(f"Log directory: {LOG_DIR}")
    main_logger.info(f"Client log: {CLIENT_LOG}")
    main_logger.info(f"Hotspot log: {HOTSPOT_LOG}")
    main_logger.info(f"WiFi log: {WIFI_LOG}")
    main_logger.info(f"Registration log: {REGISTRATION_LOG}")
    main_logger.info(f"OTA log: {OTA_LOG}")
    main_logger.info("=" * 60)
