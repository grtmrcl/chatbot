import logging
import re
import random

from lib.response_data import ResponseData

logger = logging.getLogger(__name__)


class Dice:
    MAX_NUM = 100
    MAX_SURFACES = 10000
    DEFAULT_TEMPLATES = {"default": "{{ data.text }}"}
    # [個数dD面数[±補正]] 形式のダイス記法にマッチする正規表現
    DICE_RE = re.compile(r"(\[(\d+)[dD](\d+)([+-]\d+)?[^\]]*?\])")

    def __init__(self, config: dict):
        self._templates = config.get("dice", {}).get("templates") or self.DEFAULT_TEMPLATES

    def roll(self, text: str) -> ResponseData:
        matches = self.DICE_RE.findall(text)
        response_data = ResponseData()
        response_data.templates = self._templates

        try:
            for whole, num_str, surface_str, correction in matches:
                num = int(num_str)
                surface = int(surface_str)

                if num == 0 or num > self.MAX_NUM or surface == 0 or surface > self.MAX_SURFACES:
                    raise ValueError("Invalid dice parameters")

                results = [random.randint(1, surface) for _ in range(num)]
                total = sum(results)
                result_str = ",".join(str(r) for r in results)

                if correction:
                    sign = correction[0]
                    value = int(correction[1:])
                    result_str += correction
                    total = total - value if sign == "-" else total + value

                text = text.replace(whole, str(total), 1)

            response_data.data = {"text": text}
            return response_data
        except Exception:
            logger.exception("ダイスロールエラー")
            response_data.error_message = "エラーが発生しました。管理者にお知らせください。"
            return response_data
