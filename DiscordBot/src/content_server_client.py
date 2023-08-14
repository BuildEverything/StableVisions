import datetime
import json
import logging
import time

import websockets as websockets

from time_utility import TimeUtility


class ContentServerClient:
    def __init__(self, redis, host, port):
        self.redis = redis
        self.host = host
        self.port = port
        self.server_type = "UNASSIGNED_SERVER_TYPE"
        self.default_steps = 50

    async def send_request(self, prompt, actor_id, options):
        generation_start_time = time.time()

        try:
            async with websockets.connect(f"ws://{self.host}:{self.port}", timeout=1200) as websocket:
                steps = int(options.get('steps', self.default_steps))

                await websocket.send(json.dumps({'prompt': prompt, 'actor_id': actor_id, 'options': options}))
                async for message in websocket:
                    data = json.loads(message)
                    if data['type'] == 'progress':
                        await self.handle_progress_update(data)
                    elif data['type'] == 'complete':
                        logging.debug(f"{self.server_type} Generation complete: {data}")
                        generation_total_time = time.time() - generation_start_time
                        await self.update_generative_task_metrics(
                            generation_total_time / steps,
                            generation_total_time)

                        return await self.handle_generation_complete(data)

        except ConnectionRefusedError as e:
            logging.exception(f"{self.server_type} server is not running.")
            raise ConnectionRefusedError(
                f"{self.server_type} server is not running. Please start the "
                f"{self.server_type} server before running the bot.") from e
        except websockets.ConnectionClosedError as e:
            logging.exception(f"{self.server_type} server closed the connection.")
            raise websockets.ConnectionClosedError(
                f"{self.server_type} server closed the connection. Please start the "
                f"{self.server_type} server before running the bot.") from e
        except Exception as e:
            logging.exception(f"Exception while connecting to {self.server_type} server.")
            raise e

    async def handle_progress_update(self, data):
        raise NotImplementedError("Derived classes must implement this method.")

    async def handle_generation_complete(self, data):
        raise NotImplementedError("Derived classes must implement this method.")

    def calc_formatted_eta(self, steps=None):
        if steps is None:
            steps = self.default_steps

        avg_seconds_per_step = float(self.redis.get(f'{self.server_type}_avg_seconds_per_step') or 0)
        eta_seconds = avg_seconds_per_step * steps
        eta_delta = datetime.timedelta(seconds=eta_seconds)
        formatted_time = TimeUtility.format_timedelta(eta_delta)
        return eta_seconds, formatted_time

    async def update_generative_task_metrics(self,
                                             avg_seconds_per_step,
                                             generation_seconds_per_step):
        metric_record_count_key = f'{self.server_type}_record_count'
        metric_avg_seconds_per_step_key = f'{self.server_type}_avg_seconds_per_step'
        record_count = int(self.redis.get(metric_record_count_key) or 0) + 1
        self.redis.set(metric_record_count_key, record_count)

        sma_existing_record_section = (avg_seconds_per_step * (record_count - 1)) / record_count
        sma_existing_record_section += generation_seconds_per_step / record_count
        sma_existing_record_section /= record_count
        self.redis.set(metric_avg_seconds_per_step_key, sma_existing_record_section)
