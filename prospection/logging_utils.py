#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Utilitaires de logging pour le pipeline de prospection."""

import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """Configure le système de logging centralisé pour tout le pipeline.

    Args:
        level: Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Chemin optionnel vers un fichier de log

    Returns:
        Logger configuré pour le pipeline
    """
    # Créer le logger principal
    logger = logging.getLogger("prospection_pipeline")
    logger.setLevel(getattr(logging, level.upper()))

    # Éviter la duplication des handlers
    if logger.handlers:
        return logger

    # Format des messages
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Handler console avec couleurs selon le niveau
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Handler fichier optionnel
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Tout dans le fichier
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Réduire le bruit des librairies externes
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return logger
