import logging
import random
from typing import Optional

from googleapiclient.discovery import build

from lib.response_data import ResponseData

logger = logging.getLogger(__name__)

SITE_DOMAINS = {
    "wiki": "ja.wikipedia.org",
    "youtube": "youtube.com",
    "nicovideo": "nicovideo.jp",
    "pixiv": "pixiv.net",
}


class GoogleCustomSearch:
    DEFAULT_TEMPLATES = {
        "default": "{% if data.search_type == 'text' %}{{ data.title }}: {% endif %}{{ data.link }}"
    }

    def __init__(self, config: dict):
        config = config["google_custom_search"]
        self._api_key = config["api_key"]
        self._search_engine_id = config["search_engine_id"]
        self._templates = config.get("templates") or self.DEFAULT_TEMPLATES

    def search(
        self,
        query: str,
        search_type: Optional[str] = None,
        site: Optional[str] = None,
    ) -> ResponseData:
        response_data = ResponseData()
        response_data.templates = self._templates
        try:
            service = build("customsearch", "v1", developerKey=self._api_key)
            params = {
                "q": query,
                "cx": self._search_engine_id,
                "num": 10,
            }
            if search_type == "image":
                params["searchType"] = "image"
            if site and site in SITE_DOMAINS:
                params["q"] += f" site:{SITE_DOMAINS[site]}"

            results = service.cse().list(**params).execute()
            items = results.get("items", [])
            if not items:
                response_data.error_message = "検索結果が見つかりませんでした。"
                return response_data

            item = random.choice(items) if search_type == "image" else items[0]
            response_data.data = {
                "title": item.get("title"),
                "link": item.get("link"),
                "search_type": search_type or "text",
            }
            return response_data
        except Exception:
            logger.exception("Google Custom Search エラー")
            response_data.error_message = "エラーが発生しました。管理者にお知らせください。"
            return response_data
