import asyncio
import datetime
import gc
import io
import json
import logging
import os.path
import time
import redis

import boto3
import discord
import openai
from discord import Intents, File, ChannelType
from discord.ext import commands
# from tqdm.contrib.discord import tqdm, trange

from dreamer import Dreamer
from hallucination import Hallucination
from image_server_client import ImageServerClient
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
        self.image_server = ImageServerClient(image_server_host, image_server_port)
        self.video_server = VideoServerClient(video_server_host, video_server_port)
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.dreamers = {}
        self.redis_client = redis_client
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

    async def handle_rp_message(self, message):
        if message.author == self.bot.user:
            return

        await self.mark_message_processing(message)

        game_id = message.channel.id
        if game_id not in self.dreamers:
            self.dreamers[game_id] = Dreamer(game_id, 0.9)

        dreamer = self.dreamers[message.channel.id]

        explanation, message_to_players_header, message_to_players = dreamer.run(message.author.id, message.content)

        await message.channel.send(f'**{message_to_players_header}** \n{message_to_players}\n')

        debug_thread = await message.channel.create_thread(
            name="Dreamer [Debug]",
            type=ChannelType.public_thread
        )

        await debug_thread.send(
            f"**Explanation:** \n{explanation}\n\n"
            f"**Metadata:** \n{json.dumps(dreamer.meta_information)}\n\n"
            f"**World State Update:** \n{json.dumps(dreamer.world_state_update)}\n\n"
            f"**World State:** \n{json.dumps(dreamer.world_state.state)}\n\n"
        )

        await self.mark_message_processing_complete(message)

    def run(self):
        self.bot.run(self.discord_api_token)

    async def generate_image(self, ctx, prompt, actor_id, options):
        steps = 50
        if 'steps' in options:
            steps = int(options['steps'])

        try:
            generation_start_time = time.time()
            websocket = await self.image_server.send_request(prompt, actor_id, options)

            _, formatted_avg_duration = self.calc_formatted_avg_duration("dream_avg_seconds_per_step", steps)
            status_message = await ctx.send(
                f'Dream generation started... (ETA: {formatted_avg_duration})')

            # avg_seconds_per_step, progress_indicator = await self.create_progress_indicator_task(
            #     status_message,
            #     'Dream generation in progress.',
            #     'dream_avg_seconds_per_step',
            #     steps
            # )

            async for message in websocket:
                response = json.loads(message)

                if response['type'] == 'progress':
                    progress_percentage = float(response['percentage'])
                    await status_message.edit(content=f'Dream generation progress: {progress_percentage:.2f}%')

                elif response['type'] == 'complete':
                    image_paths = response['image_paths']
                    logging.debug(f'image_paths: {image_paths}')

                    generation_total_time = time.time() - generation_start_time
                    generation_seconds_per_step = generation_total_time / steps
                    logging.debug(f'generation_seconds_per_step: {generation_seconds_per_step}')

                    logging.debug(f'update_generative_task_metrics')
                    await self.update_generative_task_metrics(
                        'dream_record_count',
                        'dream_avg_seconds_per_step',
                        generation_seconds_per_step,
                        generation_total_time)

                    # logging.debug(f'cancel progress_indicator')
                    # if not progress_indicator.done():
                    #     progress_indicator.cancel()

                    logging.debug(f'edit status_message')
                    try:
                        await status_message.edit(content='Image generation completed!')
                    except Exception as e:
                        logging.error(f"Error editing status message: {e}")

                    logging.debug(f'send image(s) to user')
                    for image_path in image_paths:
                        options_string = " ".join(f'--{k} {v}' for k, v in options.items() if k != 'lucid')
                        repro_str = f'{prompt} {options_string}'
                        await ctx.message.reply(
                            file=File(image_path),
                            mention_author=True,
                            content=f'**Serving up a hot new image fresh out of the oven!** \n'
                                    f'`id: {image_path}`\n'
                                    f'`seed: {options["seed"]}`\n'
                                    f'`repro: {repro_str}`\n'
                        )

                    logging.debug(f'delete status_message')
                    await status_message.delete()
                    break

            logging.debug(f'close websocket')
            await websocket.close()

        except Exception as e:
            logging.error(f'Error generating dream: {e}')
            await ctx.message.reply(f'Error generating dream: {e}')

    # @staticmethod
    # async def spinner_task(current_progress, status_message):
    #     try:
    #         logging.debug('Spinner task started!')

    #         frame_duration = 1 / 24  # 24 frames per second

    #         buffer = io.StringIO()
    #         previous_progress = 0  # Track the previous progress

    #         # tqdm will write its output to the buffer
    #         with tqdm(total=100, file=buffer) as pbar:
    #             while True:
    #                 progress_diff = current_progress[0] - previous_progress
    #                 if progress_diff > 0:
    #                     pbar.update(progress_diff)
    #                     buffer.seek(0)
    #                     progress_string = buffer.readline().strip()
    #                     previous_progress = current_progress[0]  # Update the previous progress after updating the bar

    #                 logging.debug(f'Progress string: {progress_string}')
    #                 await status_message.edit(content=f'Mirage generation in progress... {progress_string}')
    #                 await asyncio.sleep(frame_duration)  # Sleep for 1/24 seconds to achieve 24 FPS

    #     except Exception as e:
    #         logging.error(f'Spinner task encountered an error: {e}')

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
        mirage_record_count = self.redis_client.get(metric_record_count_key)
        if mirage_record_count is None:
            mirage_record_count = 0
        else:
            mirage_record_count = int(mirage_record_count)
        mirage_record_count += 1
        self.redis_client.set(metric_record_count_key, mirage_record_count)
        sma_existing_record_section = (avg_seconds_per_step * (mirage_record_count - 1)) / mirage_record_count
        sma_existing_record_section += generation_seconds_per_step / mirage_record_count
        sma_existing_record_section /= mirage_record_count
        self.redis_client.set(metric_avg_seconds_per_step_key, sma_existing_record_section)

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

    def calc_formatted_avg_duration(self, avg_seconds_key, steps):
        avg_seconds_per_step = self.redis_client.get(avg_seconds_key)
        if avg_seconds_per_step is None:
            avg_seconds_per_step = 0
        else:
            avg_seconds_per_step = float(avg_seconds_per_step)

        def format_timedelta(td):
            minutes, seconds = divmod(td.seconds, 60)
            hours, minutes = divmod(minutes, 60)
            return f"{hours:02}:{minutes:02}:{seconds:02}"

        avg_seconds_per_step_delta = datetime.timedelta(seconds=(avg_seconds_per_step * steps))
        formatted_time = format_timedelta(avg_seconds_per_step_delta)
        return avg_seconds_per_step, formatted_time

    async def mark_message_processing_complete(self, message):
        await message.remove_reaction('⏳', self.bot.user)
        await message.add_reaction('✅')

    async def mark_message_processing_failed(self, message):
        await message.remove_reaction('⏳', self.bot.user)
        await message.add_reaction('❌')

    async def mark_message_processing(self, message):
        await message.add_reaction('🦑')
        await message.add_reaction('⏳')
