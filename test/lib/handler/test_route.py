import pytest
from datetime import datetime

from lib.handler.route import Route


class TestParseOptions:
    """乗換検索のオプション文字列を解析する"""

    def setup_method(self):
        self.route = Route({})
        # 基準日時: 2024/04/01 10:30
        self.now = datetime(2024, 4, 1, 10, 30)

    @pytest.mark.parametrize("name,options,expected_type", [
        ("オプションなしはデフォルト着時刻", None, "4"),
        ("「発」は出発時刻指定", "発", "1"),
        ("「着」は到着時刻指定", "着", "4"),
        ("「始発」は始発検索", "始発", "8"),
        ("「終電」は終電検索", "終電", "16"),
    ])
    def test_検索タイプが正しく解析される(self, name, options, expected_type):
        # When
        result = self.route._parse_options(options, self.now)

        # Then
        assert result["type"] == expected_type

    def test_オプションなしは現在日時が使われる(self):
        # When
        result = self.route._parse_options(None, self.now)

        # Then: 基準日時の各フィールドが設定される
        assert result["y"] == "2024"
        assert result["m"] == "04"
        assert result["d"] == "01"
        assert result["hh"] == "10"
        assert result["m1"] == "3"
        assert result["m2"] == "0"

    def test_8桁の日付オプションで日付を上書きする(self):
        # Given: 日付オプション
        options = "20240615"

        # When
        result = self.route._parse_options(options, self.now)

        # Then: 指定した日付に変わる
        assert result["y"] == "2024"
        assert result["m"] == "06"
        assert result["d"] == "15"

    def test_4桁の時刻オプションで時刻を上書きする(self):
        # Given: 時刻オプション
        options = "1430"

        # When
        result = self.route._parse_options(options, self.now)

        # Then: 指定した時刻に変わる
        assert result["hh"] == "14"
        assert result["m1"] == "3"
        assert result["m2"] == "0"

    def test_1分台の時刻は先頭ゼロ埋めされる(self):
        # Given: 08:05 の時刻オプション
        options = "0805"

        # When
        result = self.route._parse_options(options, self.now)

        # Then: 分が2桁表現される
        assert result["hh"] == "08"
        assert result["m1"] == "0"
        assert result["m2"] == "5"

    def test_終電は時刻指定があっても現在時刻が使われる(self):
        # Given: 終電 + 時刻オプションを同時に指定
        options = "終電 1430"

        # When
        result = self.route._parse_options(options, self.now)

        # Then: typeは終電で、時刻は現在時刻のまま
        assert result["type"] == "16"
        assert result["hh"] == "10"
        assert result["m1"] == "3"

    def test_終電検索では時刻指定が無視される(self):
        # Given: 終電 + 時刻オプション
        options = "終電 2359"

        # When
        result = self.route._parse_options(options, self.now)

        # Then: typeは終電で、時刻は現在時刻のまま
        assert result["type"] == "16"
        assert result["hh"] == "10"

    def test_日付と時刻と検索タイプを同時に指定できる(self):
        # Given: 全オプション同時指定
        options = "20240615 1430 発"

        # When
        result = self.route._parse_options(options, self.now)

        # Then: 全て反映される
        assert result["y"] == "2024"
        assert result["m"] == "06"
        assert result["d"] == "15"
        assert result["hh"] == "14"
        assert result["type"] == "1"
