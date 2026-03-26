import json
import logging
import os

import discord
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
}

processer = MessageProcesser(platform=PLATFORM, config=lib_config)
formatter = MessageFormatter(platform=PLATFORM)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    channel_id = message.channel.id
    response_data = processer.get_response_data(channel=channel_id, text=message.content)

    if response_data.error_message:
        await message.channel.send(response_data.error_message)
    elif response_data.data is not None:
        channel_config: dict[str, str] = servers.get(str(channel_id), {})
        response_type = channel_config.get("response_type", "default")
        response = formatter.get_response(response_data=response_data, response_type=response_type)
        while response:
            await message.channel.send(response[:MESSAGE_MAX_LENGTH])
            response = response[MESSAGE_MAX_LENGTH:]


token = os.environ.get("token")
if not token:
    raise ValueError("token environment variable is not set")

client.run(token)
