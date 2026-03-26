import re

from lib.response_data import ResponseData
from lib.handler.chatgpt import ChatGPT
from lib.handler.dice import Dice
from lib.handler.omikuji import Omikuji
from lib.handler.google_custom_search import GoogleCustomSearch
from lib.handler.tenki_jp import TenkiJp
from lib.handler.navitime import Navitime


class MessageProcesser:
    def __init__(self, platform: str, config: dict):
        self._platform = platform
        self._chatgpt = ChatGPT(config)
        self._dice = Dice(config)
        self._omikuji = Omikuji(config)
        self._google = GoogleCustomSearch(config)
        self._tenki = TenkiJp(config)
        self._navitime = Navitime(config)

    def get_response_data(self, channel, text: str) -> ResponseData:
        text = re.sub(r"^Reminder\s", "", text)

        # ChatGPT
        # if re.match(r"^gpt\s+list$", text):
        #     return self._chatgpt.list(channel)
        # if m := re.match(r"^gpt\s+detail\s+(\d+)$", text):
        #     return self._chatgpt.detail(m.group(1), channel)
        # if m := re.match(r"^gpt\s+id\s+(\d+)$", text):
        #     return self._chatgpt.set_talk_id(m.group(1), channel)
        # if m := re.match(r"^gpt\s+delete\s+(\d+)$", text):
        #     return self._chatgpt.delete(m.group(1), channel)
        # if re.match(r"^gpt\s+clear$", text):
        #     return self._chatgpt.clear(channel)
        # if m := re.match(r"^gpt\s+system\s+(.+)$", text, re.DOTALL):
        #     return self._chatgpt.system(m.group(1), channel)
        # if m := re.match(r"^gpt\s+(.+)$", text, re.DOTALL):
        #     return self._chatgpt.chat(m.group(1), channel)

        # Google Custom Search
        if m := re.match(r"^google\s+(.+)$", text):
            return self._google.search(m.group(1))
        if m := re.match(r"^image\s+(.+)$", text):
            return self._google.search(m.group(1), search_type="image")
        if m := re.match(r"^wiki\s+(.+)$", text):
            return self._google.search(m.group(1), site="wiki")
        if m := re.match(r"^youtube\s+(.+)$", text):
            return self._google.search(m.group(1), site="youtube")
        if m := re.match(r"^nicovideo\s+(.+)$", text):
            return self._google.search(m.group(1), site="nicovideo")

        # Weather
        if m := re.match(r"^(?:tenki|weather)\s+(.+)$", text):
            return self._tenki.search(m.group(1))

        # Route
        if m := re.match(r"^(?:route|乗換)\s+(\S+)\s+(\S+)(?:\s+(.+))?$", text):
            return self._navitime.search(m.group(1), m.group(2), m.group(3))

        # Omikuji
        if m := re.match(r"^omikuji(?:\s+(\w+))?$", text):
            omikuji_type = m.group(1) or "g1"
            return self._omikuji.draw(omikuji_type)

        # Dice
        if re.search(r"\[\d+[dD]\d+(?:[+-]\d+)?\]", text):
            return self._dice.role(text)

        return ResponseData()
