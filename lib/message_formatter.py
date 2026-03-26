import logging
import random

from jinja2 import Template

from lib.emoji import Emoji
from lib.response_data import ResponseData

logger = logging.getLogger(__name__)


class MessageFormatter:
    def __init__(self, platform: str):
        self._platform = platform

    def get_response(self, response_data: ResponseData, response_type: str) -> str:
        try:
            data = response_data.data
            if response_data.templates is None:
                return "テンプレートが見つかりません。"
            template = response_data.templates[response_type]
            if isinstance(template, list):
                template = random.choice(template)
            return Template(template).render(data=data, Emoji=Emoji)
        except Exception:
            logger.exception("テンプレートレンダリングエラー")
            return "テンプレートエラーが発生しました。"
