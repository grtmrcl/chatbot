import logging
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup, Tag

from lib.response_data import ResponseData

logger = logging.getLogger(__name__)

SEARCH_URL = "https://transit.yahoo.co.jp/search/result"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
}

TYPE_MAP = {
    "発": "1",
    "着": "4",
    "始発": "8",
    "終電": "16",
}


class Route:
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
        self._templates = config.get("route", {}).get("templates") or self.DEFAULT_TEMPLATES

    def _parse_options(self, options: str | None, now: datetime) -> dict:
        year, month, day = now.year, now.month, now.day
        hour, minute = now.hour, now.minute
        type_ = "4"

        if options:
            date_m = re.search(r"\b(\d{8})\b", options)
            if date_m:
                s = date_m.group(1)
                year, month, day = int(s[:4]), int(s[4:6]), int(s[6:8])

            for key, value in TYPE_MAP.items():
                if key in options:
                    type_ = value
                    break

            # 始発・終電は時刻指定不可
            if type_ not in ("8", "16"):
                time_m = re.search(r"\b(\d{4})\b", options)
                if time_m:
                    s = time_m.group(1)
                    hour, minute = int(s[:2]), int(s[2:4])

        minute_str = f"{minute:02d}"
        return {
            "y": str(year),
            "m": f"{month:02d}",
            "d": f"{day:02d}",
            "hh": f"{hour:02d}",
            "m1": minute_str[0],
            "m2": minute_str[1],
            "type": type_,
        }

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
            date_params = self._parse_options(options, now)
            params = {
                "from": dep,
                "to": arr,
                **date_params,
                "ticket": "ic",
                "expkind": "1",
                "userpass": "1",
                "ws": "3",
                "s": "0",
                "al": "1",
                "shin": "1",
                "ex": "1",
                "hb": "1",
                "lb": "1",
                "sr": "1",
            }

            res = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=15)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")

            search_time = "{}/{}/{} {}:{}".format(
                date_params["y"], date_params["m"], date_params["d"],
                date_params["hh"], date_params["m1"] + date_params["m2"],
            )
            summary = []
            candidates = []

            route_items = soup.select("ul#rsltlst > li")
            for i, item in enumerate(route_items[:3], start=1):
                time_el = item.select_one("li.time")
                fare_el = item.select_one("li.fare")
                transfer_el = item.select_one("li.transfer")

                time_text = time_el.get_text(" ", strip=True) if time_el else ""
                fee_text = fare_el.get_text(strip=True) if fare_el else ""
                transfer_text = transfer_el.get_text(strip=True) if transfer_el else ""

                summary.append(
                    {
                        "number": i,
                        "time": time_text,
                        "fee": fee_text,
                        "transfer": transfer_text,
                    }
                )

                detail = self._parse_detail(soup, i)
                candidates.append(
                    {
                        "number": i,
                        "time": time_text,
                        "fee": fee_text,
                        "transfer": transfer_text,
                        "detail": detail,
                    }
                )

            if not summary:
                response_data.error_message = "経路が見つかりませんでした。"
                return response_data

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

    def _parse_detail(self, soup: BeautifulSoup, index: int) -> str:
        route_div = soup.select_one(f"#route0{index}")
        if not route_div:
            return ""
        route_detail = route_div.select_one(".routeDetail")
        if not route_detail:
            return ""

        lines = []

        def parse_station(el: Tag) -> None:
            name_el = el.select_one("dl dt a")
            time_els = el.select("ul.time li")
            name = name_el.get_text(strip=True) if name_el else ""
            times = " ".join(t for li in time_els if (t := li.get_text(strip=True)))
            if name:
                lines.append(f"{times} {name}".strip())

        def parse_access(el: Tag) -> None:
            transport_el = el.select_one("li.transport")
            if transport_el:
                line = transport_el.get_text(" ", strip=True)
                lines.append(f"  [{line}]")

        for child in route_detail.find_all(True, recursive=False):
            if not isinstance(child, Tag):
                continue
            classes = child.get("class") or []
            if "station" in classes:
                parse_station(child)
            elif "fareSection" in classes:
                for sub in child.find_all(True, recursive=False):
                    if not isinstance(sub, Tag):
                        continue
                    sub_classes = sub.get("class") or []
                    if "access" in sub_classes:
                        parse_access(sub)
                        for inner in sub.find_all("div", class_="station"):
                            parse_station(inner)
                    elif "station" in sub_classes:
                        parse_station(sub)

        return "\n".join(lines)
