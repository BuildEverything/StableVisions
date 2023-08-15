import os
import logging

import boto3
import openai
from dotenv import load_dotenv
from discord_bot import DiscordBot
from redis import Redis

from dream_server_client import DreamServerClient
from mirage_server_client import MirageServerClient

logging.basicConfig(level=logging.DEBUG)

if __name__ == "__main__":
    IMAGE_SERVER_HOST = os.getenv('IMAGE_SERVER_HOST')
    IMAGE_SERVER_PORT = os.getenv('IMAGE_SERVER_PORT')
    VIDEO_SERVER_HOST = os.getenv('MIRAGE_SERVER_HOST')
    VIDEO_SERVER_PORT = os.getenv('MIRAGE_SERVER_PORT')

    load_dotenv('.\\.env')
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    OPENAI_API_TOKEN = os.getenv('OPENAI_API_TOKEN')
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    REDIS_HOST = os.getenv('REDIS_HOST')
    REDIS_PORT = os.getenv('REDIS_PORT')
    REDIS_USERNAME = os.getenv('REDIS_USERNAME')

    redis_client = Redis(host=REDIS_HOST,
                         port=REDIS_PORT,
                         db=0)

    boto_client = boto3.client('s3',
                               aws_access_key_id=AWS_ACCESS_KEY_ID,
                               aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

    dream_server_client = DreamServerClient(redis=redis_client,
                                            host=IMAGE_SERVER_HOST,
                                            port=IMAGE_SERVER_PORT)

    mirage_server_client = MirageServerClient(redis=redis_client,
                                              host=VIDEO_SERVER_HOST,
                                              port=VIDEO_SERVER_PORT,
                                              boto_client=boto_client)

    openai.api_key = OPENAI_API_TOKEN

    bot = DiscordBot(discord_auth_token=DISCORD_BOT_TOKEN,
                     dream_server_client=dream_server_client,
                     mirage_server_client=mirage_server_client)
    bot.run()
