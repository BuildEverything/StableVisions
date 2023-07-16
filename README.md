# Project: Image Generation Bot

This project contains a Discord bot and an image generation server. The bot takes a text prompt from the user and sends it to the server, which uses the Stable Diffusion model to generate an image from the text. The generated image is then sent back to the Discord bot and delivered to the user.

The project is structured in a way that it can be easily set up and run using Docker.

## Project Structure

- **DiscordBot**: Contains all the necessary files for running the Discord bot.
  - `Dockerfile`: Contains instructions to create the Docker image for the Discord bot.
  - `.env`: Contains environment variables such as the Discord bot token.
  - `requirements.txt`: Lists all Python dependencies required by the Discord bot.
  - `src`: Contains the source code for the Discord bot.

- **ImageServer**: Contains all the necessary files for running the image generation server.
  - `Dockerfile`: Contains instructions to create the Docker image for the image generation server.
  - `.env`: Contains environment variables such as the Hugging Face authentication token.
  - `requirements.txt`: Lists all Python dependencies required by the image generation server.
  - `src`: Contains the source code for the image generation server.

- `docker-compose.yml`: Defines services, networks, and volumes for Docker Compose.

## Setup and Running

1. Install Docker and Docker Compose.

2. Clone this repository and navigate to its root directory.

3. Replace `{MY_TOKEN}` in `DiscordBot/.env` and `ImageServer/.env` with your Discord bot token and Hugging Face authentication token, respectively.

4. Build and run the Docker services using Docker Compose:

```
docker-compose up --build
```

You should now have the Discord bot and image generation server running in separate Docker containers. The bot is ready to receive `/dream` commands on Discord, and the server is ready to process those commands and generate images.

**Note:** Make sure to replace `{MY_TOKEN}` with your actual tokens in the respective `.env` files.
