import json

from discord import Intents, File
from discord.ext import commands

from image_server_client import ImageServerClient


class DiscordBot:
    def __init__(self, discord_auth_token, image_server_host, image_server_port):
        intents = Intents.default()
        intents.message_content = True
        self.token = discord_auth_token
        self.image_server = ImageServerClient(image_server_host, image_server_port)
        self.bot = commands.Bot(command_prefix='/',
                                intents=intents,
                                description='A bot that generates images from text prompts using the Stable Diffusion '
                                            'model.',
                                help_command=None)

        @self.bot.command(name='dream', help='Generates an image given a prompt')
        async def generate(ctx, *, message):
            await self.generate_image(ctx, message, ctx.message.author.id)

    def run(self):
        self.bot.run(self.token)

    async def generate_image(self, ctx, message, actor_id):
        websocket = await self.image_server.send_request(message, actor_id)

        await ctx.message.add_reaction('🦑')
        await ctx.message.add_reaction('⏳')
        status_message = await ctx.send('Image generation started...')

        async for message in websocket:
            if message.startswith("Progress:"):
                progress = float(message.split(":")[1].strip().strip("%"))
                await status_message.edit(content=f'Image generation progress: {progress:.2f}%')
            else:
                # Here I assume that the received message is a serialized list (JSON)
                image_paths = json.loads(message)
                await status_message.edit(content='Image generation completed!')
                for image_path in image_paths:
                    await ctx.message.reply(
                        file=File(image_path),
                        mention_author=True,
                        content=f'**Serving up a hot new image fresh out of the oven!** \n`*id: {image_path}*`'
                    )

        await ctx.message.remove_reaction('⏳', self.bot.user)
        await ctx.message.add_reaction('✅')
        await status_message.delete()

        await websocket.close()
