import asyncio
import datetime
import json
import os
import uuid

import websockets

from image_generator import ImageGenerator


class ImageServer:
    def __init__(self, hf_auth_token, port=5678):
        print("Initializing ImageServer")
        self.port = port
        self.image_generator = ImageGenerator(hf_auth_token)

    async def process_request(self, websocket):
        print("Waiting for request")
        request = await websocket.recv()
        prompt, actor_id = request.split('|', 1)

        print(f"Received prompt: {prompt} for actor: {actor_id}")

        print("Generating images")
        generated_images = self.image_generator.generate(prompt, websocket)
        print("Images generated")

        print("Sending progress update")
        await websocket.send(f"Progress: {100}%")

        print("Checking directories")
        if not os.path.exists("generated_images"):
            os.makedirs("generated_images")

        actor_dir = f"generated_images/{actor_id}"
        if not os.path.exists(actor_dir):
            os.makedirs(actor_dir)

        print("Saving generated images")
        generated_image_paths = []
        for generated_image in generated_images:
            image_path = self.save_generated_image(generated_image, actor_dir)
            generated_image_paths.append(image_path)

        print("Sending image paths")
        await websocket.send(json.dumps(generated_image_paths))

    def save_generated_image(self, generated_image, actor_dir):
        filename = f"{datetime.datetime.utcnow().isoformat()}-{str(uuid.uuid4())}.png"
        image_path = os.path.join(actor_dir, filename)
        print("Saving image: ", image_path)
        generated_image.save(image_path)
        return image_path

    def run(self):
        print("Starting server")
        start_server = websockets.serve(self.process_request, "0.0.0.0", self.port)

        print("Entering main event loop")
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()
