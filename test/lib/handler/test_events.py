import pytest
from datetime import date
from unittest.mock import MagicMock

from lib.handler.events import _parse_date, Events


class TestParseDate:
    """日付文字列をdateオブジェクトに変換する"""

    @pytest.mark.parametrize("name,date_str,expected", [
        ("yyyymmdd形式", "20240327", date(2024, 3, 27)),
        ("yyyy-mm-dd形式", "2024-03-27", date(2024, 3, 27)),
        ("年初", "20240101", date(2024, 1, 1)),
        ("年末", "20241231", date(2024, 12, 31)),
    ])
    def test_有効な日付文字列をdateオブジェクトに変換する(self, name, date_str, expected):
        assert _parse_date(date_str) == expected

    @pytest.mark.parametrize("name,date_str", [
        ("スラッシュ区切り", "2024/03/27"),
        ("空文字", ""),
        ("文字列", "abc"),
        ("mmdd形式（年なし）", "0327"),
    ])
    def test_無効な形式はNoneを返す(self, name, date_str):
        assert _parse_date(date_str) is None


class TestEventsRegister:
    """イベントをスプレッドシートに登録する"""

    def _make_events(self, existing_rows=None):
        events = Events({"events": {"spreadsheets": {"ak": "dummy_id"}}})
        mock_sheet = MagicMock()
        mock_sheet.get_all_values.return_value = existing_rows or [["イベント名", "開始日", "終了日"]]
        events._get_sheet = MagicMock(return_value=mock_sheet)
        return events, mock_sheet

    def test_新規イベントをスプレッドシートに追加する(self):
        # Given: まだ登録されていないイベント
        events, mock_sheet = self._make_events()

        # When: イベントを登録する
        result = events.register("ak", "新イベント", "20240401", "20240430")

        # Then: 行が追加され、成功メッセージが返る
        mock_sheet.append_row.assert_called_once()
        assert result.error_message is None
        assert "新イベント" in result.data["message"]

    def test_登録日がYYYY_MM_DD形式でも登録できる(self):
        # Given
        events, mock_sheet = self._make_events()

        # When: ハイフン区切りの日付で登録する
        result = events.register("ak", "新イベント", "2024-04-01", "2024-04-30")

        # Then: 正常に登録される
        mock_sheet.append_row.assert_called_once()
        assert result.error_message is None

    def test_既に登録済みのイベントは上書き登録される(self):
        # Given: 既に登録されているイベント
        existing_rows = [
            ["イベント名", "開始日", "終了日"],
            ["既存イベント", "2024/03/01", "2024/03/31"],
        ]
        events, mock_sheet = self._make_events(existing_rows)

        # When: 同じイベントを登録する
        result = events.register("ak", "既存イベント", "20240401", "20240430")

        # Then: append_rowは呼ばれず、updateで上書きされる
        mock_sheet.append_row.assert_not_called()
        mock_sheet.update.assert_called_once_with(
            "A2:D2",
            [["既存イベント", "2024/04/01", "2024/04/30", "TRUE"]],
            value_input_option="RAW",
        )
        assert "上書き登録しました" in result.data["message"]

    def test_無効な開始日形式はエラーメッセージを返す(self):
        # Given
        events, _ = self._make_events()

        # When
        result = events.register("ak", "イベント", "2024/04/01", "20240430")

        # Then
        assert result.error_message is not None

    def test_無効な終了日形式はエラーメッセージを返す(self):
        # Given
        events, _ = self._make_events()

        # When
        result = events.register("ak", "イベント", "20240401", "2024/04/30")

        # Then
        assert result.error_message is not None

    def test_存在しないラベルはエラーメッセージを返す(self):
        # Given: 設定にないラベル
        events = Events({"events": {"spreadsheets": {}}})
        events._get_sheet = MagicMock(return_value=None)

        # When
        result = events.register("unknown", "イベント", "20240401", "20240430")

        # Then
        assert result.error_message is not None


class TestEventsReminder:
    """終了日が近いイベントをリマインドする"""

    def _make_events(self, sheet_values):
        events = Events({"events": {"spreadsheets": {"ak": "dummy_id"}}})
        mock_sheet = MagicMock()
        mock_sheet.get_all_values.return_value = sheet_values
        events._get_sheet = MagicMock(return_value=mock_sheet)
        return events

    def test_1日後に終了するイベントが通知される(self):
        # Given: 基準日(2024/04/01)の1日後に終了するイベント
        sheet_values = [
            ["イベント名", "開始日", "終了日"],
            ["明日終了イベント", "2024/03/01", "2024/04/02"],
        ]
        events = self._make_events(sheet_values)

        # When
        result = events.reminder("ak", "20240401")

        # Then: 1日後終了のイベントが含まれる
        assert result.data is not None
        names = [e["name"] for e in result.data["events"]]
        days = [e["days"] for e in result.data["events"]]
        assert "明日終了イベント" in names
        assert 1 in days

    def test_3日後に終了するイベントが通知される(self):
        # Given: 基準日(2024/04/01)の3日後に終了するイベント
        sheet_values = [
            ["イベント名", "開始日", "終了日"],
            ["3日後終了イベント", "2024/03/01", "2024/04/04"],
        ]
        events = self._make_events(sheet_values)

        # When
        result = events.reminder("ak", "20240401")

        # Then
        names = [e["name"] for e in result.data["events"]]
        assert "3日後終了イベント" in names

    def test_終了日が近くないイベントは通知されない(self):
        # Given: 遠い将来に終了するイベント
        sheet_values = [
            ["イベント名", "開始日", "終了日"],
            ["まだ続くイベント", "2024/03/01", "2024/12/31"],
        ]
        events = self._make_events(sheet_values)

        # When
        result = events.reminder("ak", "20240401")

        # Then: データなし（通知なし）
        assert result.data is None

    def test_無効な日付形式はエラーメッセージを返す(self):
        # Given
        events = Events({"events": {"spreadsheets": {"ak": "dummy_id"}}})

        # When
        result = events.reminder("ak", "2024/04/01")

        # Then
        assert result.error_message is not None


class TestEventsDelete:
    """登録済みイベントを削除する"""

    def _make_events(self, existing_rows):
        events = Events({"events": {"spreadsheets": {"ak": "dummy_id"}}})
        mock_sheet = MagicMock()
        mock_sheet.get_all_values.return_value = existing_rows
        events._get_sheet = MagicMock(return_value=mock_sheet)
        return events, mock_sheet

    def test_登録済みイベントを削除できる(self):
        # Given: 登録されているイベント（2行目 → row_idx=2）
        existing_rows = [
            ["イベント名", "開始日", "終了日"],
            ["削除対象イベント", "2024/03/01", "2024/03/31"],
        ]
        events, mock_sheet = self._make_events(existing_rows)

        # When
        result = events.delete("ak", "削除対象イベント")

        # Then: 対象行が削除され、成功メッセージが返る
        mock_sheet.delete_rows.assert_called_once_with(2)
        assert "削除しました" in result.data["message"]

    def test_存在しないイベントの削除は登録なし旨のメッセージを返す(self):
        # Given: 空のシート
        existing_rows = [["イベント名", "開始日", "終了日"]]
        events, mock_sheet = self._make_events(existing_rows)

        # When
        result = events.delete("ak", "存在しないイベント")

        # Then: 削除は実行されない
        mock_sheet.delete_rows.assert_not_called()
        assert result.data is not None
