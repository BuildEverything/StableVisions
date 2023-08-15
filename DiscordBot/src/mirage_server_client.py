import logging
import os
import subprocess

from ffmpeg import FFmpeg

from content_server_client import ContentServerClient


class MirageServerClient(ContentServerClient):
    server_type = "Mirage"
    default_steps = 150

    def __init__(self, redis, host, port, boto_client):
        super().__init__(redis, host, port)
        self.boto_client = boto_client

    async def handle_progress_update(self, data):
        # progress_percentage = float(data['percentage'])
        # await status_message.edit(content=f'{self.server_type} generation progress: {progress_percentage:.2f}%')
        pass

    async def handle_generation_complete(self, data):
        mirage_path = data['mirage_path']
        logging.debug(f'image_paths: {mirage_path}')
        return mirage_path

    def upload_mirage(self, actor_id, mirage_path) -> (str, bool):
        video_object_key = f'{actor_id}_{os.path.basename(mirage_path)}'

        try:
            self.boto_client.upload_file(
                mirage_path,
                'enchantus-visions-mirage-bucket',
                video_object_key)
        except Exception as e:
            logging.error(f'Error uploading mirage to S3: {e}')
            return '', False

        return f'https://enchantus-visions-mirage-bucket.s3.amazonaws.com/{video_object_key}', True

    @staticmethod
    def convert_to_webm(input_path: str) -> str:
        output_path = input_path.replace('.mp4', '.webm')

        ffmpeg = FFmpeg()

        # Setup input options
        input_options = {}
        ffmpeg.input(url=input_path, options=input_options)

        # Setup output options
        output_options = {
            "codec:v": "libvpx",
            "codec:a": "libvorbis",
            "vf": "scale=1280:-1",
            "preset": "veryslow",
            "b": "1500k"
        }
        ffmpeg.output(url=output_path, options=output_options)

        # Execute FFmpeg to perform the conversion
        ffmpeg.execute()

        return output_path

    @staticmethod
    def convert_to_av1(input_path: str) -> str:
        output_path = input_path.replace('.mp4', '.av1')

        ffmpeg = FFmpeg()

        # Setup input options
        input_options = {}
        ffmpeg.input(url=input_path, options=input_options)

        # Setup output options for AV1 codec. For audio, Opus is a good choice with AV1.
        output_options = {
            "codec:v": "libaom-av1",
            "codec:a": "libopus",
            "vf": "scale=1280:-1",  # Adjust as per requirements. AV1 is efficient for 4K, but this keeps it at 720p.
            "preset": "veryslow",
            # AV1 encoding can be slow. 'veryslow' will give better compression but might be really slow.
            "b:v": "1500k",  # Adjust video bitrate based on the desired file size and quality
            "b:a": "128k",  # Adjust audio bitrate for clarity. Opus is efficient, even at lower bitrates.
            "strict": "experimental",  # Sometimes necessary with certain FFmpeg builds for AV1
            "cpu-used": "4"  # This controls the encoding speed-to-compression ratio.
        }
        ffmpeg.output(url=output_path, options=output_options)

        # Execute FFmpeg to perform the conversion
        ffmpeg.execute()

        return output_path