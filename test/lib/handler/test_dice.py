import pytest
from unittest.mock import patch

from lib.handler.dice import Dice


class TestDiceRoll:
    """ダイスロールの振る舞いを検証する"""

    def setup_method(self):
        self.dice = Dice({})

    @pytest.mark.parametrize("name,text,mocked_rolls,expected_text", [
        (
            "1個のサイコロを振って結果がテキストに反映される",
            "[1d6]",
            [3],
            "3",
        ),
        (
            "2個のサイコロを振って合計がテキストに反映される",
            "[2d6]",
            [3, 4],
            "7",
        ),
        (
            "プラス補正値が合計に加算される",
            "[1d6+3]",
            [4],
            "7",
        ),
        (
            "マイナス補正値が合計から減算される",
            "[1d6-2]",
            [5],
            "3",
        ),
        (
            "テキスト中のダイス記法が結果で置換される",
            "攻撃ダメージは[1d6]点です",
            [4],
            "攻撃ダメージは4点です",
        ),
        (
            "複数のダイス記法がそれぞれ独立して置換される",
            "[1d6]と[1d4]",
            [3, 2],
            "3と2",
        ),
        (
            "大文字Dのダイス記法も受け付ける",
            "[1D6]",
            [5],
            "5",
        ),
    ])
    def test_ダイス記法をロール結果のテキストに置換する(self, name, text, mocked_rolls, expected_text):
        # Given: ランダム結果を固定する
        with patch("random.randint", side_effect=mocked_rolls):
            # When: テキストをロールする
            result = self.dice.roll(text)

        # Then: ダイス記法が結果に置換され、エラーがない
        assert result.data["text"] == expected_text
        assert result.error_message is None

    @pytest.mark.parametrize("name,text", [
        ("個数が0のダイスはエラー", "[0d6]"),
        ("面数が0のダイスはエラー", "[1d0]"),
        ("個数が上限（100）を超えるとエラー", "[101d6]"),
        ("面数が上限（10000）を超えるとエラー", "[1d10001]"),
    ])
    def test_無効なダイスパラメータはエラーメッセージを返す(self, name, text):
        # When: 無効なパラメータでロールする
        result = self.dice.roll(text)

        # Then: エラーメッセージが設定され、データはない
        assert result.error_message is not None
        assert result.data is None

    def test_ダイス記法がないテキストはそのまま返る(self):
        # Given: ダイス記法を含まないテキスト
        text = "普通のメッセージです"

        # When
        result = self.dice.roll(text)

        # Then: テキストが変わらない
        assert result.data["text"] == text
        assert result.error_message is None

    def test_上限ちょうどのパラメータは正常にロールされる(self):
        # Given: 上限値ちょうどのダイス（100個、1万面）
        with patch("random.randint", return_value=1):
            result = self.dice.roll("[100d10000]")

        # Then: エラーなく結果が返る
        assert result.error_message is None
        assert result.data is not None
