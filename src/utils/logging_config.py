"""
Utilitário de configuração de logging.
Centraliza o formato e garante que o diretório existe.
"""

from pathlib import Path
import logging
from typing import Optional, Union

DEFAULT_LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"


def configure_logging(
    log_file: Union[str, Path],
    level: int = logging.INFO,
    logger_name: Optional[str] = None,
    add_console: bool = False,
    propagate: bool = True,
) -> logging.Logger:
    """
    Configura logging padrão da aplicação.

    Args:
        log_file: Caminho do ficheiro de log
        level: Nível de logging
        logger_name: Nome do logger. Se `None`, configura o root logger.
        add_console: Se True, adiciona também output para consola.
        propagate: Se False, impede propagação para loggers pais.
    """
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(DEFAULT_LOG_FORMAT)
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = propagate

    resolved_log_path = str(log_path.resolve())
    has_file_handler = any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename).resolve() == Path(resolved_log_path)
        for handler in logger.handlers
    )

    if not has_file_handler:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if add_console:
        has_console_handler = any(
            isinstance(handler, logging.StreamHandler)
            and not isinstance(handler, logging.FileHandler)
            for handler in logger.handlers
        )
        if not has_console_handler:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

    return logger
