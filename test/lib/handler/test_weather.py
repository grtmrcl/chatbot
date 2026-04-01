import pytest

from lib.handler.weather import Weather


class TestRains:
    """降水確率が雨傘が必要なレベル（30%以上）かどうかを判定する"""

    def setup_method(self):
        self.weather = Weather({})

    @pytest.mark.parametrize("name,rain_probability,expected", [
        ("30%は雨あり（境界値）", ["30%"], True),
        ("50%は雨あり", ["50%"], True),
        ("100%は雨あり", ["100%"], True),
        ("29%は雨なし（境界値未満）", ["29%"], False),
        ("0%は雨なし", ["0%"], False),
        ("複数の時間帯で40%があれば雨あり", ["10%", "40%", "20%"], True),
        ("複数の時間帯がすべて30%未満なら雨なし", ["10%", "20%", "0%"], False),
        ("データなし（-）は雨なし", ["-"], False),
        ("空リストは雨なし", [], False),
    ])
    def test_降水確率のリストから雨の有無を判定する(self, name, rain_probability, expected):
        # When
        result = self.weather._rains(rain_probability)

        # Then
        assert result == expected
