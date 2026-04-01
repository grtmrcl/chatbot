import json
import logging

from openai import OpenAI

from lib.response_data import ResponseData
from lib.redis_wrapper import RedisWrapper

logger = logging.getLogger(__name__)


class ChatGPT:
    REDIS_KEY_PREFIX = "chatgpt_"
    SUMMARY_MAX_LENGTH = 100
    DEFAULT_TEMPLATES = {"default": "{{ data.text }}"}

    def __init__(self, config: dict):
        config = config["chatgpt"]
        self._templates = config.get("templates") or self.DEFAULT_TEMPLATES
        self._client = OpenAI(api_key=config["openai_api_key"])
        self._talk_id: dict = {}

    def chat(self, message: str, channel) -> ResponseData:
        redis = self._get_redis_client(channel)
        talk_id = self._talk_id.get(channel, 1)
        messages = self._load_history(redis, talk_id)
        messages.append({"role": "user", "content": message})
        try:
            response = self._client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
            )
            reply = response.choices[0].message.content or ""
            messages.append({"role": "assistant", "content": reply})
            self._save_history(redis, talk_id, messages)
            return self._make_response_data(reply)
        except Exception:
            logger.exception("ChatGPT エラー")
            rd = ResponseData()
            rd.error_message = "エラーが発生しました。管理者にお知らせください。"
            return rd

    def system(self, message: str, channel) -> ResponseData:
        redis = self._get_redis_client(channel)
        talk_id = self._talk_id.get(channel, 1)
        messages = self._load_history(redis, talk_id)
        if not messages or messages[0]["role"] != "system":
            messages.insert(0, {"role": "system", "content": message})
        else:
            messages[0] = {"role": "system", "content": message}
        self._save_history(redis, talk_id, messages)
        return self._make_response_data(f"set system: {talk_id}")

    def list_talks(self, channel) -> ResponseData:
        redis = self._get_redis_client(channel)
        prefix = self._get_prefix(channel)
        ids = [k[len(prefix):] for k in redis.keys()]
        return self._make_response_data(str(ids))

    def detail(self, talk_id: str, channel) -> ResponseData:
        redis = self._get_redis_client(channel)
        messages = self._load_history(redis, talk_id)
        summary = [
            {"role": h["role"], "content": h["content"][: self.SUMMARY_MAX_LENGTH]}
            for h in messages
        ]
        return self._make_response_data(str(summary))

    def set_talk_id(self, talk_id: str, channel) -> ResponseData:
        try:
            self._talk_id[channel] = int(talk_id)
        except ValueError:
            rd = ResponseData()
            rd.error_message = f"IDが不正です: {talk_id}"
            return rd
        return self._make_response_data(f"set talk id: {self._talk_id[channel]}")

    def delete(self, talk_id: str, channel) -> ResponseData:
        try:
            numeric_id = int(talk_id)
        except ValueError:
            rd = ResponseData()
            rd.error_message = f"IDが不正です: {talk_id}"
            return rd
        redis = self._get_redis_client(channel)
        redis.del_(str(numeric_id))
        self._talk_id[channel] = 1
        return self._make_response_data(f"deleted id: {talk_id}")

    def clear(self, channel) -> ResponseData:
        redis = self._get_redis_client(channel)
        prefix = self._get_prefix(channel)
        for key in redis.keys():
            redis.del_(key[len(prefix):])
        self._talk_id[channel] = 1
        return self._make_response_data("cleared")

    def _get_redis_client(self, channel) -> RedisWrapper:
        return RedisWrapper(self._get_prefix(channel))

    def _get_prefix(self, channel) -> str:
        return f"{self.REDIS_KEY_PREFIX}{channel}_"

    def _make_response_data(self, text: str) -> ResponseData:
        rd = ResponseData()
        rd.templates = self._templates
        rd.data = {"text": text}
        return rd

    def _load_history(self, redis: RedisWrapper, id) -> list:
        content = redis.get(str(id))
        if not content:
            return []
        return json.loads(content)["history"]

    def _save_history(self, redis: RedisWrapper, id, messages: list):
        redis.set(str(id), json.dumps({"id": id, "history": messages}))
