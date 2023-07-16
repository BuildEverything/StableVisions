import os
from dotenv import load_dotenv
from image_server import ImageServer

load_dotenv('.\\.env')
HF_AUTH_TOKEN = os.getenv('HF_AUTH_TOKEN')

if __name__ == "__main__":
    image_server = ImageServer(hf_auth_token=HF_AUTH_TOKEN)
    image_server.run()
