import logging
import os
from typing import Any, Optional
from xml.etree import ElementTree

import requests
import yaml

from lib.response_data import ResponseData

logger = logging.getLogger(__name__)

FORECAST_URL = "https://weather.tsukumijima.net/api/forecast"
AREA_XML_URL = "https://weather.tsukumijima.net/primary_area.xml"

_TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "../../template.yml")

_city_map: Optional[dict[str, str]] = None
_pref_map: Optional[dict[str, list[str]]] = None


def _load_default_templates() -> dict[str, Any]:
    try:
        with open(_TEMPLATE_FILE) as f:
            return (yaml.safe_load(f) or {}).get("weather", {}).get("templates") or {}
    except Exception:
        logger.exception("template.yml の読み込みエラー")
        return {}


def _fetch_area_xml() -> ElementTree.Element:
    res = requests.get(AREA_XML_URL, timeout=10)
    res.raise_for_status()
    return ElementTree.fromstring(res.content)


def _get_city_map() -> dict[str, str]:
    global _city_map
    if _city_map is not None:
        return _city_map
    root = _fetch_area_xml()
    _city_map = {
        city.get("title", ""): city.get("id", "")
        for city in root.iter("city")
        if city.get("title") and city.get("id")
    }
    return _city_map


def _get_pref_map() -> dict[str, list[str]]:
    global _pref_map
    if _pref_map is not None:
        return _pref_map
    root = _fetch_area_xml()
    _pref_map = {}
    for pref in root.iter("pref"):
        pref_title = pref.get("title", "")
        if not pref_title:
            continue
        cities = [city.get("title", "") for city in pref.findall("city") if city.get("title")]
        if cities:
            _pref_map[pref_title] = cities
    return _pref_map


def _find_city_id(area_name: str) -> Optional[str]:
    city_map = _get_city_map()
    # 完全一致優先
    if area_name in city_map:
        return city_map[area_name]
    # 部分一致
    for title, code in city_map.items():
        if area_name in title or title in area_name:
            return code
    return None


_DEFAULT_TEMPLATES = _load_default_templates()


class Weather:
    def __init__(self, config: dict):
        self._templates = config.get("weather", {}).get("templates") or _DEFAULT_TEMPLATES

    def search(self, area_name: str) -> ResponseData:
        response_data = ResponseData()
        response_data.templates = self._templates
        try:
            city_id = _find_city_id(area_name)
            if not city_id:
                response_data.error_message = f"「{area_name}」の天気情報が見つかりませんでした。"
                return response_data

            res = requests.get(FORECAST_URL, params={"city": city_id}, timeout=10)
            res.raise_for_status()
            data = res.json()

            weather_list = []
            for forecast in data.get("forecasts", [])[:2]:  # 今日・明日
                date_label = forecast.get("dateLabel", "")
                date = forecast.get("date", "")
                telop = forecast.get("telop", "")
                temp = forecast.get("temperature", {})
                high = (temp.get("max") or {}).get("celsius") or "-"
                low = (temp.get("min") or {}).get("celsius") or "-"
                chance = forecast.get("chanceOfRain", {})
                rain_probability = [
                    v for v in chance.values() if v and v != "--%"
                ] or ["-"]

                weather_list.append(
                    {
                        "date": f"{date_label}({date})",
                        "weather": telop,
                        "hightemp": high,
                        "lowtemp": low,
                        "rain_probability": rain_probability,
                    }
                )

            rains = any(self._rains(w["rain_probability"]) for w in weather_list)

            response_data.data = {
                "area_name": data.get("location", {}).get("city") or area_name,
                "weather": weather_list,
                "rains": rains,
            }
            return response_data
        except Exception:
            logger.exception("天気予報取得エラー")
            response_data.error_message = "エラーが発生しました。管理者にお知らせください。"
            return response_data

    def search_area(self, pref_name: str) -> ResponseData:
        response_data = ResponseData()
        response_data.templates = {"default": "{{ data.areas }}"}
        try:
            pref_map = _get_pref_map()
            # 完全一致優先、次に部分一致
            cities = pref_map.get(pref_name)
            if not cities:
                for title, city_list in pref_map.items():
                    if pref_name in title or title in pref_name:
                        cities = city_list
                        break
            if not cities:
                response_data.error_message = f"「{pref_name}」に対応するエリアが見つかりませんでした。"
                return response_data
            response_data.data = {"areas": ", ".join(cities)}
            return response_data
        except Exception:
            logger.exception("エリア検索エラー")
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
