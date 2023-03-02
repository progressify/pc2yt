import argparse
import httplib2
import os
import random
import time
import subprocess

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from oauth2client import client
from oauth2client import file
from oauth2client import tools

from decouple import config
import requests
import feedparser

FEED_URL = config('FEED_URL')
PRIVACY_STATUS = config('PRIVACY_STATUS', default='private')
SOURCE_BACKGROUND_IMAGE = config('SOURCE_BACKGROUND_IMAGE', default='background.gif')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIOS_DIR = os.path.join(BASE_DIR, 'audios')
VIDEOS_DIR = os.path.join(BASE_DIR, 'videos')
BACKGROUND_IMAGE = os.path.join(BASE_DIR, SOURCE_BACKGROUND_IMAGE)
IS_GIF_BACKGROUND = ".gif" in BACKGROUND_IMAGE
LAST_PODCAST_FILE = os.path.join(BASE_DIR, '.last')

httplib2.RETRIES = 1
MAX_RETRIES = 10
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, 'client_secret.json')
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'youtube.dat')
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'
VALID_PRIVACY_STATUSES = ('public', 'private', 'unlisted')


class Podcast(object):
    def __init__(self, title, description, url):
        self.title = title
        self.description = description
        self.url = url
        self.category = '22'  # see youtube categories IDs
        self.keywords = ''
        self.privacy_status = PRIVACY_STATUS
        self.video_file = None
        self.audio_file = None


def get_authenticated_service():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[tools.argparser]
    )
    flags = parser.parse_args([])

    flow = client.flow_from_clientsecrets(
        CLIENT_SECRETS_FILE,
        scope=SCOPES,
        message=tools.message_if_missing(CLIENT_SECRETS_FILE)
    )

    storage = file.Storage(CREDENTIALS_FILE)
    credentials = storage.get()
    if credentials is None or credentials.invalid:
        credentials = tools.run_flow(flow, storage)
    http = credentials.authorize(http=httplib2.Http())

    youtube = build(API_SERVICE_NAME, API_VERSION, http=http)

    return youtube


def initialize_upload(youtube, options):
    tags = None
    if options.keywords:
        tags = options.keywords.split(',')
    body = dict(
        snippet=dict(
            title=options.title,
            description=options.description,
            tags=tags,
            categoryId=options.category
        ),
        status=dict(
            privacyStatus=options.privacy_status
        )
    )
    insert_request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=MediaFileUpload(
            options.video_file,
            chunksize=-1,
            resumable=True
        )
    )
    resumable_upload(insert_request)


def resumable_upload(request):
    response = None
    error = None
    retry = 0
    while response is None:
        try:
            print('Uploading file...')
            status, response = request.next_chunk()
            if response is not None:
                if 'id' in response:
                    print(f'Video id "{response["id"]}" was successfully uploaded.')
                else:
                    exit(f'The upload failed with an unexpected response: {response}')
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = f'A retriable HTTP error {e.resp.status} occurred:\n{e.content}'
            else:
                raise
        except Exception as e:
            error = f'A retriable error occurred: {e}'

        if error is not None:
            print(error)
            retry += 1
            if retry > MAX_RETRIES:
                exit('No longer attempting to retry.')

            max_sleep = 2 ** retry
            sleep_seconds = random.random() * max_sleep
            print(f'Sleeping {sleep_seconds} seconds and then retrying...')
            time.sleep(sleep_seconds)


def get_latest_podcasts():
    latest_episodes = list()

    last = None
    if os.path.exists(LAST_PODCAST_FILE):
        with open(LAST_PODCAST_FILE, 'r') as f:
            last = f.read()
            last = ''.join(last.splitlines())

    d = feedparser.parse(FEED_URL)
    for entry in d['entries']:
        if entry['id'] != last:
            url = None
            for link in entry['links']:
                if link['type'] == 'audio/mpeg':
                    url = link['href']
                    break
            if url is not None:
                podcast = Podcast(title=entry['title'], description=entry['subtitle'], url=url)
                latest_episodes.append(podcast)
        else:
            break

    last = d['entries'][0]['id']
    with open(LAST_PODCAST_FILE, 'w') as f:
        f.write(last)

    if latest_episodes:
        print(f'Found {len(latest_episodes)} new podcasts.')
    else:
        print(f'Nothing new here. Last podcast uploaded to YouTube was {last}')

    return latest_episodes


def download_podcasts(podcasts):
    for podcast in podcasts:
        podcast.filename = podcast.url.split('/')[-1]
        podcast.audio_file = os.path.join(AUDIOS_DIR, podcast.filename)
        response = requests.get(podcast.url, stream=True)
        print(f'Downloading file {podcast.filename}...')
        with open(podcast.audio_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
    return podcasts


def convert_to_video(podcasts):
    for podcast in podcasts:
        basename = podcast.filename.split('.')[0]
        podcast.video_file = os.path.join(VIDEOS_DIR, '%s.mp4' % basename)
        print(f'Converting file {podcast.filename}...')
        if IS_GIF_BACKGROUND:
            subprocess.call([
                'ffmpeg',
                '-stream_loop',
                '-1',
                '-i',
                BACKGROUND_IMAGE,
                '-i',
                podcast.audio_file,
                '-map',
                '0',
                '-map',
                '1:a',
                '-c:v',
                'libx265',
                '-crf',
                '26',
                '-preset',
                'ultrafast',
                '-s',
                '1920x1080',
                '-pix_fmt',
                'yuv420p',
                '-c:a',
                'aac',
                '-movflags',
                '+faststart',
                '-shortest',
                podcast.video_file
            ])
        else:
            subprocess.call([
                'ffmpeg',
                '-r',
                '1',
                '-loop',
                '1',
                '-i',
                BACKGROUND_IMAGE,
                '-i',
                podcast.audio_file,
                '-acodec',
                'copy',
                '-r',
                '1',
                '-shortest',
                '-vf',
                'scale=1920:1080',
                podcast.video_file
            ])
    return podcasts


def upload_to_youtube(podcasts):
    youtube = get_authenticated_service()
    try:
        for podcast in reversed(podcasts):
            initialize_upload(youtube, podcast)
    except HttpError as e:
        print(f'An HTTP error {e.resp.status} occurred:\n{e.content}')


def cleanup(podcasts):
    print('Cleaning up...')
    for podcast in podcasts:
        os.remove(podcast.audio_file)
        os.remove(podcast.video_file)


if __name__ == '__main__':
    if PRIVACY_STATUS not in VALID_PRIVACY_STATUSES:
        exit('Invalid privacy status in configuration file.')

    new_episodes = get_latest_podcasts()
    if new_episodes:
        new_episodes = download_podcasts(new_episodes)
        new_episodes = convert_to_video(new_episodes)
        upload_to_youtube(new_episodes)
        cleanup(new_episodes)
        print('Process completed!')
