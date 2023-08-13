import os
import logging
from dotenv import load_dotenv
from discord_bot import DiscordBot
from redis import Redis

logging.basicConfig(level=logging.DEBUG)

if __name__ == "__main__":
    IMAGE_SERVER_HOST = os.getenv('IMAGE_SERVER_HOST')
    IMAGE_SERVER_PORT = os.getenv('IMAGE_SERVER_PORT')
    VIDEO_SERVER_HOST = os.getenv('MIRAGE_SERVER_HOST')
    VIDEO_SERVER_PORT = os.getenv('MIRAGE_SERVER_PORT')

    load_dotenv('.\\.env')
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    OPENAI_API_TOKEN = os.getenv('OPENAI_API_TOKEN')
    YOUTUBE_CREDENTIALS_FILE = os.getenv('YOUTUBE_API_CREDENTIALS_FILE')
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    REDIS_HOST = os.getenv('REDIS_HOST')
    REDIS_PORT = os.getenv('REDIS_PORT')
    REDIS_USERNAME = os.getenv('REDIS_USERNAME')

    redis_client = Redis(host=REDIS_HOST,
                         port=REDIS_PORT,
                         db=0)

    bot = DiscordBot(DISCORD_BOT_TOKEN,
                     OPENAI_API_TOKEN,
                     YOUTUBE_CREDENTIALS_FILE,
                     IMAGE_SERVER_HOST,
                     IMAGE_SERVER_PORT,
                     VIDEO_SERVER_HOST,
                     VIDEO_SERVER_PORT,
                     AWS_ACCESS_KEY_ID,
                     AWS_SECRET_ACCESS_KEY,
                     redis_client)
    bot.run()
