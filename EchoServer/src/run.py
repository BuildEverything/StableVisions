import os
from dotenv import load_dotenv
from mirage_server import MirageServer

load_dotenv('.\\.env')
HF_AUTH_TOKEN = os.getenv('HF_AUTH_TOKEN')
MIRAGE_SERVER_PORT = os.getenv('MIRAGE_SERVER_PORT')

if __name__ == "__main__":
    mirage_server = MirageServer(hf_auth_token=HF_AUTH_TOKEN, port=MIRAGE_SERVER_PORT)
    mirage_server.run()
