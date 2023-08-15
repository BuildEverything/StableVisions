import asyncio
import logging
import os.path

import discord
from discord import Intents, File
from discord.ext import commands

from dream_server_client import DreamServerClient
from hallucination import Hallucination
from input_handler import InputHandler
from mirage_server_client import MirageServerClient


class DiscordBot:
    def __init__(self,
                 discord_auth_token: str,
                 dream_server_client: DreamServerClient,
                 mirage_server_client: MirageServerClient):
        intents = Intents.default()
        intents.message_content = True
        self.discord_api_token = discord_auth_token

        self.dream_server_client = dream_server_client
        self.mirage_server_client = mirage_server_client

        self.dreamers = {}

        self.bot = commands.Bot(command_prefix='/',
                                intents=intents,
                                description='A bot that generates images from text prompts using the Stable Diffusion '
                                            'model.',
                                help_command=None,
                                keep_alive=False)

        @self.bot.command(name='dream', help='Generates an image given a prompt')
        async def generate(ctx, *, message):
            await self.mark_message_processing(ctx.message)

            input_handler = InputHandler()
            prompt, options = input_handler.sanitize_input(message)
            await self.generate_image(ctx, prompt, ctx.message.author.id, options)
            await self.mark_message_processing_complete(ctx.message)

        @self.bot.command(name='hallucinate', help='Generates a hallucinated image given a prompt')
        async def generate(ctx, *, message):
            await self.mark_message_processing(ctx.message)

            input_handler = InputHandler()
            prompt, options = input_handler.sanitize_input(message)

            temperature = 0.9
            if 'lucid' in options:
                lucid = max(0.0, min(float(options['lucid']), 1.0))
                temperature = 1.0 - lucid

            negative_prompt = ""
            if 'negative_prompt' in options:
                negative_prompt = options['negative_prompt']

            hallucination = Hallucination(prompt, negative_prompt, temperature)
            transformed_prompt, transformed_negative_prompt, explanation = hallucination.run()
            await ctx.message.reply(f'We are coming out of the deep dream.\n'
                                    f'**Prompt:** {transformed_prompt}\n'
                                    f'**Negative:** {transformed_negative_prompt}\n'
                                    f'**Explanation:** {explanation}')

            options['negative_prompt'] = transformed_negative_prompt

            await self.generate_image(ctx, transformed_prompt, ctx.message.author.id, options)
            await self.mark_message_processing_complete(ctx.message)

        @self.bot.command(name='mirage', help='Generates a video given a prompt')
        async def generate(ctx, *, message):
            await self.mark_message_processing(ctx.message)

            input_handler = InputHandler()
            prompt, options = input_handler.sanitize_input(message)
            await self.generate_video(ctx, prompt, ctx.message.author.id, options)
            await self.mark_message_processing_complete(ctx.message)

    def run(self):
        self.bot.run(self.discord_api_token)

    async def generate_image(self, ctx, prompt, actor_id, options):
        steps = int(options['steps']) if 'steps' in options else None
        formatted_eta = self.dream_server_client.calc_formatted_eta(steps)
        status_message = await ctx.send(f'Dream generation started... (ETA: {formatted_eta})')

        image_paths = await self.dream_server_client.send_request(prompt, actor_id, options)
        await status_message.edit(content=f'Dream generation complete.')

        logging.debug(f'send image(s) to user')
        for image_path in image_paths:
            options_string = " ".join(f'--{k} {v}' for k, v in options.items() if k != 'lucid')
            repro_str = f'{prompt} {options_string}'
            await ctx.message.reply(
                embed=discord.Embed(
                    title=f'`id: {image_path}`',
                    description=f'`seed: {options["seed"]}`\n'
                                f'`repro: {repro_str}`\n'
                ),
                file=File(image_path),
                mention_author=True,
            )

        logging.debug(f'delete status_message')
        await status_message.delete()

    @staticmethod
    async def in_progress_indicator_task(status_message,
                                         status_message_content='Task in progress...',
                                         token_sequence='...',
                                         are_tokens_cumulative=True,
                                         frame_duration=1 / 24):
        assert (len(status_message_content) > 0)
        assert (len(token_sequence) > 0)
        assert (frame_duration > 0)

        while True:
            try:
                for i in range(len(token_sequence)):
                    await asyncio.sleep(frame_duration)
                    if are_tokens_cumulative:
                        await status_message.edit(content=f'{status_message_content} {token_sequence[:i]}')
                    else:
                        await status_message.edit(content=f'{status_message_content} {token_sequence[i]}')

            except Exception as e:
                logging.error(f'Progress indicator task encountered an error: {e}')
                break
            except asyncio.CancelledError:
                logging.debug('Progress indicator task cancelled.')
                break

    async def generate_video(self, ctx, prompt, actor_id, options):
        steps = int(options['steps']) if 'steps' in options else None
        formatted_eta = self.dream_server_client.calc_formatted_eta(steps)
        status_message = await ctx.send(f'Mirage generation started... (ETA: {formatted_eta})')

        mirage_path = await self.mirage_server_client.send_request(prompt, actor_id, options)

        # avg_seconds_per_step, progress_indicator = await self.create_progress_indicator_task(
        #     status_message,
        #     'Mirage generation in progress.',
        #     'mirage_avg_seconds_per_step',
        #     steps
        # )

        # progress_indicator.cancel()

        await status_message.edit(content='Uploading your mirage to the cloud...')

        video_url, upload_succeeded = self.mirage_server_client.upload_mirage(actor_id=actor_id,
                                                                              mirage_path=mirage_path)

        if not upload_succeeded:
            await status_message.edit(
                content=f'Mirage upload failed! Ask for help retrieving your mirage, {mirage_path}')
            return

        video_file = None
        if os.stat(mirage_path).st_size < 8 * 1024 * 1024:
            video_file_path = self.mirage_server_client.convert_to_webm(mirage_path)
            video_file = File(video_file_path)

        await status_message.edit(content='Mirage generation completed!')

        options_string = " ".join(f'--{k} {v}' for k, v in options.items() if k != 'lucid')
        repro_str = f'{prompt} {options_string}'

        embedding = discord.Embed(
            title=os.path.basename(mirage_path),
            description=prompt,
            url=video_url,
        )

        await ctx.message.reply(
            file=video_file,
            embed=embedding,
            mention_author=True,
            content=f'**What will your mirage show? Observe.** \n'
                    f'`id: {mirage_path}`\n'
                    f'`seed: {options["seed"]}`\n'
                    f'`repro: {repro_str}`\n'
        )

        await status_message.delete()

    # async def create_progress_indicator_task(self,
    #                                         status_message,
    #                                         status_message_content,
    #                                         avg_seconds_key,
    #                                         steps):
    #    avg_seconds_per_step, formatted_time = self.calc_formatted_avg_duration(avg_seconds_key, steps)
    #
    #    progress_indicator = asyncio.create_task(DiscordBot.in_progress_indicator_task(
    #        status_message=status_message,
    #        status_message_content=f'{status_message_content} Average time: {formatted_time}',
    #        token_sequence='⣷⣯⣟⡿⢿⣻⣽⣾⣽⣻⢿⡿⣟⣯',
    #        frame_duration=0.4,
    #        are_tokens_cumulative=False
    #    ))
    #
    #    # token_sequence = '⣾⣿' '⣽⣿' '⣻⣿' '⢿⣿' '⡿⣿' '⣿⢿' '⣿⡿' '⣿⡿' '⣿⣟' '⣿⣯' '⣿⣷' '⣿⣾' '⣷⣿' \
    #    #                  '⣯⣿' '⣟⣿' '⣿⣻' '⣿⣽'
    #
    #    return avg_seconds_per_step, progress_indicator

    async def mark_message_processing_complete(self, message):
        await message.remove_reaction('⏳', self.bot.user)
        await message.add_reaction('✅')

    async def mark_message_processing_failed(self, message):
        await message.remove_reaction('⏳', self.bot.user)
        await message.add_reaction('❌')

    async def mark_message_processing(self, message):
        await message.add_reaction('🦑')
        await message.add_reaction('⏳')
