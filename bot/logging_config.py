import os
import sys
import logging
from logging.handlers import RotatingFileHandler


def setup_logging():
    """Налаштування логування в консоль та у файл з автоматичною ротацією."""
    os.makedirs("logs", exist_ok=True)
    log_file = os.path.join("logs", "mtservice.log")

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # 1. Ротація лог-файлів: макс 10 МБ, зберігати до 5 архівів (до 50 МБ разом)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # 2. Консольний потік (UTF-8)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return root_logger
