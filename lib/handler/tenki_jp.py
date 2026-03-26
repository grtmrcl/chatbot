import logging
import os
from typing import Any

import requests
import yaml
from bs4 import BeautifulSoup

from lib.response_data import ResponseData

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.tenki.jp/search/"

_TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "../../template.yml")


def _load_default_templates() -> dict[str, Any]:
    try:
        with open(_TEMPLATE_FILE) as f:
            return (yaml.safe_load(f) or {}).get("tenki_jp", {}).get("templates") or {}
    except Exception:
        logger.exception("template.yml の読み込みエラー")
        return {}


_DEFAULT_TEMPLATES = _load_default_templates()


class TenkiJp:
    def __init__(self, config: dict):
        self._templates = config.get("tenki_jp", {}).get("templates") or _DEFAULT_TEMPLATES

    def search(self, area_name: str) -> ResponseData:
        response_data = ResponseData()
        response_data.templates = self._templates
        try:
            # エリア名で検索して最初の予報ページへ
            params = {"keyword": area_name}
            res = requests.get(SEARCH_URL, params=params, timeout=10)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")

            # 検索結果の最初のリンクを取得
            link = soup.select_one(".search-item-title a")
            if not link:
                response_data.error_message = f"「{area_name}」の天気情報が見つかりませんでした。"
                return response_data

            forecast_url = "https://www.tenki.jp" + link["href"]
            res = requests.get(forecast_url, timeout=10)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")

            weather_list = []
            days = soup.select(".forecast-days-wrap .forecast-day-item")
            for day in days[:2]:  # 今日・明日
                date_el = day.select_one(".forecast-day-item-header")
                weather_el = day.select_one(".weather-telop-item")
                high_el = day.select_one(".high-temp")
                low_el = day.select_one(".low-temp")
                high_diff_el = day.select_one(".high-temp-diff")
                low_diff_el = day.select_one(".low-temp-diff")
                rain_els = day.select(".rain-probability td")

                date = date_el.get_text(strip=True) if date_el else ""
                weather = weather_el.get_text(strip=True) if weather_el else ""
                high = high_el.get_text(strip=True) if high_el else "-"
                low = low_el.get_text(strip=True) if low_el else "-"
                high_diff = high_diff_el.get_text(strip=True) if high_diff_el else ""
                low_diff = low_diff_el.get_text(strip=True) if low_diff_el else ""
                rain = [el.get_text(strip=True) for el in rain_els] if rain_els else []

                weather_list.append(
                    {
                        "date": date,
                        "weather": weather,
                        "hightemp": high,
                        "hightempdiff": high_diff,
                        "lowtemp": low,
                        "lowtempdiff": low_diff,
                        "rain_probability": rain,
                    }
                )

            rains = any(
                self._rains(w["rain_probability"]) for w in weather_list
            )

            response_data.data = {
                "area_name": area_name,
                "weather": weather_list,
                "rains": rains,
            }
            return response_data
        except Exception:
            logger.exception("天気予報取得エラー")
            response_data.error_message = "エラーが発生しました。管理者にお知らせください。"
            return response_data

    def _rains(self, rain_probability: list) -> bool:
        for prob in rain_probability:
            try:
                if int(prob.replace("%", "")) >= 30:
                    return True
            except ValueError:
                pass
        return False
