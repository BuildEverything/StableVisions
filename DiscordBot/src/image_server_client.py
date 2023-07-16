import json

import websockets as websockets


class ImageServerClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    async def send_request(self, message, actor_id, options):
        try:
            websocket = await websockets.connect(f"ws://{self.host}:{self.port}")
            await websocket.send(json.dumps({'prompt': message, 'actor_id': actor_id, 'options': options}))
            return websocket
        except ConnectionRefusedError:
            raise ConnectionRefusedError("Image server is not running. Please start the image server before running "
                                         "the bot.")
