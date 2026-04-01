import pytest
from unittest.mock import MagicMock

from lib.handler.opebirth import _parse_month_day, _extract_month_day_from_cell, Opebirth


class TestParseMonthDay:
    """入力文字列から月と日をパースする"""

    @pytest.mark.parametrize("name,date_str,expected", [
        ("mmdd形式（3月27日）", "0327", (3, 27)),
        ("mmdd形式（1月1日）", "0101", (1, 1)),
        ("mmdd形式（12月31日）", "1231", (12, 31)),
        ("mm-dd形式（3月27日）", "03-27", (3, 27)),
        ("mm-dd形式（1月1日）", "01-01", (1, 1)),
    ])
    def test_有効な日付文字列を月日タプルに変換する(self, name, date_str, expected):
        assert _parse_month_day(date_str) == expected

    @pytest.mark.parametrize("name,date_str", [
        ("不正な形式（スラッシュ区切り）", "03/27"),
        ("年月日形式", "20240327"),
        ("空文字", ""),
        ("文字列", "abc"),
    ])
    def test_無効な形式はNoneを返す(self, name, date_str):
        assert _parse_month_day(date_str) is None


class TestExtractMonthDayFromCell:
    """スプレッドシートのセル値から誕生日の月日を抽出する"""

    @pytest.mark.parametrize("name,cell,expected", [
        ("X月Y日形式", "3月27日", (3, 27)),
        ("前後にスペースがあるX月Y日形式", "  3月27日  ", (3, 27)),
        ("1桁月日のX月Y日形式", "1月1日", (1, 1)),
        ("2桁月日のX月Y日形式", "12月31日", (12, 31)),
        ("yyyy/m/d形式", "2000/3/27", (3, 27)),
        ("m/d形式", "3/27", (3, 27)),
        ("1桁月日のm/d形式", "1/1", (1, 1)),
    ])
    def test_誕生日セル値から月日を抽出する(self, name, cell, expected):
        assert _extract_month_day_from_cell(cell) == expected

    @pytest.mark.parametrize("name,cell", [
        ("月日を含まない文字列", "誕生日不明"),
        ("空文字", ""),
        ("数字のみ（mmdd形式）", "0327"),
        ("月だけで日がない", "3月"),
    ])
    def test_解釈できないセル値はNoneを返す(self, name, cell):
        assert _extract_month_day_from_cell(cell) is None


class TestOpebirthSearch:
    """特定のラベルのスプレッドシートから誕生日オペレーターを検索する"""

    def _make_opebirth(self, sheet_values):
        opebirth = Opebirth({"sss": {"spreadsheets": {"ak": "dummy_id"}}})
        mock_sheet = MagicMock()
        mock_sheet.get_all_values.return_value = sheet_values
        opebirth._get_sheet = MagicMock(return_value=mock_sheet)
        return opebirth

    def test_指定日に誕生日のオペレーターを返す(self):
        # Given: 3月27日生まれのオペレーターがいる
        sheet_values = [
            ["コードネーム", "誕生日"],
            ["アーミヤ", "3月27日"],
            ["エクシア", "1月1日"],
        ]
        opebirth = self._make_opebirth(sheet_values)

        # When: 3月27日で検索する
        result = opebirth.search("ak", "0327")

        # Then: 誕生日が一致するオペレーターのみ返る
        assert result.data == {"names": ["アーミヤ"]}
        assert result.error_message is None

    def test_複数オペレーターが同じ誕生日の場合全員返す(self):
        # Given: 同じ誕生日のオペレーターが複数いる
        sheet_values = [
            ["コードネーム", "誕生日"],
            ["オペレーターA", "3月27日"],
            ["オペレーターB", "2000/3/27"],
        ]
        opebirth = self._make_opebirth(sheet_values)

        # When
        result = opebirth.search("ak", "0327")

        # Then: 全員が返る
        assert result.data["names"] == ["オペレーターA", "オペレーターB"]

    def test_誕生日のオペレーターがいない日はデータなしを返す(self):
        # Given: 3月27日生まれがいないシート
        sheet_values = [
            ["コードネーム", "誕生日"],
            ["アーミヤ", "3月27日"],
        ]
        opebirth = self._make_opebirth(sheet_values)

        # When: 該当なしの日付で検索する
        result = opebirth.search("ak", "0101")

        # Then: dataはNone（結果なし）でエラーもない
        assert result.data is None
        assert result.error_message is None

    def test_無効な日付形式はエラーメッセージを返す(self):
        # Given
        opebirth = Opebirth({"sss": {"spreadsheets": {"ak": "dummy_id"}}})

        # When: 不正な形式で検索する
        result = opebirth.search("ak", "invalid")

        # Then: エラーメッセージが設定される
        assert result.error_message is not None

    def test_存在しないラベルはエラーメッセージを返す(self):
        # Given: 設定にないラベル
        opebirth = Opebirth({"sss": {"spreadsheets": {}}})
        opebirth._get_sheet = MagicMock(return_value=None)

        # When
        result = opebirth.search("unknown", "0327")

        # Then: エラーメッセージが設定される
        assert result.error_message is not None


class TestOpebirthSearchAll:
    """全ラベルにわたって誕生日オペレーターを検索する"""

    def test_複数ラベルを横断して誕生日オペレーターを返す(self):
        # Given: ak と ef の両方にオペレーターがいる
        opebirth = Opebirth({"sss": {"spreadsheets": {"ak": "id_ak", "ef": "id_ef"}}})

        def mock_get_sheet(label):
            mock = MagicMock()
            if label == "ak":
                mock.get_all_values.return_value = [
                    ["コードネーム", "誕生日"],
                    ["アーミヤ", "3月27日"],
                ]
            else:
                mock.get_all_values.return_value = [
                    ["コードネーム", "誕生日"],
                    ["EFオペレーター", "3月27日"],
                ]
            return mock

        opebirth._get_sheet = mock_get_sheet

        # When
        result = opebirth.search_all("0327")

        # Then: 全ラベルのオペレーターが返る
        assert set(result.data["names"]) == {"アーミヤ", "EFオペレーター"}

    def test_無効な日付形式はエラーメッセージを返す(self):
        # Given
        opebirth = Opebirth({"sss": {"spreadsheets": {"ak": "dummy_id"}}})

        # When
        result = opebirth.search_all("invalid")

        # Then
        assert result.error_message is not None
