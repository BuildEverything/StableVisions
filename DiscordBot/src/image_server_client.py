import websockets as websockets

from web_socket_context_manager import WebSocketContextManager


class ImageServerClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    async def send_request(self, prompt, actor_id):
        try:
            websocket = await websockets.connect(f"ws://{self.host}:{self.port}")
            await websocket.send(f"{prompt}|{actor_id}")
            return websocket
        except ConnectionRefusedError:
            raise ConnectionRefusedError("Image server is not running. Please start the image server before running "
                                         "the bot.")
