import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Optional

import google.auth
import gspread
import yaml

from lib.response_data import ResponseData

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DATE_INPUT_FORMATS = ["%Y%m%d", "%Y-%m-%d"]
DATE_OUTPUT_FORMAT = "%Y/%m/%d"

_TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "../../template.yml")


def _load_reminder_templates() -> dict[str, Any]:
    try:
        with open(_TEMPLATE_FILE) as f:
            return (yaml.safe_load(f) or {}).get("event_reminder", {}).get("templates", {})
    except Exception:
        logger.exception("template.yml の読み込みエラー")
        return {}


_REMINDER_TEMPLATES = _load_reminder_templates()


def _parse_date(date_str: str) -> Optional[date]:
    for fmt in DATE_INPUT_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


class Events:
    REGIST_TEMPLATES = {"default": "{{ data.message }}"}

    def __init__(self, config: dict):
        self._spreadsheets: dict[str, str | dict] = config.get("events", {}).get("spreadsheets", {})
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

    def regist(self, label: str, event_name: str, start_str: str, end_str: str) -> ResponseData:
        response_data = ResponseData()
        response_data.templates = self.REGIST_TEMPLATES

        start = _parse_date(start_str)
        if start is None:
            response_data.error_message = f"開始日の形式が正しくありません: {start_str}（yyyymmdd または yyyy-mm-dd）"
            return response_data

        end = _parse_date(end_str)
        if end is None:
            response_data.error_message = f"終了日の形式が正しくありません: {end_str}（yyyymmdd または yyyy-mm-dd）"
            return response_data

        try:
            sheet = self._get_sheet(label)
            if sheet is None:
                response_data.error_message = f"識別子 '{label}' が見つかりません。"
                return response_data

            all_values = sheet.get_all_values()
            for row in all_values[1:]:
                if row and row[0] == event_name:
                    response_data.data = {"message": f"「{event_name}」は既に登録されています。"}
                    return response_data

            sheet.append_row(
                [event_name, start.strftime(DATE_OUTPUT_FORMAT), end.strftime(DATE_OUTPUT_FORMAT)],
                value_input_option="RAW",
            )
            response_data.data = {
                "message": f"「{event_name}」を登録しました。（{start.strftime(DATE_OUTPUT_FORMAT)} ～ {end.strftime(DATE_OUTPUT_FORMAT)}）"
            }
        except Exception:
            logger.exception("event-register エラー")
            response_data.error_message = "エラーが発生しました。管理者にお知らせください。"
        return response_data

    def delete(self, label: str, event_name: str) -> ResponseData:
        response_data = ResponseData()
        response_data.templates = self.REGIST_TEMPLATES

        try:
            sheet = self._get_sheet(label)
            if sheet is None:
                response_data.error_message = f"識別子 '{label}' が見つかりません。"
                return response_data

            all_values = sheet.get_all_values()
            row_idx = next(
                (i + 2 for i, row in enumerate(all_values[1:]) if row and row[0] == event_name),
                None,
            )
            if row_idx is None:
                response_data.data = {"message": f"「{event_name}」は登録されていません。"}
                return response_data

            sheet.delete_rows(row_idx)
            response_data.data = {"message": f"「{event_name}」を削除しました。"}
        except Exception:
            logger.exception("event-delete エラー")
            response_data.error_message = "エラーが発生しました。管理者にお知らせください。"
        return response_data

    def reminder(self, label: str, date_str: Optional[str] = None) -> ResponseData:
        response_data = ResponseData()
        response_data.templates = _REMINDER_TEMPLATES

        if date_str:
            base_date = _parse_date(date_str)
            if base_date is None:
                response_data.error_message = f"日付の形式が正しくありません: {date_str}（yyyymmdd または yyyy-mm-dd）"
                return response_data
        else:
            base_date = date.today()

        notify_days = [1, 3]
        target_dates = {
            days: (base_date + timedelta(days=days)).strftime(DATE_OUTPUT_FORMAT)
            for days in notify_days
        }

        try:
            sheet = self._get_sheet(label)
            if sheet is None:
                response_data.error_message = f"識別子 '{label}' が見つかりません。"
                return response_data

            all_values = sheet.get_all_values()
            if not all_values:
                return response_data

            headers = all_values[0]
            end_col_idx = next((i for i, h in enumerate(headers) if h == "終了日"), None)
            if end_col_idx is None:
                response_data.error_message = "「終了日」列が見つかりません。"
                return response_data

            events = []
            for days, target_date in target_dates.items():
                for row in all_values[1:]:
                    if len(row) > end_col_idx and row[end_col_idx] == target_date and row[0]:
                        events.append({"name": row[0], "days": days})

            if events:
                response_data.data = {"events": events}
        except Exception:
            logger.exception("event-remind エラー")
            response_data.error_message = "エラーが発生しました。管理者にお知らせください。"
        return response_data
