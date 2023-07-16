import websockets


class WebSocketContextManager:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    async def __aenter__(self):
        self.websocket = await websockets.connect(f"ws://{self.host}:{self.port}")
        return self.websocket

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.websocket.close()
        self.websocket = None