import asyncio
import datetime
import json
import logging
import os
import pathlib
import re
import zoneinfo

import discord
from discord.ext import tasks
from dotenv import load_dotenv

from lib.message_processer import MessageProcesser
from lib.message_formatter import MessageFormatter

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

PLATFORM = "discord"
MESSAGE_MAX_LENGTH = 2000

# 牌譜インポート設定
_paifu_dir = os.environ.get("PAIFU_DIR")
_amae_scripts_dir = os.environ.get("AMAE_KOROMO_SCRIPTS_DIR")
PAIFU_DIR = pathlib.Path(_paifu_dir).resolve() if _paifu_dir else None
AMAE_KOROMO_SCRIPTS_DIR = pathlib.Path(_amae_scripts_dir).resolve() if _amae_scripts_dir else None

# env vars からチャンネル設定を構築
# 例: DISCORD_SERVERS={"123456789012345678": {"response_type": "default"}}
servers: dict[str, dict[str, str]] = json.loads(os.environ.get("DISCORD_SERVERS", "{}"))

lib_config: dict[str, dict[str, str]] = {
    "brave_search": {
        "api_key": os.environ.get("BRAVE_SEARCH_API_KEY", ""),
    },
    "chatgpt": {
        "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),
    },
    "sss": {
        "spreadsheets": json.loads(os.environ.get("SSS_SPREADSHEETS", "{}")),
    },
    "events": {
        "spreadsheets": json.loads(os.environ.get("EVENTS_SPREADSHEETS", "{}")),
    },

}

processer = MessageProcesser(platform=PLATFORM, config=lib_config)
formatter = MessageFormatter(platform=PLATFORM)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


logger = logging.getLogger(__name__)

JST = zoneinfo.ZoneInfo("Asia/Tokyo")


def _resolve_channel(channel_id_str: str, channel_config: dict[str, str]):
    """チャンネルIDまたはサーバーIDからチャンネルを解決する。
    サーバーIDの場合は notify_channel_id を使用する。"""
    channel = client.get_channel(int(channel_id_str))
    if channel is not None:
        return channel
    # サーバーIDの場合は notify_channel_id を参照
    notify_channel_id = channel_config.get("notify_channel_id")
    if notify_channel_id:
        return client.get_channel(int(notify_channel_id))
    return None


@tasks.loop(time=datetime.time(12, 0, tzinfo=JST))
async def daily_event_remind():
    for channel_id_str, channel_config in servers.items():
        label_value = channel_config.get("event_remind_label")
        if not label_value:
            continue
        labels = label_value if isinstance(label_value, list) else [label_value]

        all_events: list[dict] = []
        last_response_data = None
        for label in labels:
            rd = processer._events.reminder(label)
            if rd.error_message:
                logger.error("event-remind エラー channel=%s label=%s: %s", channel_id_str, label, rd.error_message)
                continue
            last_response_data = rd
            if rd.data:
                all_events.extend(rd.data.get("events", []))

        if not all_events or last_response_data is None:
            continue
        last_response_data.data = {"events": all_events}
        response_type = channel_config.get("response_type", "default")
        response = formatter.get_response(response_data=last_response_data, response_type=response_type)
        if not response:
            continue
        channel = _resolve_channel(channel_id_str, channel_config)
        if channel is None:
            logger.warning("チャンネルが見つかりません: %s (notify_channel_id未設定の可能性)", channel_id_str)
            continue
        while response:
            await channel.send(response[:MESSAGE_MAX_LENGTH])
            response = response[MESSAGE_MAX_LENGTH:]


@tasks.loop(time=datetime.time(0, 0, tzinfo=JST))
async def daily_opebirth():
    for channel_id_str, channel_config in servers.items():
        label_value = channel_config.get("opebirth_label")
        if not label_value:
            continue
        labels = label_value if isinstance(label_value, list) else [label_value]

        all_names: list[str] = []
        last_response_data = None
        for label in labels:
            rd = processer._opebirth.search(label)
            if rd.error_message:
                logger.error("opebirth エラー channel=%s label=%s: %s", channel_id_str, label, rd.error_message)
                continue
            last_response_data = rd
            if rd.data:
                all_names.extend(rd.data.get("names", []))

        if not all_names or last_response_data is None:
            continue
        last_response_data.data = {"names": all_names}
        response_type = channel_config.get("response_type", "default")
        response = formatter.get_response(response_data=last_response_data, response_type=response_type)
        if not response:
            continue
        channel = _resolve_channel(channel_id_str, channel_config)
        if channel is None:
            logger.warning("チャンネルが見つかりません: %s (notify_channel_id未設定の可能性)", channel_id_str)
            continue
        while response:
            await channel.send(response[:MESSAGE_MAX_LENGTH])
            response = response[MESSAGE_MAX_LENGTH:]


@client.event
async def on_ready():
    logger.info("Logged in as %s", client.user)
    if not daily_event_remind.is_running():  # type: ignore[union-attr]
        daily_event_remind.start()  # type: ignore[union-attr]
    if not daily_opebirth.is_running():  # type: ignore[union-attr]
        daily_opebirth.start()  # type: ignore[union-attr]


_SAFE_FILENAME_RE = re.compile(r'^[\w\-\.]+\.json$')


async def _handle_paifu_import(message: discord.Message, attachments: list[discord.Attachment]) -> None:
    """@mention + .json添付ファイルで牌譜をインポートする。"""
    if PAIFU_DIR is None or AMAE_KOROMO_SCRIPTS_DIR is None:
        await message.reply("PAIFU_DIR / AMAE_KOROMO_SCRIPTS_DIR が設定されていません。")
        return

    PAIFU_DIR.mkdir(parents=True, exist_ok=True)
    saved_files: list[str] = []
    for attachment in attachments:
        if not _SAFE_FILENAME_RE.match(attachment.filename):
            await message.reply(f"不正なファイル名です: {attachment.filename}")
            return
        dest = PAIFU_DIR / attachment.filename
        try:
            data = await attachment.read()
            dest.write_bytes(data)
        except Exception:
            logger.exception("ファイル保存失敗: %s", attachment.filename)
            await message.reply(f"ファイル保存に失敗しました: {attachment.filename}")
            return
        saved_files.append(attachment.filename)
        logger.info("牌譜ファイルを保存: %s", dest)

    filenames = ",".join(saved_files)
    cmd = [
        "docker", "compose", "run", "--rm",
        "-e", "IMPORT_PAIFU=1",
        "-e", f"PAIFU_FILES={filenames}",
        "app", "node", "index.js",
    ]
    logger.info("docker compose実行 cwd=%s files=%s", AMAE_KOROMO_SCRIPTS_DIR, filenames)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(AMAE_KOROMO_SCRIPTS_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode(errors="replace").strip() if stdout else ""
        if proc.returncode == 0:
            await message.reply(f"インポート完了: {filenames}")
        else:
            logger.error("docker compose失敗 (returncode=%d): %s", proc.returncode, output)
            await message.reply(f"インポート失敗 (code={proc.returncode}): {filenames}")
    except Exception:
        logger.exception("docker compose実行エラー")
        await message.reply("インポート中にエラーが発生しました。")


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    channel_id = message.channel.id
    guild_id = message.guild.id if message.guild else None
    # チャンネルID優先、なければサーバーIDで判定
    if str(channel_id) in servers:
        channel_config: dict[str, str] = servers[str(channel_id)]
    elif guild_id and str(guild_id) in servers:
        channel_config = servers[str(guild_id)]
    else:
        return
    # bot自身のメッセージを削除するコマンド: del [件数] (デフォルト: 1)
    # 管理者権限またはメッセージ管理権限を持つユーザーのみ実行可能
    if m := re.match(r"^del(?:\s+(\d+))?$", message.content.strip()):
        if not message.author.guild_permissions.manage_messages:
            return
        count = int(m.group(1)) if m.group(1) else 1
        try:
            await message.delete()
        except discord.Forbidden:
            pass

        def is_bot(msg: discord.Message) -> bool:
            return msg.author == client.user

        deleted = 0
        async for msg in message.channel.history(limit=500):
            if is_bot(msg):
                try:
                    await msg.delete()
                except discord.Forbidden:
                    break
                deleted += 1
                if deleted >= count:
                    break
        return

    # @mention + .json添付ファイルで牌譜インポート（チャンネル設定で有効化されている場合のみ）
    if channel_config.get("paifu_import") and client.user in message.mentions:
        json_attachments = [a for a in message.attachments if a.filename.endswith(".json")]
        if json_attachments:
            await _handle_paifu_import(message, json_attachments)
            return

    response_data = processer.get_response_data(channel=channel_id, text=message.content)

    if response_data.error_message:
        await message.channel.send(response_data.error_message)
    elif response_data.data is not None:
        response_type = channel_config.get("response_type", "default")
        response = formatter.get_response(response_data=response_data, response_type=response_type)
        while response:
            await message.channel.send(response[:MESSAGE_MAX_LENGTH])
            response = response[MESSAGE_MAX_LENGTH:]


token = os.environ.get("token")
if not token:
    raise ValueError("token environment variable is not set")

client.run(token)
