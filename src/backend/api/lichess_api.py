import datetime
import json
import os
import sys

import requests
from dotenv import load_dotenv

from src.constants import LICHESS_BASE_URL
from src.utils.config import ConfigManager
from src.utils.logger import logger

from .base_api import BaseChessAPI


def _loss_result(game_data: dict) -> str:
    """Map Lichess termination status to a loss result string."""
    status = game_data.get("status", "")
    if status == "resign":
        return "resigned"
    if status in ("outoftime", "timeout"):
        return "timeout"
    if status == "mate":
        return "checkmated"
    if status == "stalemate":
        return "stalemate"
    return "agreed"


class LichessAPI(BaseChessAPI):
