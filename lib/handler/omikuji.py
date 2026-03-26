import logging
import os
from typing import Any

import yaml

from lib.response_data import ResponseData

logger = logging.getLogger(__name__)

_TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "../../template.yml")


def _load_default_config() -> dict[str, Any]:
    try:
        with open(_TEMPLATE_FILE) as f:
            return (yaml.safe_load(f) or {}).get("omikuji") or {}
    except Exception:
        logger.exception("template.yml の読み込みエラー")
        return {}


_DEFAULT_CONFIG = _load_default_config()


class Omikuji:
    def __init__(self, config: dict):
        self._config = config.get("omikuji") or _DEFAULT_CONFIG

    def draw(self, type_: str = "unsei") -> ResponseData:
        response_data = ResponseData()
        omikuji_config = self._config.get(type_)
        if not omikuji_config:
            response_data.error_message = "そのおみくじは存在しません。"
            return response_data

        templates = omikuji_config.get("templates")
        if not templates:
            response_data.error_message = "そのおみくじは存在しません。"
            return response_data

        response_data.templates = templates
        response_data.data = "dummy"
        return response_data
