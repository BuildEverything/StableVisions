import asyncio
import json
import logging
import os.path
import time

import boto3
import discord
import openai
from discord import Intents, File
from discord.ext import commands

from dream_server_client import DreamServerClient
from hallucination import Hallucination
from input_handler import InputHandler
from video_server_client import VideoServerClient


class DiscordBot:
    def __init__(self,
                 discord_auth_token,
                 openai_api_token,
                 youtube_credentials_file,
                 image_server_host,
                 image_server_port,
                 video_server_host,
                 video_server_port,
                 aws_access_key_id,
                 aws_secret_access_key,
                 redis_client):
        intents = Intents.default()
        intents.message_content = True
        self.discord_api_token = discord_auth_token
        openai.api_key = openai_api_token
        self.youtube_credentials_file = youtube_credentials_file
        self.redis = redis_client
        self.dream_server_client = DreamServerClient(redis=self.redis, host=image_server_host, port=image_server_port)
        # self.mirage_server_client = MirageServerClient(video_server_host, video_server_port)
        self.video_server = VideoServerClient(video_server_host, video_server_port)
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
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
        steps = options.get('steps', 150)
        _, formatted_avg_duration = self.calc_formatted_avg_duration("mirage_avg_seconds_per_step", steps)
        status_message = await ctx.send(f'Mirage generation started... (ETA: {formatted_avg_duration})')

        try:
            generation_start_time = time.time()
            websocket = await self.video_server.send_request(prompt, actor_id, options)

            current_progress = [0]

            # avg_seconds_per_step, progress_indicator = await self.create_progress_indicator_task(
            #     status_message,
            #     'Mirage generation in progress.',
            #     'mirage_avg_seconds_per_step',
            #     steps
            # )

            async for packet in websocket:
                response = json.loads(packet)

                response_type = response['type']
                if response_type == 'progress':
                    progress_percentage = float(response['percentage'])
                    current_progress[0] = progress_percentage
                    continue

                elif response_type == 'complete':
                    generation_total_time = time.time() - generation_start_time
                    generation_seconds_per_step = generation_total_time / steps

                    await self.update_generative_task_metrics(
                        'mirage_record_count',
                        'mirage_avg_seconds_per_step',
                        generation_seconds_per_step,
                        generation_total_time)

                    # progress_indicator.cancel()

                    # Here I assume that the received message is a serialized list (JSON)
                    mirage_path = response['mirage_path']

                    await status_message.edit(content='Uploading your mirage to the cloud...')

                    boto_client = boto3.client('s3',
                                               aws_access_key_id=self.aws_access_key_id,
                                               aws_secret_access_key=self.aws_secret_access_key)

                    video_object_key = f'{actor_id}_{os.path.basename(mirage_path)}'

                    upload_succeeded = True
                    try:
                        boto_client.upload_file(
                            mirage_path,
                            'enchantus-visions-mirage-bucket',
                            video_object_key)
                    except Exception as e:
                        logging.error(f'Error uploading mirage to S3: {e}')
                        upload_succeeded = False

                    if not upload_succeeded:
                        await status_message.edit(
                            content=f'Mirage upload failed! Ask for help retrieving your mirage, {mirage_path}')
                        return

                    await status_message.edit(content='Mirage generation completed!')

                    video_url = f'https://enchantus-visions-mirage-bucket.s3.amazonaws.com/{video_object_key}'
                    options_string = " ".join(f'--{k} {v}' for k, v in options.items() if k != 'lucid')
                    repro_str = f'{prompt} {options_string}'

                    embedding = discord.Embed(
                        title=video_object_key,
                        description=prompt,
                        url=video_url,
                    )

                    await ctx.message.reply(
                        embed=embedding,
                        mention_author=True,
                        content=f'**What will your mirage show? Observe.** \n'
                                f'`id: {mirage_path}`\n'
                                f'`seed: {options["seed"]}`\n'
                                f'`repro: {repro_str}`\n'
                    )

                    await status_message.delete()
                    await websocket.close()
                    break

        except Exception as e:
            await ctx.message.reply(f'Error: {e}')
            raise e

    async def update_generative_task_metrics(self,
                                             metric_record_count_key,
                                             metric_avg_seconds_per_step_key,
                                             avg_seconds_per_step,
                                             generation_seconds_per_step):
        mirage_record_count = self.redis.get(metric_record_count_key)
        if mirage_record_count is None:
            mirage_record_count = 0
        else:
            mirage_record_count = int(mirage_record_count)
        mirage_record_count += 1
        self.redis.set(metric_record_count_key, mirage_record_count)
        sma_existing_record_section = (avg_seconds_per_step * (mirage_record_count - 1)) / mirage_record_count
        sma_existing_record_section += generation_seconds_per_step / mirage_record_count
        sma_existing_record_section /= mirage_record_count
        self.redis.set(metric_avg_seconds_per_step_key, sma_existing_record_section)

    async def create_progress_indicator_task(self,
                                             status_message,
                                             status_message_content,
                                             avg_seconds_key,
                                             steps):
        avg_seconds_per_step, formatted_time = self.calc_formatted_avg_duration(avg_seconds_key, steps)

        progress_indicator = asyncio.create_task(DiscordBot.in_progress_indicator_task(
            status_message=status_message,
            status_message_content=f'{status_message_content} Average time: {formatted_time}',
            token_sequence='⣷⣯⣟⡿⢿⣻⣽⣾⣽⣻⢿⡿⣟⣯',
            frame_duration=0.4,
            are_tokens_cumulative=False
        ))

        # token_sequence = '⣾⣿' '⣽⣿' '⣻⣿' '⢿⣿' '⡿⣿' '⣿⢿' '⣿⡿' '⣿⡿' '⣿⣟' '⣿⣯' '⣿⣷' '⣿⣾' '⣷⣿' \
        #                  '⣯⣿' '⣟⣿' '⣿⣻' '⣿⣽'

        return avg_seconds_per_step, progress_indicator

    async def mark_message_processing_complete(self, message):
        await message.remove_reaction('⏳', self.bot.user)
        await message.add_reaction('✅')

    async def mark_message_processing_failed(self, message):
        await message.remove_reaction('⏳', self.bot.user)
        await message.add_reaction('❌')

    async def mark_message_processing(self, message):
        await message.add_reaction('🦑')
        await message.add_reaction('⏳')
