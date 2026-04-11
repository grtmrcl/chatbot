import asyncio
import pathlib
import unittest.mock
import os
import pytest

import discord

# bot.pyはclient.run()を呼ぶため、importする前にtokenをセットしておく
with unittest.mock.patch.dict(os.environ, {"token": "dummy"}):
    with unittest.mock.patch("discord.Client.run"):
        import bot


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_attachment(filename: str, data: bytes = b"{}") -> unittest.mock.AsyncMock:
    attachment = unittest.mock.AsyncMock(spec=discord.Attachment)
    attachment.filename = filename
    attachment.read.return_value = data
    return attachment


def _make_message() -> unittest.mock.AsyncMock:
    message = unittest.mock.AsyncMock(spec=discord.Message)
    return message


class TestHandlePaifuImport:
    """牌譜インポート処理"""

    def test_PAIFU_DIRが未設定のときエラーを返す(self, tmp_path):
        # Given: PAIFU_DIR が None
        message = _make_message()
        attachments = [_make_attachment("game.json")]
        with unittest.mock.patch.object(bot, "PAIFU_DIR", None), \
             unittest.mock.patch.object(bot, "AMAE_KOROMO_SCRIPTS_DIR", tmp_path):
            # When
            _run(bot._handle_paifu_import(message, attachments))

        # Then: エラーメッセージをreply
        message.reply.assert_awaited_once()
        assert "PAIFU_DIR" in message.reply.call_args[0][0]

    def test_AMAE_KOROMO_SCRIPTS_DIRが未設定のときエラーを返す(self, tmp_path):
        # Given: AMAE_KOROMO_SCRIPTS_DIR が None
        message = _make_message()
        attachments = [_make_attachment("game.json")]
        with unittest.mock.patch.object(bot, "PAIFU_DIR", tmp_path), \
             unittest.mock.patch.object(bot, "AMAE_KOROMO_SCRIPTS_DIR", None):
            # When
            _run(bot._handle_paifu_import(message, attachments))

        # Then: エラーメッセージをreply
        message.reply.assert_awaited_once()
        assert "AMAE_KOROMO_SCRIPTS_DIR" in message.reply.call_args[0][0]

    @pytest.mark.parametrize("filename", [
        "../evil.json",
        "../../etc/passwd.json",
        "evil.json;rm -rf /",
        "evil.json|cat /etc/passwd",
        "evil json.json",  # スペース含む
        "evil.txt",        # .json以外
        "",
    ])
    def test_不正なファイル名のときエラーを返す(self, tmp_path, filename):
        # Given: 安全でないファイル名の添付ファイル
        message = _make_message()
        attachments = [_make_attachment(filename)]
        with unittest.mock.patch.object(bot, "PAIFU_DIR", tmp_path), \
             unittest.mock.patch.object(bot, "AMAE_KOROMO_SCRIPTS_DIR", tmp_path):
            # When
            _run(bot._handle_paifu_import(message, attachments))

        # Then: エラーメッセージをreply、docker composeは実行しない
        message.reply.assert_awaited_once()
        assert "不正なファイル名" in message.reply.call_args[0][0]

    def test_正常ケースでdockerコマンドが実行されインポート完了を返す(self, tmp_path):
        # Given: 正常なファイル名・docker compose成功
        paifu_dir = tmp_path / "paifu"
        scripts_dir = tmp_path / "scripts"
        message = _make_message()
        attachments = [_make_attachment("220428-abc.json", b'{"data": 1}')]

        mock_proc = unittest.mock.AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"done", None)

        with unittest.mock.patch.object(bot, "PAIFU_DIR", paifu_dir), \
             unittest.mock.patch.object(bot, "AMAE_KOROMO_SCRIPTS_DIR", scripts_dir), \
             unittest.mock.patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            # When
            _run(bot._handle_paifu_import(message, attachments))

        # Then: ファイルが保存されている
        assert (paifu_dir / "220428-abc.json").read_bytes() == b'{"data": 1}'
        # Then: docker compose run が正しい引数で呼ばれた
        mock_exec.assert_awaited_once()
        call_args = mock_exec.call_args[0]
        assert "docker" in call_args
        assert "IMPORT_PAIFU=1" in call_args
        assert "PAIFU_FILES=220428-abc.json" in call_args
        # Then: インポート完了をreply
        message.reply.assert_awaited_once()
        assert "インポート完了" in message.reply.call_args[0][0]

    def test_dockerコマンド失敗のときインポート失敗を返す(self, tmp_path):
        # Given: docker compose が非ゼロで終了
        paifu_dir = tmp_path / "paifu"
        scripts_dir = tmp_path / "scripts"
        message = _make_message()
        attachments = [_make_attachment("game.json")]

        mock_proc = unittest.mock.AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate.return_value = (b"error output", None)

        with unittest.mock.patch.object(bot, "PAIFU_DIR", paifu_dir), \
             unittest.mock.patch.object(bot, "AMAE_KOROMO_SCRIPTS_DIR", scripts_dir), \
             unittest.mock.patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            # When
            _run(bot._handle_paifu_import(message, attachments))

        # Then: インポート失敗をreply
        message.reply.assert_awaited_once()
        reply_text = message.reply.call_args[0][0]
        assert "インポート失敗" in reply_text
        assert "code=1" in reply_text

    def test_複数ファイルを同時にインポートできる(self, tmp_path):
        # Given: 複数の正常なファイル
        paifu_dir = tmp_path / "paifu"
        scripts_dir = tmp_path / "scripts"
        message = _make_message()
        attachments = [
            _make_attachment("game1.json", b'{"game": 1}'),
            _make_attachment("game2.json", b'{"game": 2}'),
        ]

        mock_proc = unittest.mock.AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"done", None)

        with unittest.mock.patch.object(bot, "PAIFU_DIR", paifu_dir), \
             unittest.mock.patch.object(bot, "AMAE_KOROMO_SCRIPTS_DIR", scripts_dir), \
             unittest.mock.patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            # When
            _run(bot._handle_paifu_import(message, attachments))

        # Then: 両ファイルが保存されている
        assert (paifu_dir / "game1.json").exists()
        assert (paifu_dir / "game2.json").exists()
        # Then: PAIFU_FILES にカンマ区切りで両ファイル名が含まれる
        call_args = mock_exec.call_args[0]
        paifu_files_arg = next(a for a in call_args if "PAIFU_FILES=" in a)
        assert "game1.json" in paifu_files_arg
        assert "game2.json" in paifu_files_arg

    def test_ファイル保存失敗のときエラーを返す(self, tmp_path):
        # Given: write_bytes が失敗する
        paifu_dir = tmp_path / "paifu"
        scripts_dir = tmp_path / "scripts"
        message = _make_message()
        attachments = [_make_attachment("game.json")]

        with unittest.mock.patch.object(bot, "PAIFU_DIR", paifu_dir), \
             unittest.mock.patch.object(bot, "AMAE_KOROMO_SCRIPTS_DIR", scripts_dir), \
             unittest.mock.patch("pathlib.Path.write_bytes", side_effect=OSError("disk full")), \
             unittest.mock.patch("asyncio.create_subprocess_exec") as mock_exec:
            # When
            _run(bot._handle_paifu_import(message, attachments))

        # Then: エラーをreplyし、docker composeは実行しない
        message.reply.assert_awaited_once()
        assert "ファイル保存に失敗しました" in message.reply.call_args[0][0]
        mock_exec.assert_not_awaited()
