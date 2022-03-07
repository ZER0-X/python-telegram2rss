"""Telegram channel class."""
from typing import Optional
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
from requests import session as requests_session, sessions as requests_sessions

from .telegram_types import (
    TEXT,
    PHOTO,
    VIDEO,
    VOICE,
    DOCUMENT,
    LOCATION,
    POLL,
    # STICKER,
    UNSUPPORTED_MEDIA,
    CHANNEL_TITLE,
    CHANNEL_DESCRIPTION,
    CHANNEL_IMAGE,
    MESSAGE_AUTHOR,
    MESSAGE_DATE,
    MESSAGE_VIEWS,
    MESSAGE_VOTERS,
    MESSAGE_NUMBER,
    VIDEO_DURATION,
    VIDEO_THUMB,
    VOICE_URL,
    VOICE_DURATION,
    DOCUMENT_TITLE,
    DOCUMENT_SIZE,
    POLL_QUESTION,
    POLL_TYPE,
    POLL_OPTIONS,
    POLL_OPTION_PERCENT,
    POLL_OPTION_VALUE,
    UNSUPPORTED_MEDIA_URL,
)


TELEGRAM_URL = "https://t.me"


class FeedEnd(Exception):
    """Error to be raised after pulling all the messages from the channel."""


class TGChannel:
    """
    Telegram channel class.

    ...

    Attributes
    ----------
    channel_id : str
        The Telegram channel id.
    session_object : requests.sessions.Session
        Session object from the requests library for the ability of using proxy for example.

    Methods
    -------
    fetch_to_python()
        Fetch data from telegram to python list.
    """

    def __init__(
        self, channel_id: str, session_object: requests_sessions.Session = None
    ):
        """
        Init method for the Telegram channel class.

        Parameters
        ----------
        channel_id : str
            The Telegram channel id.
        """
        self.channel_id = channel_id
        # Where we stopped at the last fetch process.
        self.position: Optional[str] = None

        if not session_object:
            self.session_object = requests_session()
        else:
            self.session_object = session_object

    def fetch_to_python(self, pages_to_fetch=1) -> list:
        """
        Get html code using requests then get the data from it.

        Parameters
        ----------
        pages_to_fetch : str
            The number of pages to fetch from the telegram channel.
        """
        if self.position == "0":
            raise FeedEnd("All the pages were already fetched from the channel.")

        url = f"{TELEGRAM_URL}/s/{self.channel_id}"

        all_bubbles = []

        for _ in range(pages_to_fetch):
            params = {"before": self.position}
            source = self.session_object.get(url, params=params).text
            soup = BeautifulSoup(source, "lxml")

            try:
                self.position = soup.select_one(".tme_messages_more")["data-before"]
            except TypeError:
                self.position = "0"
            except KeyError:
                self.position = "0"
                break
            bubbles = soup.select(".tgme_widget_message_bubble")
            bubbles.reverse()
            all_bubbles += bubbles

        all_messages: list = []

        for bubble in all_bubbles:
            message = {}

            # Get message meta data.
            number = bubble.select_one(MESSAGE_NUMBER.selector)["href"].split("/")[4]
            author = bubble.select_one(MESSAGE_AUTHOR.selector).text
            date = bubble.select_one(MESSAGE_DATE.selector)["datetime"]
            try:
                views = bubble.select_one(MESSAGE_VIEWS.selector).text
            except AttributeError:
                views = None
            try:
                votes = bubble.select_one(MESSAGE_VOTERS.selector).text
            except AttributeError:
                votes = None
            # TODO Detect if message is forwarded or some thing like that.
            message.update(
                {
                    MESSAGE_NUMBER.name: number,
                    MESSAGE_AUTHOR.name: author,
                    MESSAGE_DATE.name: date,
                    MESSAGE_VIEWS.name: views,
                    MESSAGE_VOTERS.name: votes,
                }
            )

            contents = []

            # Get text.
            texts = bubble.select(TEXT.selector)
            for text in texts:
                contents.append({"type": TEXT.name, "content": text.text})

            # Get photos urls.
            photos = bubble.select(PHOTO.selector)
            for photo in photos:
                # TODO proxy photons and sava them as base64.
                photo = photo["style"].split("'")[1]
                contents.append({"type": PHOTO.name, "url": photo})

            # Get videos urls, thumbnails and durations.
            videos = bubble.select(VIDEO.selector)
            for video in videos:
                video_url = video["href"]
                # TODO proxy video thumbnail and sava it as base64.
                video_thumb_url = video.select_one(VIDEO_THUMB.selector)["style"].split(
                    "'"
                )[1]
                video_duration = video.select_one(VIDEO_DURATION.selector).text
                contents.append(
                    {
                        "type": VIDEO.name,
                        "url": video_url,
                        "thumbnail": video_thumb_url,
                        "duration": video_duration,
                    }
                )

            # Get voices urls and durations.
            voices = bubble.select(VOICE.selector)
            for voice in voices:
                voice_url = voice.select(VOICE_URL.selector)["src"]
                voice_duration = voice.select(VOICE_DURATION.selector).text

                contents.append(
                    {"type": VOICE.name, "url": voice_url, "duration": voice_duration}
                )

            # Get documents urls and sizes.
            documents = bubble.select(DOCUMENT.selector)
            for document in documents:
                document_url = document["href"]
                document_title = document.select(DOCUMENT_TITLE.selector)
                document_size = document.select(DOCUMENT_SIZE.selector)
                contents.append(
                    {
                        "type": DOCUMENT.name,
                        "url": document_url,
                        "title": document_title,
                        "size": document_size,
                    }
                )

            # Get locations.
            locations = bubble.select(LOCATION.selector)
            for location in locations:
                url = location["href"]
                # Convert URL from google maps to openstreet map and get longuitude and latitude.
                query = parse_qs(urlparse(url).query)
                q = query["q"][0]
                zoom = query["z"][0]
                latitude, longitude = tuple(q.split(","))
                url = (
                    "https://www.openstreetmap.org/"
                    + f"?lat={latitude}&lon={longitude}&zoom={zoom}&layers=M"
                )
                contents.append(
                    {
                        "type": LOCATION.name,
                        "url": url,
                        "latitude": latitude,
                        "longitude": longitude,
                    }
                )

            # Get polls.
            polls = bubble.select(POLL.selector)
            for poll in polls:
                poll_question = poll.select_one(POLL_QUESTION.selector).text
                poll_type = poll.select_one(POLL_TYPE.selector).text

                poll_options = []

                options = poll.select(POLL_OPTIONS.selector)
                for option in options:
                    option_percent = option.select_one(POLL_OPTION_PERCENT.selector).text
                    option_value = option.select_one(POLL_OPTION_VALUE.selector).text
                    poll_options.append(
                        {"percent": option_percent, "value": option_value}
                    )

                contents.append(
                    {
                        "type": POLL.name,
                        "poll_question": poll_question,
                        "poll_type": poll_type,
                        "poll_options": poll_options,
                    }
                )

            # Get stickers
            # stickers = bubble.select(STICKER.selector)
            # for sticker in stickers:
            #     # Can't be implemented since we cant access them via the web interface.
            #     pass

            unsupported_medias = bubble.select(UNSUPPORTED_MEDIA.selector)
            for media in unsupported_medias:
                try:
                    url = media.select_one(UNSUPPORTED_MEDIA_URL.selector)["href"]
                except KeyError:
                    continue
                contents.append(
                    {
                        "type": UNSUPPORTED_MEDIA.name,
                        "url": url,
                    }
                )

            message.update({"contents": contents})
            all_messages.append(message)
        return all_messages

    def fetch_to_rss(self):
        pass