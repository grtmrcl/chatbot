import logging
import random
import re
from typing import Optional

import google.auth
import gspread

from lib.response_data import ResponseData

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


class Sss:
    DEFAULT_TEMPLATES = {"default": "{{ data.result }}"}

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

    def search(self, label: str, conditions_str: str) -> ResponseData:
        response_data = ResponseData()
        response_data.templates = self.DEFAULT_TEMPLATES
        try:
            sheet = self._get_sheet(label)
            if sheet is None:
                response_data.error_message = f"識別子 '{label}' が見つかりません。"
                return response_data

            all_values = sheet.get_all_values()

            if not all_values:
                response_data.data = {"result": "データがありません。"}
                return response_data

            headers = all_values[0]
            rows = all_values[1:]

            conditions = self._parse_conditions(conditions_str)
            matched = self._filter_rows(rows, headers, conditions)

            if not matched:
                response_data.data = {"result": "一致するデータが見つかりませんでした。"}
            else:
                response_data.data = {"result": ", ".join(matched)}
        except Exception:
            logger.exception("SSS 検索エラー")
            response_data.error_message = "エラーが発生しました。管理者にお知らせください。"
        return response_data

    def draw(self, label: str, conditions_str: Optional[str] = None) -> ResponseData:
        response_data = ResponseData()
        response_data.templates = self.DEFAULT_TEMPLATES
        try:
            sheet = self._get_sheet(label)
            if sheet is None:
                response_data.error_message = f"識別子 '{label}' が見つかりません。"
                return response_data

            all_values = sheet.get_all_values()

            if not all_values:
                response_data.data = {"result": "データがありません。"}
                return response_data

            headers = all_values[0]
            rows = all_values[1:]

            if conditions_str:
                conditions = self._parse_conditions(conditions_str)
                candidates = self._filter_rows(rows, headers, conditions)
            else:
                candidates = [row[0] for row in rows if row and row[0]]

            if not candidates:
                response_data.data = {"result": "一致するデータが見つかりませんでした。"}
                return response_data

            response_data.data = {"result": random.choice(candidates)}
        except Exception:
            logger.exception("SSS おみくじエラー")
            response_data.error_message = "エラーが発生しました。管理者にお知らせください。"
        return response_data

    def _parse_conditions(self, conditions_str: str) -> list[tuple[str, list[str]]]:
        """
        '列名=値1,値2 列名2=値3' をパースして [(列名, [値1, 値2]), (列名2, [値3])] を返す。
        全角・半角スペースで条件を区切り、全角・半角カンマで値を区切る。
        """
        conditions: list[tuple[str, list[str]]] = []
        parts = re.split(r"[\s　]+", conditions_str.strip())
        for part in parts:
            m = re.search(r"[=＝]", part)
            if not m:
                continue
            col = part[: m.start()]
            val_str = part[m.end() :]
            values = re.split(r"[,，、]", val_str)
            values = [v for v in values if v]
            if col and values:
                conditions.append((col, values))
        return conditions

    def _filter_rows(
        self,
        rows: list[list[str]],
        headers: list[str],
        conditions: list[tuple[str, list[str]]],
    ) -> list[str]:
        """条件をすべて満たす行の1列目の値を返す。"""
        header_index: dict[str, int] = {h: i for i, h in enumerate(headers)}
        result: list[str] = []

        for row in rows:
            if not row or not row[0]:
                continue
            if all(
                self._row_matches_condition(row, header_index, col, values)
                for col, values in conditions
            ):
                result.append(row[0])

        return result

    def _row_matches_condition(
        self,
        row: list[str],
        header_index: dict[str, int],
        col: str,
        values: list[str],
    ) -> bool:
        """列 col の値がいずれかの values に部分一致すれば True。"""
        idx = header_index.get(col)
        if idx is None:
            return False
        cell_value = row[idx] if idx < len(row) else ""
        return any(v in cell_value for v in values)
