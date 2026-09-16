import html
import json
import os
import re
import uuid
import urllib.request
import urllib.error
from datetime import datetime, timezone
from email.utils import format_datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urlencode
import xml.etree.ElementTree as ET


# ------------------------------------------------------------
# FM4 shows
# ------------------------------------------------------------

SHOWS = [
    {
        "name": "Tribe Vibes",
        "slug": "tribe-vibes",
        "url": "https://fm4.orf.at/sendereihe/40/tribe-vibes",
    },
    {
        "name": "Swound Sound",
        "slug": "swound-sound",
        "url": "https://fm4.orf.at/sendereihe/46/swound-sound",
    },
    {
        "name": "Worldwide Show",
        "slug": "worldwide-show",
        "url": "https://fm4.orf.at/sendereihe/19/worldwide-show",
    },
]

API_BASE = "https://audioapi-v2.orf.at/fm4/api/json/5.0/broadcast/"

USER_AGENT = "FM4-Podcast-Feed/1.0"

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM_NS = "http://www.w3.org/2005/Atom"

ET.register_namespace("itunes", ITUNES_NS)
ET.register_namespace("atom", ATOM_NS)


# ------------------------------------------------------------
# HTML parsing
# ------------------------------------------------------------

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return

        attrs = dict(attrs)
        href = attrs.get("href")

        if href:
            self.links.append(href)


# ------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------

def clean_html(value):
    if not value:
        return ""

    value = html.unescape(value)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</p\s*>", "\n\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n\s*\n\s*\n+", "\n\n", value)

    return value.strip()


def http_get(url, headers=None, timeout=30):
    request_headers = {
        "User-Agent": USER_AGENT,
    }

    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(
        url,
        headers=request_headers,
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def get_json(url):
    data = http_get(
        url,
        headers={
            "Accept": "application/json",
        },
    )

    return json.loads(data.decode("utf-8"))


# ------------------------------------------------------------
# Discover latest two broadcasts for a show
# ------------------------------------------------------------

def discover_broadcasts(show):
    print(f"Checking show page: {show['name']}")
    print(show["url"])

    html_data = http_get(show["url"]).decode("utf-8", errors="replace")

    parser = LinkParser()
    parser.feed(html_data)

    pattern = re.compile(
        rf"/sendung/(\d+)/{re.escape(show['slug'])}(?:[/?#]|$)"
    )

    broadcasts = []
    seen = set()

    for href in parser.links:
        absolute = urljoin(show["url"], href)
        parsed = urlparse(absolute)

        match = pattern.search(parsed.path)

        if not match:
            continue

        broadcast_id = match.group(1)

        if broadcast_id in seen:
            continue

        seen.add(broadcast_id)

        broadcasts.append(
            {
                "id": broadcast_id,
                "url": absolute,
            }
        )

        if len(broadcasts) == 2:
            break

    if len(broadcasts) < 2:
        raise RuntimeError(
            f"Could not find two broadcasts for {show['name']}"
        )

    print(
        f"  Latest:  {broadcasts[0]['id']}  {broadcasts[0]['url']}"
    )
    print(
        f"  Previous: {broadcasts[1]['id']}  {broadcasts[1]['url']}"
    )
    print()

    return broadcasts


# ------------------------------------------------------------
# FM4 API
# ------------------------------------------------------------

def get_broadcast(broadcast_id):
    url = (
        API_BASE
        + str(broadcast_id)
        + "?items=true&_o=fm4.orf.at"
    )

    return get_json(url)["payload"]


# ------------------------------------------------------------
# Construct FM4 progressive MP3 URL
# ------------------------------------------------------------

def build_audio_url(payload, broadcast_id):
    stream = payload["streams"][0]

    progressive = stream["urls"]["progressive"]

    parsed = urlparse(progressive)

    query = dict(
        item.split("=", 1)
        for item in parsed.query.split("&")
        if "=" in item
    )

    audio_id = query["id"]

    # Use a deterministic UUID so the enclosure URL does not
    # change every time the feed is regenerated.
    userid = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"fm4-podcast:{broadcast_id}",
        )
    )

    params = {
        "channel": "fm4",
        "id": audio_id,
        "offset": "0",
        "offsetende": str(payload["duration"]),
        "shoutcast": "0",
        "referer": "fm4.orf.at",
        "userid": userid,
    }

    return (
        "https://loopstreamfm4.apa.at/?"
        + urlencode(params)
    )


# ------------------------------------------------------------
# Verify audio without downloading the whole episode
# ------------------------------------------------------------

def verify_audio_url(audio_url):
    print("  Verifying audio stream...")

    # First try HEAD.
    try:
        request = urllib.request.Request(
            audio_url,
            method="HEAD",
            headers={
                "User-Agent": USER_AGENT,
                "Referer": "https://fm4.orf.at/",
            },
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            content_type = (
                response.headers.get("Content-Type") or ""
            ).lower()

            content_length = response.headers.get(
                "Content-Length"
            )

            if content_type.startswith("audio/mpeg"):
                size = int(content_length) if content_length else 0

                print(
                    f"  OK: {response.status} {content_type}"
                )

                return size

    except Exception:
        pass

    # Fallback: request only the first byte.
    request = urllib.request.Request(
        audio_url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://fm4.orf.at/",
            "Range": "bytes=0-1",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        content_type = (
            response.headers.get("Content-Type") or ""
        ).lower()

        if not content_type.startswith("audio/mpeg"):
            raise RuntimeError(
                "FM4 audio verification failed. "
                f"Content-Type was: {content_type}"
            )

        content_range = response.headers.get("Content-Range")
        content_length = response.headers.get("Content-Length")

        size = 0

        if content_range:
            match = re.search(r"/(\d+)$", content_range)

            if match:
                size = int(match.group(1))

        elif content_length:
            size = int(content_length)

        print(
            f"  OK: {response.status} {content_type}"
        )

        return size


# ------------------------------------------------------------
# Artwork
# ------------------------------------------------------------

def get_best_image(payload):
    images = payload.get("images") or []

    if not images:
        return None

    versions = images[0].get("versions") or []

    if not versions:
        return None

    candidates = [
        version
        for version in versions
        if version.get("path")
    ]

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item.get("width", 0),
        reverse=True,
    )

    return candidates[0]["path"]


# ------------------------------------------------------------
# Date
# ------------------------------------------------------------

def get_pub_date(payload):
    broadcast_day = str(payload.get("broadcastDay", ""))

    try:
        date = datetime.strptime(
            broadcast_day,
            "%Y%m%d",
        ).replace(tzinfo=timezone.utc)

        return date

    except ValueError:
        return datetime.now(timezone.utc)


# ------------------------------------------------------------
# Build episode data
# ------------------------------------------------------------

def build_episode(show, broadcast):
    broadcast_id = broadcast["id"]

    print(
        f"Processing {show['name']} / {broadcast_id}"
    )

    payload = get_broadcast(broadcast_id)

    audio_url = build_audio_url(
        payload,
        broadcast_id,
    )

    audio_size = verify_audio_url(audio_url)

    title = payload.get("title") or show["name"]

    subtitle = clean_html(
        payload.get("subtitle") or ""
    )

    description = clean_html(
        payload.get("description") or ""
    )

    # Avoid an unhelpful duplicate title.
    if subtitle and subtitle.lower() not in title.lower():
        episode_title = f"{title} — {subtitle}"
    else:
        episode_title = title

    # Add the date so the mixed feed is easy to scan.
    pub_date = get_pub_date(payload)

    episode_title = (
        f"{episode_title} "
        f"({pub_date.strftime('%d %b %Y')})"
    )

    image_url = get_best_image(payload)

    return {
        "show": show["name"],
        "show_slug": show["slug"],
        "id": broadcast_id,
        "title": episode_title,
        "description": description,
        "audio_url": audio_url,
        "audio_size": audio_size,
        "duration_ms": int(payload.get("duration") or 0),
        "pub_date": pub_date,
        "episode_url": broadcast["url"],
        "image_url": image_url,
    }


# ------------------------------------------------------------
# GitHub Pages URL
# ------------------------------------------------------------

def get_site_url():
    explicit = os.environ.get("SITE_URL")

    if explicit:
        return explicit.rstrip("/")

    repository = os.environ.get("GITHUB_REPOSITORY")

    if repository and "/" in repository:
        owner, repo = repository.split("/", 1)

        return (
            f"https://{owner}.github.io/{repo}"
        )

    raise RuntimeError(
        "Could not determine GitHub Pages URL. "
        "Set SITE_URL as an environment variable."
    )


# ------------------------------------------------------------
# Generate RSS
# ------------------------------------------------------------

def generate_feed(episodes, site_url):
    feed_url = f"{site_url}/feed.xml"

    rss = ET.Element(
        "rss",
        {
            "version": "2.0",
            f"{{{ITUNES_NS}}}version": "1.0",
        },
    )

    channel = ET.SubElement(rss, "channel")

    ET.SubElement(
        channel,
        "title",
    ).text = "FM4 — Tribe Vibes, Swound Sound & Worldwide Show"

    ET.SubElement(
        channel,
        "link",
    ).text = site_url

    ET.SubElement(
        channel,
        "description",
    ).text = (
        "The latest two episodes of FM4's "
        "Tribe Vibes, Swound Sound and Worldwide Show."
    )

    ET.SubElement(
        channel,
        "language",
    ).text = "en"

    ET.SubElement(
        channel,
        "lastBuildDate",
    ).text = format_datetime(
        datetime.now(timezone.utc),
        usegmt=True,
    )

    ET.SubElement(
        channel,
        "generator",
    ).text = "FM4 Podcast Feed Generator"

    ET.SubElement(
        channel,
        f"{{{ITUNES_NS}}}author",
    ).text = "Radio FM4"

    ET.SubElement(
        channel,
        f"{{{ITUNES_NS}}}summary",
    ).text = (
        "Latest episodes from FM4's "
        "Tribe Vibes, Swound Sound and Worldwide Show."
    )

    ET.SubElement(
        channel,
        f"{{{ITUNES_NS}}}explicit",
    ).text = "no"

    ET.SubElement(
        channel,
        f"{{{ITUNES_NS}}}type",
    ).text = "episodic"

    ET.SubElement(
        channel,
        f"{{{ITUNES_NS}}}category",
        {"text": "Music"},
    )

    # Use the first available show artwork as the feed artwork.
    artwork = next(
        (
            episode["image_url"]
            for episode in episodes
            if episode["image_url"]
        ),
        None,
    )

    if artwork:
        ET.SubElement(
            channel,
            f"{{{ITUNES_NS}}}image",
            {"href": artwork},
        )

    ET.SubElement(
        channel,
        f"{{{ATOM_NS}}}link",
        {
            "href": feed_url,
            "rel": "self",
            "type": "application/rss+xml",
        },
    )

    for episode in episodes:
        item = ET.SubElement(channel, "item")

        ET.SubElement(
            item,
            "title",
        ).text = episode["title"]

        ET.SubElement(
            item,
            "link",
        ).text = episode["episode_url"]

        ET.SubElement(
            item,
            "guid",
            {
                "isPermaLink": "false",
            },
        ).text = (
            f"fm4:{episode['show_slug']}:{episode['id']}"
        )

        description = episode["description"]

        if not description:
            description = (
                f"{episode['show']} — FM4"
            )

        ET.SubElement(
            item,
            "description",
        ).text = description

        ET.SubElement(
            item,
            "pubDate",
        ).text = format_datetime(
            episode["pub_date"],
            usegmt=True,
        )

        ET.SubElement(
            item,
            f"{{{ITUNES_NS}}}author",
        ).text = "Radio FM4"

        ET.SubElement(
            item,
            f"{{{ITUNES_NS}}}summary",
        ).text = description

        ET.SubElement(
            item,
            f"{{{ITUNES_NS}}}episodeType",
        ).text = "full"

        if episode["duration_ms"]:
            seconds = episode["duration_ms"] // 1000

            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60

            duration = (
                f"{hours:02d}:{minutes:02d}:{secs:02d}"
            )

            ET.SubElement(
                item,
                f"{{{ITUNES_NS}}}duration",
            ).text = duration

        if episode["image_url"]:
            ET.SubElement(
                item,
                f"{{{ITUNES_NS}}}image",
                {
                    "href": episode["image_url"]
                },
            )

        ET.SubElement(
            item,
            "enclosure",
            {
                "url": episode["audio_url"],
                "length": str(episode["audio_size"]),
                "type": "audio/mpeg",
            },
        )

    tree = ET.ElementTree(rss)

    ET.indent(tree, space="  ")

    tree.write(
        "feed.xml",
        encoding="utf-8",
        xml_declaration=True,
    )

    print()
    print(f"Feed written to: feed.xml")
    print(f"Feed URL: {feed_url}")


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    print("=" * 70)
    print("FM4 PODCAST FEED GENERATOR")
    print("=" * 70)
    print()

    all_episodes = []

    for show in SHOWS:
        broadcasts = discover_broadcasts(show)

        for broadcast in broadcasts:
            episode = build_episode(
                show,
                broadcast,
            )

            all_episodes.append(episode)

    # Newest first.
    all_episodes.sort(
        key=lambda episode: episode["pub_date"],
        reverse=True,
    )

    print()
    print("=" * 70)
    print("EPISODES IN FEED")
    print("=" * 70)

    for episode in all_episodes:
        print(
            f"{episode['show']}: "
            f"{episode['id']} — "
            f"{episode['title']}"
        )

    if len(all_episodes) != 6:
        raise RuntimeError(
            f"Expected 6 episodes, got {len(all_episodes)}"
        )

    site_url = get_site_url()

    print()
    print(f"GitHub Pages site: {site_url}")
    print()

    generate_feed(
        all_episodes,
        site_url,
    )


if __name__ == "__main__":
    main()
