import random
import time

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


class YoutubeUploader:
    RETRIABLE_EXCEPTIONS = (
        IOError,
    )
    RETRIABLE_STATUS_CODES = [429, 500, 502, 503, 504]
    MAX_RETRIES = 10

    def __init__(self, youtube):
        self.youtube = youtube

    def upload_video(self, file_path, title, description, category='22', keywords='', privacyStatus='private'):
        tags = None
        if keywords:
            tags = keywords.split(',')

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': category
            },
            'status': {
                'privacyStatus': privacyStatus
            }
        }

        # Prepare the request
        request = self.youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
        )

        # Perform the upload
        return self.resumable_upload(request)

    def resumable_upload(self, request):
        response = None
        error = None
        retry = 0
        while response is None:
            try:
                print('Uploading file...')
                status, response = request.next_chunk()
                if 'id' in response:
                    print(f'Video id "{response["id"]}" was successfully uploaded.')
                    return response
                else:
                    raise Exception(f'The upload failed with an unexpected response: {response}')
            except HttpError as e:
                if e.resp.status in self.RETRIABLE_STATUS_CODES:
                    error = f'A retriable HTTP error {e.resp.status} occurred:\n{e.content}'
                else:
                    raise
            except self.RETRIABLE_EXCEPTIONS as e:
                error = f'A retriable error occurred: {e}'

            if error:
                print(error)
                retry += 1
                if retry > self.MAX_RETRIES:
                    raise Exception('No longer attempting to retry.')

                max_sleep = 2 ** retry
                sleep_seconds = random.random() * max_sleep
                print(f'Sleeping {sleep_seconds} seconds and then retrying...')
                time.sleep(sleep_seconds)