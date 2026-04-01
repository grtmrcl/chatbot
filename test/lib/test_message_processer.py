import pytest
from unittest.mock import MagicMock, patch

from lib.message_processer import MessageProcesser
from lib.response_data import ResponseData


def _make_processer():
    """外部依存をすべてモックしたMessageProcesserを生成する"""
    config = {}
    with (
        patch("lib.message_processer.ChatGPT"),
        patch("lib.message_processer.Dice"),
        patch("lib.message_processer.Omikuji"),
        patch("lib.message_processer.BraveSearch"),
        patch("lib.message_processer.Weather"),
        patch("lib.message_processer.Route"),
        patch("lib.message_processer.Sss"),
        patch("lib.message_processer.Events"),
        patch("lib.message_processer.Opebirth"),
    ):
        processer = MessageProcesser("discord", config)
    return processer


class TestMessageProcesserBraveSearch:
    """Web・画像・動画検索のルーティング"""

    def setup_method(self):
        self.processer = _make_processer()
        self.mock_result = ResponseData()

    @pytest.mark.parametrize("name,text,expected_kwargs", [
        ("google コマンドでWeb検索", "google 東京タワー", {"query": "東京タワー"}),
        ("brave コマンドでWeb検索", "brave 東京タワー", {"query": "東京タワー"}),
        ("g コマンドでWeb検索", "g 東京タワー", {"query": "東京タワー"}),
    ])
    def test_Web検索コマンドがBraveSearchにルーティングされる(self, name, text, expected_kwargs):
        # Given
        self.processer._brave.search = MagicMock(return_value=self.mock_result)  # type: ignore

        # When
        self.processer.get_response_data(None, text)

        # Then
        self.processer._brave.search.assert_called_once_with("東京タワー")

    def test_imageコマンドが画像検索にルーティングされる(self):
        # Given
        self.processer._brave.search = MagicMock(return_value=self.mock_result)  # type: ignore

        # When
        self.processer.get_response_data(None, "image 猫")

        # Then
        self.processer._brave.search.assert_called_once_with("猫", search_type="image")

    def test_iコマンドが画像検索にルーティングされる(self):
        self.processer._brave.search = MagicMock(return_value=self.mock_result)  # type: ignore
        self.processer.get_response_data(None, "i 犬")
        self.processer._brave.search.assert_called_once_with("犬", search_type="image")

    def test_wikiコマンドがwikiサイト検索にルーティングされる(self):
        self.processer._brave.search = MagicMock(return_value=self.mock_result)  # type: ignore
        self.processer.get_response_data(None, "wiki アークナイツ")
        self.processer._brave.search.assert_called_once_with("アークナイツ", site="wiki")

    def test_youtubeコマンドがYoutube動画検索にルーティングされる(self):
        self.processer._brave.search = MagicMock(return_value=self.mock_result)  # type: ignore
        self.processer.get_response_data(None, "youtube アークナイツ")
        self.processer._brave.search.assert_called_once_with(
            "アークナイツ", search_type="video", site="youtube"
        )

    def test_nicovideoコマンドがニコ動検索にルーティングされる(self):
        self.processer._brave.search = MagicMock(return_value=self.mock_result)  # type: ignore
        self.processer.get_response_data(None, "nicovideo アークナイツ")
        self.processer._brave.search.assert_called_once_with(
            "アークナイツ", search_type="video", site="nicovideo"
        )


class TestMessageProcesserWeather:
    """天気・エリア検索のルーティング"""

    def setup_method(self):
        self.processer = _make_processer()
        self.mock_result = ResponseData()

    def test_weatherコマンドが天気検索にルーティングされる(self):
        self.processer._weather.search = MagicMock(return_value=self.mock_result)  # type: ignore
        self.processer.get_response_data(None, "weather 東京")
        self.processer._weather.search.assert_called_once_with("東京")

    def test_weatherareaコマンドがエリア検索にルーティングされる(self):
        self.processer._weather.search_area = MagicMock(return_value=self.mock_result)  # type: ignore
        self.processer.get_response_data(None, "weatherarea 東京都")
        self.processer._weather.search_area.assert_called_once_with("東京都")


class TestMessageProcesserRoute:
    """乗換検索のルーティング"""

    def setup_method(self):
        self.processer = _make_processer()
        self.mock_result = ResponseData()
        self.processer._route.search = MagicMock(return_value=self.mock_result)  # type: ignore

    def test_から形式の乗換検索がルーティングされる(self):
        self.processer.get_response_data(None, "route 渋谷から新宿")
        self.processer._route.search.assert_called_once_with("渋谷", "新宿", None)  # type: ignore

    def test_スペース区切りの乗換検索がルーティングされる(self):
        self.processer.get_response_data(None, "route 渋谷 新宿")
        self.processer._route.search.assert_called_once_with("渋谷", "新宿", None)  # type: ignore

    def test_日本語の乗換コマンドがルーティングされる(self):
        self.processer.get_response_data(None, "乗換 渋谷から新宿")
        self.processer._route.search.assert_called_once_with("渋谷", "新宿", None)  # type: ignore

    def test_オプション付き乗換検索がルーティングされる(self):
        self.processer.get_response_data(None, "route 渋谷から新宿 発")
        self.processer._route.search.assert_called_once_with("渋谷", "新宿", "発")  # type: ignore


class TestMessageProcesserOmikuji:
    """おみくじのルーティング"""

    def setup_method(self):
        self.processer = _make_processer()
        self.mock_result = ResponseData()

    def test_omikujiコマンドがデフォルトタイプで引かれる(self):
        self.processer._omikuji.draw = MagicMock(return_value=self.mock_result)  # type: ignore
        self.processer.get_response_data(None, "omikuji")
        self.processer._omikuji.draw.assert_called_once_with("g1")

    def test_タイプ指定のomikujiコマンドがルーティングされる(self):
        self.processer._omikuji.draw = MagicMock(return_value=self.mock_result)  # type: ignore
        self.processer.get_response_data(None, "omikuji g2")
        self.processer._omikuji.draw.assert_called_once_with("g2")

    def test_opekujiコマンドがakラベルでSssのdrawにルーティングされる(self):
        self.processer._sss.draw = MagicMock(return_value=self.mock_result)  # type: ignore
        self.processer.get_response_data(None, "opekuji")
        self.processer._sss.draw.assert_called_once_with("ak", None)


class TestMessageProcesserEvents:
    """イベント管理のルーティング"""

    def setup_method(self):
        self.processer = _make_processer()
        self.mock_result = ResponseData()

    def test_event_registerコマンドがEventsのregisterにルーティングされる(self):
        self.processer._events.register = MagicMock(return_value=self.mock_result)  # type: ignore
        self.processer.get_response_data(None, "event-register ak イベント名 20240401 20240430")
        self.processer._events.register.assert_called_once_with("ak", "イベント名", "20240401", "20240430")

    def test_event_remindコマンドがEventsのreminderにルーティングされる(self):
        self.processer._events.reminder = MagicMock(return_value=self.mock_result)  # type: ignore
        self.processer.get_response_data(None, "event-remind ak")
        self.processer._events.reminder.assert_called_once_with("ak", None)

    def test_event_deleteコマンドがEventsのdeleteにルーティングされる(self):
        self.processer._events.delete = MagicMock(return_value=self.mock_result)  # type: ignore
        self.processer.get_response_data(None, "event-delete ak イベント名")
        self.processer._events.delete.assert_called_once_with("ak", "イベント名")


class TestMessageProcesserDice:
    """ダイスロールのルーティング"""

    def setup_method(self):
        self.processer = _make_processer()
        self.mock_result = ResponseData()
        self.processer._dice.roll = MagicMock(return_value=self.mock_result)  # type: ignore

    def test_ダイス記法を含むメッセージがDiceにルーティングされる(self):
        self.processer.get_response_data(None, "[2d6]")
        self.processer._dice.roll.assert_called_once_with("[2d6]")  # type: ignore

    def test_テキスト中のダイス記法もDiceにルーティングされる(self):
        self.processer.get_response_data(None, "攻撃: [1d20+5]")
        self.processer._dice.roll.assert_called_once_with("攻榇: [1d20+5]")  # type: ignore


class TestMessageProcesserSpecial:
    """特殊ケースのルーティング"""

    def setup_method(self):
        self.processer = _make_processer()
        self.mock_result = ResponseData()

    def test_どのコマンドにも一致しないと空のResponseDataを返す(self):
        # When: 認識できないメッセージ
        result = self.processer.get_response_data(None, "ただの会話")

        # Then: 空のResponseDataが返る
        assert result.data is None
        assert result.error_message is None

    def test_Reminderプレフィックスが除去されてルーティングされる(self):
        # Given
        self.processer._weather.search = MagicMock(return_value=self.mock_result)  # type: ignore

        # When: Discordのリマインダー形式のメッセージ
        self.processer.get_response_data(None, "Reminder weather 東京")

        # Then: Reminderが除去された上でルーティングされる
        self.processer._weather.search.assert_called_once_with("東京")

    def test_opebirthコマンドでsearch_allにルーティングされる(self):
        # Given
        self.processer._opebirth.search_all = MagicMock(return_value=self.mock_result)  # type: ignore

        # When: 引数なし
        self.processer.get_response_data(None, "opebirth")

        # Then
        self.processer._opebirth.search_all.assert_called_once_with()

    def test_日付付きopebirthコマンドでsearch_allにルーティングされる(self):
        self.processer._opebirth.search_all = MagicMock(return_value=self.mock_result)  # type: ignore
        self.processer.get_response_data(None, "opebirth 0327")
        self.processer._opebirth.search_all.assert_called_once_with("0327")
