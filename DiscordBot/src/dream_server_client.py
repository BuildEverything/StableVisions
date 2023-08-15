import logging

from content_server_client import ContentServerClient


class DreamServerClient(ContentServerClient):
    server_type = "Dream"
    default_steps = 50

    async def handle_progress_update(self, data):
        # progress_percentage = float(data['percentage'])
        # await status_message.edit(content=f'{self.server_type} generation progress: {progress_percentage:.2f}%')
        pass

    async def handle_generation_complete(self, data):
        image_paths = data['image_paths']
        logging.debug(f'image_paths: {image_paths}')
        return image_paths
