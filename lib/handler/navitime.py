import logging
import urllib.parse
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from lib.response_data import ResponseData

logger = logging.getLogger(__name__)

SEARCH_URL = "https://transfer.navitime.biz/bus-navi/pc/route/RouteSearch"

CRITERIA_MAP = {
    "発": "departure",
    "着": "arrival",
    "始発": "first",
    "終電": "last",
}


class Navitime:
    DEFAULT_TEMPLATES = {
        "default": (
            "{{ data.dep }}⇒{{ data.arr }} {{ data.search_time }}\n"
            "{% for s in data.summary %}"
            "{{ Emoji.NUMBER[s.number] }} {{ s.time }} {{ s.transfer }} {{ s.fee }}\n"
            "{% endfor %}"
            "{% for c in data.candidate %}"
            "{{ Emoji.NUMBER[c.number] }} {{ c.time }} {{ c.transfer }} {{ c.fee }}\n"
            "{{ c.detail }}\n"
            "{% endfor %}"
        )
    }

    def __init__(self, config: dict):
        self._templates = config.get("navitime", {}).get("templates") or self.DEFAULT_TEMPLATES

    def search(
        self,
        dep: str,
        arr: str,
        options: str | None = None,
    ) -> ResponseData:
        response_data = ResponseData()
        response_data.templates = self._templates
        try:
            now = datetime.now()
            params = {
                "fromName": dep,
                "toName": arr,
                "year": now.strftime("%Y"),
                "month": now.strftime("%m"),
                "day": now.strftime("%d"),
                "hour": now.strftime("%H"),
                "minute": now.strftime("%M"),
                "criteria": "departure",
            }

            if options:
                for key, value in CRITERIA_MAP.items():
                    if key in options:
                        params["criteria"] = value
                        break

            res = requests.get(SEARCH_URL, params=params, timeout=15)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")

            title_el = soup.select_one(".route-result-title")
            title = title_el.get_text(strip=True) if title_el else f"{dep}→{arr}"
            search_time = now.strftime("%Y/%m/%d %H:%M")

            summary = []
            candidates = []
            route_items = soup.select(".route-result-item")
            for i, item in enumerate(route_items[:3], start=1):
                time_el = item.select_one(".route-result-item-time")
                fee_el = item.select_one(".route-result-item-fare")
                transfer_el = item.select_one(".route-result-item-transfer")

                time_text = time_el.get_text(strip=True) if time_el else ""
                fee_text = fee_el.get_text(strip=True) if fee_el else ""
                transfer_text = transfer_el.get_text(strip=True) if transfer_el else ""

                summary.append(
                    {
                        "number": i,
                        "time": time_text,
                        "fee": fee_text,
                        "transfer": transfer_text,
                    }
                )

                detail_lines = []
                steps = item.select(".route-detail-item")
                for step in steps:
                    step_text = step.get_text(separator=" ", strip=True)
                    if step_text:
                        detail_lines.append(step_text)
                detail = "\n".join(detail_lines)

                candidates.append(
                    {
                        "number": i,
                        "time": time_text,
                        "fee": fee_text,
                        "transfer": transfer_text,
                        "detail": detail,
                    }
                )

            response_data.data = {
                "dep": dep,
                "arr": arr,
                "search_time": search_time,
                "summary": summary,
                "candidate": candidates,
            }
            return response_data
        except Exception:
            logger.exception("乗換案内取得エラー")
            response_data.error_message = "エラーが発生しました。管理者にお知らせください。"
            return response_data
