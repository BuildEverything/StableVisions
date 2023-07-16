import os
from dotenv import load_dotenv
from discord_bot import DiscordBot


if __name__ == "__main__":
    IMAGE_SERVER_HOST = os.getenv('IMAGE_SERVER_HOST')
    IMAGE_SERVER_PORT = os.getenv('IMAGE_SERVER_PORT')

    load_dotenv('.\\.env')
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    OPENAI_API_TOKEN = os.getenv('OPENAI_API_TOKEN')

    bot = DiscordBot(DISCORD_BOT_TOKEN, OPENAI_API_TOKEN, IMAGE_SERVER_HOST, IMAGE_SERVER_PORT)
    bot.run()
