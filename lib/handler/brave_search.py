import logging
import random
from typing import Optional

import requests

from lib.response_data import ResponseData

logger = logging.getLogger(__name__)

WEB_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
IMAGE_SEARCH_URL = "https://api.search.brave.com/res/v1/images/search"
VIDEO_SEARCH_URL = "https://api.search.brave.com/res/v1/videos/search"

SITE_DOMAINS = {
    "wiki": "ja.wikipedia.org",
    "youtube": "youtube.com",
    "nicovideo": "nicovideo.jp",
    "pixiv": "pixiv.net",
}


class BraveSearch:
    DEFAULT_TEMPLATES = {
        "default": "{% if data.search_type != 'image' %}{{ data.title }}: {% endif %}{{ data.link }}"
    }

    def __init__(self, config: dict):
        config = config["brave_search"]
        self._api_key = config["api_key"]
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
            if site and site in SITE_DOMAINS:
                query += f" site:{SITE_DOMAINS[site]}"

            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": self._api_key,
            }

            if search_type == "image":
                title, link = "", self._image_search(query, headers)
            elif search_type == "video":
                title, link = self._video_search(query, headers)
            else:
                title, link = self._web_search(query, headers)
                search_type = "text"

            response_data.data = {
                "title": title,
                "link": link,
                "search_type": search_type,
            }
            return response_data
        except Exception:
            logger.exception("Brave Search エラー")
            response_data.error_message = "エラーが発生しました。管理者にお知らせください。"
            return response_data

    def _web_search(self, query: str, headers: dict) -> tuple[str, str]:
        res = requests.get(
            WEB_SEARCH_URL,
            params={"q": query, "count": 1},
            headers=headers,
            timeout=10,
        )
        res.raise_for_status()
        results = res.json().get("web", {}).get("results", [])
        if not results:
            raise ValueError("検索結果が見つかりませんでした。")
        item = results[0]
        return item.get("title", ""), item.get("url", "")

    def _image_search(self, query: str, headers: dict) -> str:
        res = requests.get(
            IMAGE_SEARCH_URL,
            params={"q": query, "count": 10},
            headers=headers,
            timeout=10,
        )
        res.raise_for_status()
        results = res.json().get("results", [])
        if not results:
            raise ValueError("画像検索結果が見つかりませんでした。")
        item = random.choice(results)
        return item.get("properties", {}).get("url") or item.get("image", {}).get("src", "")

    def _video_search(self, query: str, headers: dict) -> tuple[str, str]:
        res = requests.get(
            VIDEO_SEARCH_URL,
            params={"q": query, "count": 1},
            headers=headers,
            timeout=10,
        )
        res.raise_for_status()
        results = res.json().get("results", [])
        if not results:
            raise ValueError("動画検索結果が見つかりませんでした。")
        item = results[0]
        return item.get("title", ""), item.get("url", "")
