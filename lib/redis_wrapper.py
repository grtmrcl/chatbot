import redis


class RedisWrapper:
    def __init__(self, prefix: str):
        self._prefix = prefix
        self._client = redis.Redis()

    def get(self, key: str):
        value = self._client.get(self._prefix + key)
        return value.decode() if value else None

    def set(self, key: str, value: str):
        self._client.set(self._prefix + key, value)

    def keys(self) -> list[str]:
        return [k.decode() for k in self._client.scan_iter(self._prefix + "*")]  # type: ignore[union-attr]

    def del_(self, key: str):
        self._client.delete(self._prefix + key)
