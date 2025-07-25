import logging
import logging.handlers
import sys

LOG_FILE = 'app.log'

def setup_logger():
    """
    Sets up the root logger for the application.
    """
    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG) # Set the lowest level for the logger

    # Prevent adding duplicate handlers if this function is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO) # Log INFO and above to console
    stdout_handler.setFormatter(formatter)

    # Rotating File Handler
    # Creates a new log file when the current one reaches 1MB, keeps up to 5 old log files.
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG) # Log DEBUG and above to file
    file_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(stdout_handler)
    logger.addHandler(file_handler)

    # Set the excepthook to log unhandled exceptions
    sys.excepthook = handle_exception

def handle_exception(exc_type, exc_value, exc_traceback):
    """
    Log unhandled exceptions using the root logger.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logging.getLogger().critical("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))

if __name__ == '__main__':
    setup_logger()
    logging.info("Logger is set up.")
    logging.warning("This is a test warning.")
    logging.error("This is a test error.")
    logging.debug("This debug message should go to the file, but not the console.")
    # To test the exception hook:
    # raise TypeError("This is a test unhandled exception.")
