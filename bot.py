import datetime
import json
import logging
import os
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


@tasks.loop(time=datetime.time(10, 0, tzinfo=JST))
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
    print(f"Logged in as {client.user}")
    if not daily_event_remind.is_running():  # type: ignore[union-attr]
        daily_event_remind.start()  # type: ignore[union-attr]
    if not daily_opebirth.is_running():  # type: ignore[union-attr]
        daily_opebirth.start()  # type: ignore[union-attr]


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
    # bot自身のメッセージを削除するコマンド: purge [件数] (デフォルト: 1)
    if m := re.match(r"^purge(?:\s+(\d+))?$", message.content.strip()):
        count = int(m.group(1)) if m.group(1) else 1
        try:
            await message.delete()
        except discord.Forbidden:
            pass
        deleted = 0
        async for msg in message.channel.history(limit=500):
            if msg.author == client.user:
                await msg.delete()
                deleted += 1
                if deleted >= count:
                    break
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
