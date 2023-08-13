import asyncio
import datetime
import json
import os
import uuid

import websockets

from mirage_generator import MirageGenerator
from diffusers.utils import export_to_video


class MirageServer:
    def __init__(self, hf_auth_token, port=5678):
        print("Initializing MirageServer")
        self.port = port
        self.hf_auth_token = hf_auth_token

    @staticmethod
    async def send_pong_periodically(websocket, interval=15):
        while True:
            await asyncio.sleep(interval)
            await websocket.pong()

    async def process_request(self, websocket):
        packet = await websocket.recv()
        print(f"Received packet: {packet}")

        if packet == "ping":
            print("Sending pong")
            await websocket.send("pong")
        else:
            await self.handle_mirage_generation_request(websocket, packet)

    async def handle_mirage_generation_request(self, websocket, packet):
        request_data = json.loads(packet)
        prompt, actor_id, options = request_data['prompt'], request_data['actor_id'], request_data['options']
        print(f"Received prompt: {prompt} for actor: {actor_id} with options: {options}")

        pong_task = asyncio.create_task(MirageServer.send_pong_periodically(websocket))
        mirage_path = await self.execute_mirage_generation(websocket, prompt, actor_id, options)
        pong_task.cancel()

        print("Sending video paths")
        await websocket.send(json.dumps({
            'type': 'complete',
            'mirage_path': mirage_path,
            'options': options,
        }))

    async def execute_mirage_generation(self, websocket, prompt, actor_id, options):
        with MirageGenerator(self.hf_auth_token) as mirage_generator:
            print("Generating mirage")
            generated_video_frames = \
                await asyncio.get_event_loop().run_in_executor(None,
                                                               lambda: mirage_generator.generate(prompt, options))
            print("Mirage generated")

            # print("Sending progress update")
            # packet = json.dumps({
            #     'type': 'progress',
            #     'percentage': 0.2
            # })
            # await websocket.send(packet)

            print("Checking directories")
            if not os.path.exists("generated_videos"):
                os.makedirs("generated_videos")

            actor_dir = f"generated_videos/{actor_id}"
            if not os.path.exists(actor_dir):
                os.makedirs(actor_dir)

            print("Saving generated videos")
            return self.save_generated_mirage(generated_video_frames, actor_dir)

    def save_generated_mirage(self, video_frames, actor_dir):
        filename = f"{datetime.datetime.utcnow().isoformat()}-{str(uuid.uuid4())}.mp4"
        video_path = os.path.join(actor_dir, filename)
        print("Saving video: ", video_path)
        video_path = export_to_video(video_frames=video_frames, output_video_path=video_path)
        return video_path

    def run(self):
        print("Starting server")
        start_server = websockets.serve(self.process_request, "0.0.0.0", self.port, ping_interval=60 * 5,
                                        ping_timeout=60 * 30)

        print("Entering main event loop")
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()
