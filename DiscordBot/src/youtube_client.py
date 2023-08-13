import os
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import googleapiclient.discovery
import googleapiclient.errors

from youtube_uploader import YoutubeUploader

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YoutubeClient:
    def __init__(self, credentials_file):
        self.youtube = YoutubeClient.authorize(credentials_file)
        self.uploader = YoutubeUploader(self.youtube)

    def upload_video(self, file_path, title, description, category='22', keywords='', privacyStatus='private'):
        response = self.uploader.upload_video(file_path, title, description, category, keywords, privacyStatus)
        return self.get_video_url(response['id'])

    @staticmethod
    def authorize(credentials_file):
        credentials = YoutubeClient.generate_authentication_token(credentials_file)
        return googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

    @staticmethod
    def generate_authentication_token(credentials_file):
        credentials = None
        if os.path.exists('token.json'):
            credentials = Credentials.from_authorized_user_file('token.json', SCOPES)
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
                credentials = flow.run_local_server(port=0)

            with open('token.json', 'w') as token:
                token.write(credentials.to_json())

        return credentials

    @staticmethod
    def get_video_url(video_id):
        return f"https://www.youtube.com/watch?v={video_id}"
