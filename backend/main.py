# backend/main.py
from __future__ import annotations
import logging

from backend.util.logging_setup import init_logging
import config as cfg
from backend.api.app import create_app

init_logging(cfg.settings.log_level)
log = logging.getLogger("jarvin")

app = create_app()

