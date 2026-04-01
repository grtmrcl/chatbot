import pytest

from lib.message_formatter import MessageFormatter
from lib.response_data import ResponseData


class TestMessageFormatterGetResponse:
    """テンプレートにデータを埋め込んでDiscordメッセージを生成する"""

    def setup_method(self):
        self.formatter = MessageFormatter("discord")

    def test_テンプレートにデータを埋め込んでメッセージを返す(self):
        # Given: シンプルなJinja2テンプレートとデータ
        response_data = ResponseData()
        response_data.templates = {"default": "こんにちは、{{ data.name }}さん！"}
        response_data.data = {"name": "アーミヤ"}

        # When
        result = self.formatter.get_response(response_data, "default")

        # Then
        assert result == "こんにちは、アーミヤさん！"

    def test_テンプレートがNoneの場合はエラーメッセージを返す(self):
        # Given: テンプレート未設定
        response_data = ResponseData()
        response_data.templates = None

        # When
        result = self.formatter.get_response(response_data, "default")

        # Then
        assert result == "テンプレートが見つかりません。"

    def test_存在しないテンプレートキーを指定するとエラーメッセージを返す(self):
        # Given: "default" しか定義されていないテンプレート
        response_data = ResponseData()
        response_data.templates = {"default": "テンプレート"}

        # When: 存在しないキーを指定する
        result = self.formatter.get_response(response_data, "nonexistent")

        # Then
        assert "テンプレートエラー" in result

    def test_リスト形式のテンプレートはランダムに1つ選ばれる(self):
        # Given: 複数の候補からなるテンプレートリスト
        response_data = ResponseData()
        response_data.templates = {"default": ["応答パターンA", "応答パターンB", "応答パターンC"]}
        response_data.data = {}

        # When: 十分な回数レンダリングする
        results = {self.formatter.get_response(response_data, "default") for _ in range(50)}

        # Then: 複数の異なる結果が得られる（ランダム選択が機能している）
        assert len(results) > 1

    def test_Emojiクラスを参照するテンプレートが正常にレンダリングされる(self):
        # Given: Emoji定数を利用するテンプレート
        response_data = ResponseData()
        response_data.templates = {"default": "{{ Emoji.NUMBER[1] }}番"}
        response_data.data = {}

        # When
        result = self.formatter.get_response(response_data, "default")

        # Then: Emoji定数が展開されている
        assert result == ":one:番"

    def test_dataがNoneでもエラーにならずレンダリングされる(self):
        # Given: dataなしのテンプレート
        response_data = ResponseData()
        response_data.templates = {"default": "固定メッセージ"}
        response_data.data = None

        # When
        result = self.formatter.get_response(response_data, "default")

        # Then
        assert result == "固定メッセージ"
