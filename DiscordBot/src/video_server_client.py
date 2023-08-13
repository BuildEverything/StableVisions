import json

import websockets as websockets


class VideoServerClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    async def send_request(self, message, actor_id, options):
        try:
            websocket = await websockets.connect(f"ws://{self.host}:{self.port}", timeout=1200)
            await websocket.send(json.dumps({'prompt': message, 'actor_id': actor_id, 'options': options}))
            return websocket
        except ConnectionRefusedError:
            raise ConnectionRefusedError("Video server is not running. Please start the video server before running "
                                         "the bot.")
