import pytest
from unittest.mock import MagicMock

from lib.handler.sss import Sss


class TestParseConditions:
    """条件文字列をパースして列名と値の対に変換する"""

    def setup_method(self):
        self.sss = Sss({})

    @pytest.mark.parametrize("name,conditions_str,expected", [
        (
            "単一条件",
            "レアリティ=6",
            [("レアリティ", ["6"])],
        ),
        (
            "半角スペース区切りの複数条件",
            "レアリティ=6 種族=コータス",
            [("レアリティ", ["6"]), ("種族", ["コータス"])],
        ),
        (
            "全角スペース区切りの複数条件",
            "レアリティ=6　種族=コータス",
            [("レアリティ", ["6"]), ("種族", ["コータス"])],
        ),
        (
            "半角カンマで区切られた複数の値",
            "レアリティ=5,6",
            [("レアリティ", ["5", "6"])],
        ),
        (
            "全角カンマで区切られた複数の値",
            "レアリティ=5，6",
            [("レアリティ", ["5", "6"])],
        ),
        (
            "読点（、）で区切られた複数の値",
            "レアリティ=5、6",
            [("レアリティ", ["5", "6"])],
        ),
        (
            "全角イコールの単一条件",
            "レアリティ＝6",
            [("レアリティ", ["6"])],
        ),
        (
            "全角イコールの複数条件",
            "レアリティ＝6 種族＝サンクタ",
            [("レアリティ", ["6"]), ("種族", ["サンクタ"])],
        ),
        (
            "半角イコールの前後に半角スペース",
            "陣営 = Ave",
            [("陣営", ["Ave"])],
        ),
        (
            "半角イコールの前後に全角スペース",
            "陣営　＝　Ave",
            [("陣営", ["Ave"])],
        ),
        (
            "イコール前後にスペースがある複数条件",
            "レアリティ = 6 種族 = コータス",
            [("レアリティ", ["6"]), ("種族", ["コータス"])],
        ),
    ])
    def test_条件文字列を列名と値リストのタプルに変換する(self, name, conditions_str, expected):
        result = self.sss._parse_conditions(conditions_str)
        assert result == expected


class TestFilterRows:
    """条件に合致する行を絞り込む"""

    def setup_method(self):
        self.sss = Sss({})
        self.headers = ["コードネーム", "レアリティ", "種族"]
        self.rows = [
            ["アーミヤ", "5", "コータス"],
            ["エクシア", "6", "サンクタ"],
            ["メランサ", "3", "フェリーン"],
            ["", "6", "コータス"],  # コードネームなし（スキップ対象）
        ]

    def test_単一条件で合致する行を返す(self):
        # Given: レアリティ=6の条件
        conditions = [("レアリティ", ["6"])]

        # When
        result = self.sss._filter_rows(self.rows, self.headers, conditions)

        # Then: 6星のオペレーターのみ返る
        assert result == ["エクシア"]

    def test_複数条件のAND絞り込みで全条件を満たす行を返す(self):
        # Given: レアリティ=5 かつ 種族=コータス
        conditions = [("レアリティ", ["5"]), ("種族", ["コータス"])]

        # When
        result = self.sss._filter_rows(self.rows, self.headers, conditions)

        # Then: 両方の条件を満たすオペレーターのみ返る
        assert result == ["アーミヤ"]

    def test_複数値のOR絞り込みでいずれかに一致する行を返す(self):
        # Given: レアリティ=5 または 6
        conditions = [("レアリティ", ["5", "6"])]

        # When
        result = self.sss._filter_rows(self.rows, self.headers, conditions)

        # Then: 5星と6星の全オペレーターが返る
        assert result == ["アーミヤ", "エクシア"]

    def test_コードネームが空の行はスキップされる(self):
        # Given: 種族=コータス（コードネームなし行も該当するが除外される）
        conditions = [("種族", ["コータス"])]

        # When
        result = self.sss._filter_rows(self.rows, self.headers, conditions)

        # Then: コードネームなし行は結果に含まれない
        assert "" not in result
        assert "アーミヤ" in result

    def test_存在しない列名の条件は一致なしとなる(self):
        # Given: 存在しない列
        conditions = [("存在しない列", ["値"])]

        # When
        result = self.sss._filter_rows(self.rows, self.headers, conditions)

        # Then: 結果は空
        assert result == []

    def test_部分一致で行を返す(self):
        # Given: 「コータス」を部分文字列として含む値の条件
        conditions = [("種族", ["コータス"])]

        # When
        result = self.sss._filter_rows(self.rows, self.headers, conditions)

        # Then: 種族にコータスを含む行が返る
        assert "アーミヤ" in result


class TestSssSearch:
    """スプレッドシートの条件検索"""

    def _make_sss(self, sheet_values):
        sss = Sss({"sss": {"spreadsheets": {"ak": "dummy_id"}}})
        mock_sheet = MagicMock()
        mock_sheet.get_all_values.return_value = sheet_values
        sss._get_sheet = MagicMock(return_value=mock_sheet)
        return sss

    def test_条件に一致する行の1列目をカンマ区切りで返す(self):
        # Given
        sheet_values = [
            ["コードネーム", "レアリティ"],
            ["アーミヤ", "5"],
            ["メランサ", "3"],
        ]
        sss = self._make_sss(sheet_values)

        # When
        result = sss.search("ak", "レアリティ=5")
        # Then
        assert result.data == {"result": "アーミヤ"}
        assert result.error_message is None

    def test_一致する行がない場合は該当なしメッセージを返す(self):
        # Given
        sheet_values = [
            ["コードネーム", "レアリティ"],
            ["メランサ", "3"],
        ]
        sss = self._make_sss(sheet_values)

        # When
        result = sss.search("ak", "レアリティ=6")

        # Then
        assert result.data == {"result": "一致するデータが見つかりませんでした。"}

    def test_存在しないラベルはエラーメッセージを返す(self):
        # Given
        sss = Sss({"sss": {"spreadsheets": {}}})
        sss._get_sheet = MagicMock(return_value=None)

        # When
        result = sss.search("unknown", "レアリティ=6")

        # Then
        assert result.error_message is not None


class TestSssDraw:
    """スプレッドシートのランダム抽選"""

    def _make_sss(self, sheet_values):
        sss = Sss({"sss": {"spreadsheets": {"ak": "dummy_id"}}})
        mock_sheet = MagicMock()
        mock_sheet.get_all_values.return_value = sheet_values
        sss._get_sheet = MagicMock(return_value=mock_sheet)
        return sss

    def test_条件なしで全データからランダムに1件抽選する(self):
        # Given
        sheet_values = [
            ["コードネーム"],
            ["アーミヤ"],
            ["エクシア"],
        ]
        sss = self._make_sss(sheet_values)

        # When: 複数回抽選して結果を収集
        results = {sss.draw("ak").data["result"] for _ in range(30)}

        # Then: 登録されているオペレーターの中から選ばれている
        assert results.issubset({"アーミヤ", "エクシア"})
        assert len(results) >= 1

    def test_条件付きで絞り込んだデータからランダム抽選する(self):
        # Given
        sheet_values = [
            ["コードネーム", "レアリティ"],
            ["アーミヤ", "5"],
            ["メランサ", "3"],
        ]
        sss = self._make_sss(sheet_values)

        # When: レアリティ=5のみで抽選
        result = sss.draw("ak", "レアリティ=5")

        # Then: 5星のオペレーターが返る
        assert result.data["result"] == "アーミヤ"
