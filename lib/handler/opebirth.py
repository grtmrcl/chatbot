import logging
import os
from datetime import date, datetime
from typing import Any, Optional

import google.auth
import gspread
import yaml

from lib.response_data import ResponseData

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
DATE_INPUT_FORMATS = ["%m%d", "%m-%d"]

_TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "../../template.yml")


def _load_templates() -> dict[str, Any]:
    try:
        with open(_TEMPLATE_FILE) as f:
            return (yaml.safe_load(f) or {}).get("opebirth", {}).get("templates", {})
    except Exception:
        logger.exception("template.yml の読み込みエラー")
        return {}


_TEMPLATES = _load_templates()


def _parse_month_day(date_str: str) -> Optional[tuple[int, int]]:
    """mmdd または mm-dd をパースして (month, day) を返す。"""
    for fmt in DATE_INPUT_FORMATS:
        try:
            dt = datetime.strptime(date_str, fmt)
            return (dt.month, dt.day)
        except ValueError:
            continue
    return None


def _extract_month_day_from_cell(cell: str) -> Optional[tuple[int, int]]:
    """セルの誕生日文字列から (month, day) を抽出する。
    対応フォーマット:
      - X月Y日 (例: 3月27日)
      - yyyy/m/d (例: 2000/3/27)
      - m/d (例: 3/27)
    """
    cell = cell.strip()
    # X月Y日
    if "月" in cell and "日" in cell:
        try:
            month_part, rest = cell.split("月")
            day_part = rest.rstrip("日")
            return (int(month_part), int(day_part))
        except (ValueError, AttributeError):
            return None
    # スラッシュ区切り
    if "/" in cell:
        parts = cell.split("/")
        try:
            if len(parts) == 3:
                # yyyy/m/d
                return (int(parts[1]), int(parts[2]))
            elif len(parts) == 2:
                # m/d
                return (int(parts[0]), int(parts[1]))
        except ValueError:
            return None
    return None


class Opebirth:
    def __init__(self, config: dict):
        self._spreadsheets: dict[str, str | dict] = config.get("sss", {}).get("spreadsheets", {})
        self._client: Optional[gspread.Client] = None

    def _get_client(self) -> gspread.Client:
        if self._client is None:
            creds, _ = google.auth.default(scopes=SCOPES)
            self._client = gspread.authorize(creds)
        return self._client

    def _get_sheet(self, label: str) -> Optional[gspread.Worksheet]:
        entry = self._spreadsheets.get(label)
        if not entry:
            return None
        if isinstance(entry, str):
            return self._get_client().open_by_key(entry).sheet1
        sheet_id = entry.get("id", "")
        sheet_name = entry.get("sheet")
        wb = self._get_client().open_by_key(sheet_id)
        return wb.worksheet(sheet_name) if sheet_name else wb.sheet1

    def search_all(self, date_str: Optional[str] = None) -> ResponseData:
        """設定ファイルのすべての識別子に対して検索を実行する。"""
        response_data = ResponseData()
        response_data.templates = _TEMPLATES

        if date_str:
            md = _parse_month_day(date_str)
            if md is None:
                response_data.error_message = f"日付の形式が正しくありません: {date_str}（mmdd または mm-dd）"
                return response_data
            month, day = md
        else:
            today = date.today()
            month, day = today.month, today.day

        all_names: list[str] = []
        for label in self._spreadsheets:
            try:
                sheet = self._get_sheet(label)
                if sheet is None:
                    continue
                all_values = sheet.get_all_values()
                if not all_values:
                    continue
                headers = all_values[0]
                birth_col_idx = next((i for i, h in enumerate(headers) if h == "誕生日"), None)
                if birth_col_idx is None:
                    continue
                names = [
                    row[0]
                    for row in all_values[1:]
                    if len(row) > birth_col_idx
                    and row[0]
                    and _extract_month_day_from_cell(row[birth_col_idx]) == (month, day)
                ]
                all_names.extend(names)
            except Exception:
                logger.exception("opebirth エラー (label=%s)", label)

        if all_names:
            response_data.data = {"names": all_names}
        return response_data

    def search(self, label: str, date_str: Optional[str] = None) -> ResponseData:
        response_data = ResponseData()
        response_data.templates = _TEMPLATES

        if date_str:
            md = _parse_month_day(date_str)
            if md is None:
                response_data.error_message = f"日付の形式が正しくありません: {date_str}（mmdd または mm-dd）"
                return response_data
            month, day = md
        else:
            today = date.today()
            month, day = today.month, today.day

        try:
            sheet = self._get_sheet(label)
            if sheet is None:
                response_data.error_message = f"識別子 '{label}' が見つかりません。"
                return response_data

            all_values = sheet.get_all_values()
            if not all_values:
                return response_data

            headers = all_values[0]
            birth_col_idx = next((i for i, h in enumerate(headers) if h == "誕生日"), None)
            if birth_col_idx is None:
                response_data.error_message = "「誕生日」列が見つかりません。"
                return response_data

            names = [
                row[0]
                for row in all_values[1:]
                if len(row) > birth_col_idx
                and row[0]
                and _extract_month_day_from_cell(row[birth_col_idx]) == (month, day)
            ]

            if names:
                response_data.data = {"names": names}
        except Exception:
            logger.exception("opebirth エラー")
            response_data.error_message = "エラーが発生しました。管理者にお知らせください。"
        return response_data
