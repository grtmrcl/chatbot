import re

from lib.response_data import ResponseData
from lib.handler.brave_search import BraveSearch
from lib.handler.chatgpt import ChatGPT
from lib.handler.dice import Dice
from lib.handler.omikuji import Omikuji
from lib.handler.weather import Weather
from lib.handler.route import Route
from lib.handler.sss import Sss
from lib.handler.events import Events
from lib.handler.opebirth import Opebirth


class MessageProcesser:
    def __init__(self, platform: str, config: dict):
        self._platform = platform
        self._chatgpt = ChatGPT(config)
        self._dice = Dice(config)
        self._omikuji = Omikuji(config)
        self._brave = BraveSearch(config)
        self._weather = Weather(config)
        self._route = Route(config)
        self._sss = Sss(config)
        self._events = Events(config)
        self._opebirth = Opebirth(config)

    def get_response_data(self, channel, text: str) -> ResponseData:
        text = re.sub(r"^Reminder\s", "", text)

        # Brave Search
        if m := re.match(r"^(?:google|brave|g)\s+(.+)$", text):
            return self._brave.search(m.group(1))
        if m := re.match(r"^(?:image|i)\s+(.+)$", text):
            return self._brave.search(m.group(1), search_type="image")
        if m := re.match(r"^wiki\s+(.+)$", text):
            return self._brave.search(m.group(1), site="wiki")
        if m := re.match(r"^(?:youtube|yt)\s+(.+)$", text):
            return self._brave.search(m.group(1), search_type="video", site="youtube")
        if m := re.match(r"^(?:nicovideo|nico)\s+(.+)$", text):
            return self._brave.search(m.group(1), search_type="video", site="nicovideo")

        # Weather
        if m := re.match(r"^(?:weather|tenki|天気)area\s+(.+)$", text):
            return self._weather.search_area(m.group(1))
        if m := re.match(r"^(?:weather|tenki|天気)\s+(.+)$", text):
            return self._weather.search(m.group(1))

        # Route
        if m := re.match(r"^(?:route|乗換|乗り換え|乗換え)\s+(\S+?)から(\S+)(?:\s+(.+))?$", text):
            return self._route.search(m.group(1), m.group(2), m.group(3))
        if m := re.match(r"^(?:route|乗換|乗り換え|乗換え)\s+(\S+)\s+(\S+)(?:\s+(.+))?$", text):
            return self._route.search(m.group(1), m.group(2), m.group(3))

        # Spreadsheet Search
        if m := re.match(r"^sss\s+(\S+)\s+(.+)$", text, re.DOTALL):
            return self._sss.search(m.group(1), m.group(2))

        # Omikuji
        if m := re.match(r"^omikuji(?:\s+(\w+))?$", text):
            omikuji_type = m.group(1) or "unsei"
            return self._omikuji.draw(omikuji_type)

        # Omikuji SS
        if m := re.match(r"^ss-omikuji\s+(\S+)(?:\s+(.+))?$", text, re.DOTALL):
            return self._sss.draw(m.group(1), m.group(2))
        if m := re.match(r"^(?:opekuji|オペくじ)(?:\s+(.+))?$", text, re.DOTALL):
            return self._sss.draw("ak", m.group(1))
        if m := re.match(r"^ef-opekuji(?:\s+(.+))?$", text, re.DOTALL):
            return self._sss.draw("ef", m.group(1))

        # Events
        if m := re.match(r"^event-register\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$", text):
            return self._events.register(m.group(1), m.group(2), m.group(3), m.group(4))
        if m := re.match(r"^event-remind\s+(\S+)(?:\s+(\S+))?$", text):
            return self._events.reminder(m.group(1), m.group(2))
        if m := re.match(r"^event-delete\s+(\S+)\s+(.+)$", text):
            return self._events.delete(m.group(1), m.group(2))

        # Opebirth
        if text == "opebirth":
            return self._opebirth.search_all()
        if m := re.match(r"^opebirth\s+(\d{4}|\d{2}-\d{2})$", text):
            return self._opebirth.search_all(m.group(1))
        if m := re.match(r"^opebirth\s+(\S+)(?:\s+(\S+))?$", text):
            return self._opebirth.search(m.group(1), m.group(2))

        # Dice
        if re.search(r"\[\d+[dD]\d+(?:[+-]\d+)?\]", text):
            return self._dice.roll(text)

        return ResponseData()
