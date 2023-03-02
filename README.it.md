<img src="https://progressify.dev/img/progressify-logo.png" alt="logo" height="120" align="right" />
# Podcast to YouTube Auto Uploader
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/progressify/pc2yt/graphs/commit-activity)
[![Paypal Donate](https://img.shields.io/badge/PayPal-Donate%20to%20Author-blue.svg)](https://www.paypal.me/progressify) 
[![Satispay Donate](https://img.shields.io/badge/Satispay-Donate%20to%20Author-red.svg)](https://tag.satispay.com/progressify) 
[![Ask Me Anything !](https://img.shields.io/badge/Ask%20me-anything-1abc9c.svg)](https://github.com/progressify/pc2yt/issues)

[Here you find the english version of this README](README.md)

A small hack to automatically upload Podcast audios to YouTube. The code is not pretty (and the required setup neither).

Read the instructions bellow carefully (and also check the source code, it's just a few functions).

It probably won't work out-of-the-box -- sorry about that. 


## What it Does?

* Watches a Podcast feed for new episodes;
* Convert the episode to a video format using a static background image;
* Push the video to a YouTube channel.


## How it Works?

* The script is deployed to a cloud server;
* A crontab executes the script periodically;
* First parse the podcast xml from the web, check if there is a new episode;
* If there's a new episode, download it first to the server;
* Grab a predefined image, generate a `.flv` video file using this static image as background;
* When the video file is done, push it to a YouTube channel.


## Why?

If you already have a Podcast setup and wants to make your episodes available on YouTube this script will automate that task. 
The file conversion is necessary because YouTube doesn't let you upload audio files to their platform.


## Installation

The script might need some tweaks to make it work on your environment. In my case it's running on a Ubuntu VPS.

```
git clone https://github.com/progressify/pc2yt
```

After that, install the requirements (ideally inside a virtualenv):

```
pip install -r requirements.txt
```

Now install ffmpeg:

```
apt-get install ffmpeg
```


### Setup

Copy an image file in the same directory as the `pc2yt.py`. 
This file will be used to generate the background of the podcast video.

You can use a static png file or an animated gif file.

To send a file from your local machine to a server:

```
scp background.png root@server_ip_address:/path/to/pc2yt_directory/
```

Always the same directory as the `pc2yt.py` create a `.env` file:

```
cp .env-example .env
```

and replace the values:

- FEED_URL: your podcast rss feed url
- PRIVACY_STATUS: can assume only this 3 values ('public', 'private', 'unlisted')
- SOURCE_BACKGROUND_IMAGE: the name of your background image


### YouTube API Credentials

Now go to the [Google Cloud Platform Console](https://console.cloud.google.com), optionally create a new project or use an existing one.

Visit the **APIs & Services** page, then **Credentials** and create a new **OAuth client ID**. You may need to fill out the details of the **OAuth consent screen** before generating the credentials.

After you create your new OAuth credentials, click on the **Download JSON** button. 

You will download a file named `client_secret_9999999999-xxxxxxxxxx.apps.googleusercontent.com.json`.

Rename it to just `client_secret.json` instead.

Now save this file to the save directory as the `pc2yt.py` script. If it's on a cloud server, you can send it using `scp`:

```
scp client_secret.json root@server_ip_address:/path/to/pc2yt_directory/
```


## Usage

There's another configuration file, which is a file named `.last`. This file stores the reference to the last podcast converted and uploaded. The reference I use here is the **id** of the podcast entry. In case of podcast using Wordpress/Blubbry setup, an example of this file contents is:

**.last**

```
https://example.com/?p=596
```

To understand what you should put there you should first inspect your feed xml and check what is used as **id**. You can do that using a Python shell:

```
import feedparser

d = feedparser.parse('https://example.com/feed.xml')
d['entries'][0]['id']
```

This file is not mandatory. If you start the script without a `.last` file, it will download, convert and upload **ALL** podcasts in your feed.

So you can either use `.last` file to set a reference point, from what point it will start converting and uploading, or let the script figure it out.


### First Usage

This is important, because of the OAuth, the first time you use it is a little bit different. You also need to tell to *what YouTube channel* should the script upload the files.

First time you are using it, run the command below:

```
python pc2yt.py --noauth_local_webserver
```

When the code reachs the `get_authenticated_service()` function, you will get a notification on the console. It will give you a long URL. Access this URL on a web browser, select which Google account you want to use and what YouTube channel you want to upload the files to. Finally, get the verification code, go back to the console and paste the verification code.

After that you will see the script will create a file named `youtube.dat`. It will now take care of refreshing the token by itself.


## Crontab

This should be the last thing in the configuration. Depends on how frequently you post new episodes, you might want to tune this setting:

```
sudo crontab -e
```

An example where the script would be execute every hour, at 12:05, 13:05, 14:05, etc:

```
# m h  dom mon dow   command
5 * * * * /home/pc2yt/venv/bin/python /home/pc2yt/pc2yt.py
```
