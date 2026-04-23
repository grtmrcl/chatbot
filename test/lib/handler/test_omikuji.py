import pytest

from lib.handler.omikuji import Omikuji


def _make_config(*types: str) -> dict:
    omikuji = {}
    for t in types:
        omikuji[t] = {"templates": {"default": ["A", "B", "C"]}}
    return {"omikuji": omikuji}


class TestOmikujiDraw:
    """おみくじを引く振る舞いを検証する"""

    def test_存在するタイプを指定するとテンプレートが返る(self):
        # Given
        omikuji = Omikuji(_make_config("unsei"))

        # When
        result = omikuji.draw("unsei")

        # Then
        assert result.error_message is None
        assert result.templates is not None

    def test_タイプ未指定のときデフォルトのunseiが使われる(self):
        # Given: unsei が存在するconfig
        omikuji = Omikuji(_make_config("unsei"))

        # When: タイプを指定しない
        result = omikuji.draw()

        # Then
        assert result.error_message is None
        assert result.templates is not None

    @pytest.mark.parametrize("name,type_", [
        ("存在しないタイプはエラー", "g1"),
        ("空文字はエラー", ""),
    ])
    def test_存在しないタイプを指定するとエラーメッセージが返る(self, name, type_):
        # Given
        omikuji = Omikuji(_make_config("unsei"))

        # When
        result = omikuji.draw(type_)

        # Then
        assert result.error_message == "そのおみくじは存在しません。"
        assert result.templates is None

    def test_テンプレートが空のタイプはエラーメッセージが返る(self):
        # Given: templatesキーがないconfig
        config = {"omikuji": {"broken": {"templates": {}}}}
        omikuji = Omikuji(config)

        # When
        result = omikuji.draw("broken")

        # Then
        assert result.error_message == "そのおみくじは存在しません。"

    def test_configがない場合はtemplate_ymlのデフォルト設定で動作する(self):
        # Given: configにomikujiキーがない → _DEFAULT_CONFIG（template.yml）を使う
        omikuji = Omikuji({})

        # When: template.ymlに存在するunseiを引く
        result = omikuji.draw("unsei")

        # Then
        assert result.error_message is None
        assert result.templates is not None

    @pytest.mark.parametrize("name,type_", [
        ("ak2604_stdタイプが存在する", "ak2604_std"),
        ("ak2604_midタイプが存在する", "ak2604_mid"),
    ])
    def test_template_ymlに定義されたタイプが正常に読み込まれる(self, name, type_):
        # Given: configなし → template.ymlのデフォルトを使用
        omikuji = Omikuji({})

        # When
        result = omikuji.draw(type_)

        # Then
        assert result.error_message is None
        assert result.templates is not None
        assert isinstance(result.templates.get("default"), list)
