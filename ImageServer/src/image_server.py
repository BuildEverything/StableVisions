import asyncio
import datetime
import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import websockets

from image_generator import ImageGenerator

logging.basicConfig(level=logging.DEBUG)


class ImageServer:
    def __init__(self, hf_auth_token, port=5678):
        logging.debug("Initializing ImageServer")
        self.port = port
        self.hf_auth_token = hf_auth_token
        self.executor = ThreadPoolExecutor()

    async def process_request(self, websocket):
        packet = await websocket.recv()
        logging.debug(f"Received packet: {packet}")

        await self.handle_image_generation_request(websocket, packet)

    async def handle_image_generation_request(self, websocket, packet):
        request_data = json.loads(packet)
        prompt, actor_id, options = request_data['prompt'], request_data['actor_id'], request_data['options']
        logging.debug(f"Received prompt: {prompt} for actor: {actor_id} with options: {options}")

        loop = asyncio.get_event_loop()
        image_paths = await loop.run_in_executor(self.executor, self.sync_image_generation, websocket, prompt, actor_id,
                                                 options)

        logging.debug("Sending image paths")
        await websocket.send(json.dumps({
            'type': 'complete',
            'image_paths': image_paths,
            'options': options,
        }))

    def sync_image_generation(self, websocket, prompt, actor_id, options):
        with ImageGenerator(self.hf_auth_token) as image_generator:
            logging.debug("Generating images")
            # Note: We cannot use await here, so you'll have to make the image generation call synchronous
            generated_images = image_generator.generate(prompt, websocket, options)
            logging.debug("Images generated")

            logging.debug("Checking directories")
            if not os.path.exists("generated_images"):
                os.makedirs("generated_images")

            actor_dir = f"generated_images/{actor_id}"
            if not os.path.exists(actor_dir):
                os.makedirs(actor_dir)

            logging.debug("Saving generated images")
            generated_image_paths = []
            for generated_image in generated_images:
                image_path = self.save_generated_image(generated_image, actor_dir)
                generated_image_paths.append(image_path)

            return generated_image_paths

    async def execute_image_generation(self, websocket, prompt, actor_id, options):
        with ImageGenerator(self.hf_auth_token) as image_generator:
            logging.debug("Generating images")
            generated_images = await asyncio.create_task(image_generator.generate(prompt, websocket, options))
            logging.debug("Images generated")

            logging.debug("Checking directories")
            if not os.path.exists("generated_images"):
                os.makedirs("generated_images")

            actor_dir = f"generated_images/{actor_id}"
            if not os.path.exists(actor_dir):
                os.makedirs(actor_dir)

            logging.debug("Saving generated images")
            generated_image_paths = []
            for generated_image in generated_images:
                image_path = self.save_generated_image(generated_image, actor_dir)
                generated_image_paths.append(image_path)

            return generated_image_paths

    def save_generated_image(self, generated_image, actor_dir):
        filename = f"{datetime.datetime.utcnow().isoformat()}-{str(uuid.uuid4())}.png"
        image_path = os.path.join(actor_dir, filename)
        logging.debug("Saving image: ", image_path)
        generated_image.save(image_path)
        return image_path

    def run(self):
        logging.debug("Starting server")
        start_server = websockets.serve(self.process_request, "0.0.0.0", self.port)

        logging.debug("Entering main event loop")
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()
