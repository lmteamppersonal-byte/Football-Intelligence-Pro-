# utils/logging_config.py
import logging

def setup_logging(name=None, level=logging.INFO, fmt="%(asctime)s %(levelname)s %(name)s: %(message)s"):
    """
    Configura logging básico e retorna o logger para o nome especificado.
    Mantém dependências mínimas para evitar falhas no import.
    """
    logging.basicConfig(level=level, format=fmt)
    return logging.getLogger(name or __name__)