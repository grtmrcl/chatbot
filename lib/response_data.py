from typing import Any, Optional


class ResponseData:
    def __init__(self):
        self.data: Any = None
        self.templates: Optional[dict[str, Any]] = None
        self.error_message: Optional[str] = None
        self.notice: Optional[str] = None
