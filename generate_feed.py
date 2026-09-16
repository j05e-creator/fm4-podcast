import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from email.utils import format_datetime

from playwright.sync_api import sync_playwright


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

SHOWS = [
    {
        "name": "Tribe Vibes",
        "url": "https://fm4.orf.at/sendereihe/40/tribe-vibes",
        "description": "Tribe Vibes on FM4.",
    },
    {
        "name": "Swound Sound",
        "url": "https://fm4.orf.at/sendereihe/46/swound-sound",
        "description": "Swound Sound on FM4.",
    },
    {
        "name": "Worldwide Show",
        "url": "https://fm4.orf.at/sendereihe/19/worldwide-show",
        "description": "Worldwide Show on FM4.",
    },
]

OUTPUT_FILE = "feed.xml"


# ------------------------------------------------------------
# Download a webpage
# ------------------------------------------------------------

def fetch(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Mozilla/5.0 FM4-Podcast-Feed/1.0"
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        return response.read().decode(
            "utf-8",
            errors="replace"
        )


# ------------------------------------------------------------
# Find episode pages
# ------------------------------------------------------------

def find_episode_urls(series_url):

    page = fetch(series_url)

    pattern = re.compile(
        r'href=["\'](/sendung/(\d+)/[^"\']+)["\']',
        re.IGNORECASE,
    )

    results = []

    seen = set()

    for path, episode_id in pattern.findall(page):

        full_url = urllib.parse.urljoin(
            "https://fm4.orf.at",
            path
        )

        if full_url not in seen:

            seen.add(full_url)

            results.append(
                (
                    full_url,
                    episode_id
                )
            )

    return results


# ------------------------------------------------------------
# Extract the audio URL from an FM4 episode page
#
# We use Playwright because the current ORF Sound player
# is JavaScript based.
# ------------------------------------------------------------

def get_audio_from_page(page_url):

    audio_urls = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        def request_handler(request):

            url = request.url

            if (
                "loopstream" in url.lower()
                or ".mp3" in url.lower()
                or "audioapi.orf.at" in url.lower()
            ):

                if url not in audio_urls:

                    print(
                        "    Audio request:",
                        url[:250]
                    )

                    audio_urls.append(url)

        page.on(
            "request",
            request_handler
        )

        print(
            f"    Opening {page_url}"
        )

        page.goto(
            page_url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        # Give the player time to initialise.
        page.wait_for_timeout(5000)

        # Try the visible "Anhören" / play control.
        selectors = [
            "text=Anhören",
            "text=Wiedergabe starten",
            "[aria-label*='Wiedergabe']",
            "[aria-label*='Play']",
            "button",
        ]

        for selector in selectors:

            try:

                locator = page.locator(
                    selector
                ).first

                if locator.count() > 0:

                    locator.click(
                        timeout=3000
                    )

                    print(
                        "    Clicked:",
                        selector
                    )

                    page.wait_for_timeout(
                        5000
                    )

                    break

            except Exception:
                pass

        browser.close()

    if not audio_urls:

        raise RuntimeError(
            "Could not find an ORF audio stream."
        )

    # Prefer an actual MP3/loopstream URL.
    for url in audio_urls:

        if (
            "loopstream" in url.lower()
            or ".mp3" in url.lower()
        ):

            return url

    return audio_urls[0]


# ------------------------------------------------------------
# Extract basic information from the FM4 page
# ------------------------------------------------------------

def extract_page_info(page_url):

    page = fetch(page_url)

    # Title
    title_match = re.search(
        r"<h1[^>]*>(.*?)</h1>",
        page,
        re.IGNORECASE | re.DOTALL,
    )

    if title_match:

        title = re.sub(
            r"<[^>]+>",
            "",
            title_match.group(1)
        ).strip()

    else:

        title = "FM4 Episode"

    # Remove HTML entities.
    title = html.unescape(title)

    return {
        "title": title,
        "description": "",
        "date": None,
    }


# ------------------------------------------------------------
# Get latest episodes for one show
# ------------------------------------------------------------

def get_show_episodes(show):

    print(
        f"\nChecking {show['name']}..."
    )

    episode_urls = find_episode_urls(
        show["url"]
    )

    if not episode_urls:

        raise RuntimeError(
            f"No episodes found for {show['name']}"
        )

    # We only need the two newest.
    episode_urls = episode_urls[:2]

    episodes = []

    for page_url, episode_id in episode_urls:

        print(
            f"  Episode {episode_id}"
        )

        try:

            info = extract_page_info(
                page_url
            )

            audio_url = get_audio_from_page(
                page_url
            )

            episodes.append(
                {
                    "show": show["name"],
                    "title": (
                        f"{show['name']} — "
                        f"{info['title']}"
                    ),
                    "description":
                        show["description"],
                    "url": audio_url,
                    "page": page_url,
                    "guid":
                        f"fm4-{episode_id}",
                    "date":
                        info["date"],
                }
            )

        except Exception as e:

            print(
                f"    ERROR: {e}"
            )

    return episodes


# ------------------------------------------------------------
# Generate RSS feed
# ------------------------------------------------------------

def make_feed(episodes):

    rss = ET.Element(
        "rss",
        {
            "version": "2.0",
            "xmlns:itunes":
                "http://www.itunes.com/dtds/podcast-1.0.dtd",
        },
    )

    channel = ET.SubElement(
        rss,
        "channel"
    )

    def add(tag, text):

        element = ET.SubElement(
            channel,
            tag
        )

        element.text = str(
            text or ""
        )

        return element

    add(
        "title",
        "FM4 — My Shows"
    )

    add(
        "link",
        "https://fm4.orf.at/"
    )

    add(
        "description",
        "Latest episodes of Tribe Vibes, "
        "Swound Sound and Worldwide Show."
    )

    add(
        "language",
        "en-at"
    )

    add(
        "lastBuildDate",
        format_datetime(
            datetime.now(
                timezone.utc
            )
        )
    )

    add(
        "itunes:author",
        "FM4"
    )

    add(
        "itunes:summary",
        "Latest FM4 shows."
    )

    add(
        "itunes:explicit",
        "no"
    )

    for episode in episodes:

        item = ET.SubElement(
            channel,
            "item"
        )

        def item_add(tag, text):

            element = ET.SubElement(
                item,
                tag
            )

            element.text = str(
                text or ""
            )

            return element

        item_add(
            "title",
            episode["title"]
        )

        item_add(
            "description",
            episode["description"]
        )

        item_add(
            "guid",
            episode["guid"]
        )

        item_add(
            "link",
            episode["page"]
        )

        ET.SubElement(
            item,
            "enclosure",
            {
                "url": episode["url"],
                "type": "audio/mpeg",
                "length": "0",
            },
        )

        item_add(
            "itunes:author",
            "FM4"
        )

    ET.indent(
        rss,
        space="  "
    )

    tree = ET.ElementTree(
        rss
    )

    tree.write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True,
    )


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():

    episodes = []

    for show in SHOWS:

        try:

            episodes.extend(
                get_show_episodes(
                    show
                )
            )

        except Exception as e:

            print(
                f"ERROR processing "
                f"{show['name']}: {e}"
            )

    if not episodes:

        raise RuntimeError(
            "No FM4 episodes were found."
        )

    make_feed(
        episodes
    )

    print(
        f"\nCreated {OUTPUT_FILE} "
        f"with {len(episodes)} episodes."
    )


if __name__ == "__main__":

    main()    if not seconds:
        return None

    seconds = int(float(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"

    return f"{minutes}:{secs:02d}"


# ------------------------------------------------------------
# Find the latest FM4 programme pages
# ------------------------------------------------------------

def find_episode_urls(series_url):
    page = fetch(series_url)

    # FM4 programme pages contain links such as:
    # /sendung/123456/tribe-vibes
    pattern = re.compile(
        r'href=["\'](/sendung/(\d+)/[^"\']+)["\']',
        re.IGNORECASE,
    )

    results = []

    for path, episode_id in pattern.findall(page):
        full_url = urllib.parse.urljoin(BASE_URL, path)

        if full_url not in [x[0] for x in results]:
            results.append((full_url, episode_id))

    return results


# ------------------------------------------------------------
# Get the actual audio information from ORF Sound
#
# This uses ORF's current API:
#
# https://audioapi.orf.at/fm4/api/json/5.0/broadcast/ID
#     ?items=true&_o=sound.orf.at
#
# ------------------------------------------------------------

def get_broadcast(broadcast_id):

    url = (
        "https://audioapi.orf.at/fm4/api/json/5.0/broadcast/"
        f"{broadcast_id}?_o=sound.orf.at"
    )

    raw = fetch(url)
    data = __import__("json").loads(raw)

    # ORF returns the broadcast data in "payload".
    return data.get("payload", data)


def extract_audio_items(payload):

    items = []

    # ORF has used several names for the audio list over time.
    streams = (
        payload.get("streams")
        or payload.get("items")
        or payload.get("content")
        or []
    )

    if isinstance(streams, dict):
        streams = streams.get("items") or streams.get("streams") or []

    for stream in streams:

        if not isinstance(stream, dict):
            continue

        audio_url = (
            stream.get("url")
            or stream.get("streamUrl")
            or stream.get("audioUrl")
        )

        loop_id = stream.get("loopStreamId")

        if not audio_url and loop_id:
    audio_url = (
        "https://loopstream01.apa.at/"
        "?channel=fm4&id="
        + urllib.parse.quote(str(loop_id), safe="")
    )

        if not audio_url:
            continue

        start = stream.get("start")
        end = stream.get("end")

        duration = None

        try:
            if start is not None and end is not None:
                # ORF uses milliseconds for these values.
                duration = (float(end) - float(start)) / 1000
        except Exception:
            pass

        items.append(
            {
                "url": audio_url,
                "duration": duration,
                "start": start,
                "end": end,
                "id": loop_id or audio_url,
            }
        )

    return items


# ------------------------------------------------------------
# Process one FM4 show
# ------------------------------------------------------------

def get_show_episodes(show):

    print(f"\nChecking {show['name']}...")

    episode_urls = find_episode_urls(show["url"])

    if not episode_urls:
        raise RuntimeError(
            f"No episode URLs found for {show['name']}"
        )

    episodes = []

    # We only need the newest two programme pages.
    for episode_url, broadcast_id in episode_urls[:2]:

        print(f"  Broadcast {broadcast_id}")

        try:
            payload = get_broadcast(broadcast_id)
        except Exception as e:
            print(f"    API error: {e}")
            continue

        title = payload.get("title") or show["name"]
        subtitle = payload.get("subtitle") or show["description"]

        # Possible date fields used by ORF.
        date_value = (
            payload.get("start")
            or payload.get("startISO")
            or payload.get("date")
            or payload.get("broadcastDate")
        )

        broadcast_date = iso_to_datetime(date_value)

        audio_items = extract_audio_items(payload)

        if not audio_items:
            print("    No audio items found.")
            continue

        for index, audio in enumerate(audio_items, start=1):

            part_title = title

            # Worldwide Show is commonly split into two parts.
            if len(audio_items) > 1:
                part_title = f"{title} — Part {index}"

            episodes.append(
                {
                    "show": show["name"],
                    "title": part_title,
                    "description": subtitle,
                    "url": audio["url"],
                    "duration": audio["duration"],
                    "date": broadcast_date,
                    "page": episode_url,
                    "guid": (
                        f"fm4-{broadcast_id}-"
                        f"{audio['id']}"
                    ),
                }
            )

    return episodes


# ------------------------------------------------------------
# Build RSS feed
# ------------------------------------------------------------

def make_feed(all_episodes):

    # Newest first.
    all_episodes.sort(
        key=lambda x: x["date"] or datetime.min.replace(
            tzinfo=timezone.utc
        ),
        reverse=True,
    )

    rss = ET.Element(
        "rss",
        {
            "version": "2.0",
            "xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
        },
    )

    channel = ET.SubElement(rss, "channel")

    def add(tag, text):
        element = ET.SubElement(channel, tag)
        element.text = text
        return element

    add("title", FEED_TITLE)
    add(
        "link",
        "https://fm4.orf.at/",
    )
    add("description", FEED_DESCRIPTION)
    add("language", "en-at")
    add(
        "copyright",
        "Audio hosted by ORF / FM4. This feed provides links to ORF audio.",
    )

    add("lastBuildDate", format_datetime(datetime.now(timezone.utc)))

    # Podcast/iTunes metadata
    add("itunes:author", "FM4")
    add("itunes:summary", FEED_DESCRIPTION)
    add("itunes:explicit", "no")

    for episode in all_episodes:

        item = ET.SubElement(channel, "item")

        def item_add(tag, text):
            element = ET.SubElement(item, tag)
            element.text = str(text or "")
            return element

        item_add("title", episode["title"])

        description = (
            f"{episode['show']}\n\n"
            f"{episode['description']}\n\n"
            f"Original FM4 page: {episode['page']}"
        )

        item_add("description", description)
        item_add("guid", episode["guid"])
        item_add("link", episode["page"])

        if episode["date"]:
            item_add(
                "pubDate",
                format_datetime(episode["date"]),
            )

        # Audio enclosure.
        enclosure = ET.SubElement(
            item,
            "enclosure",
            {
                "url": episode["url"],
                "type": "audio/mpeg",
                "length": "0",
            },
        )

        # Podcast/iTunes fields.
        item_add("itunes:author", "FM4")
        item_add("itunes:summary", description)

        duration = format_duration(episode["duration"])

        if duration:
            item_add("itunes:duration", duration)

    tree = ET.ElementTree(rss)

    ET.indent(tree, space="  ")

    tree.write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True,
    )


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():

    all_episodes = []

    for show in SHOWS:

        episodes = get_show_episodes(show)

        # Keep the two latest programme broadcasts.
        # Worldwide Show may generate two parts per broadcast.
        all_episodes.extend(episodes)

    if not all_episodes:
        raise RuntimeError(
            "No FM4 episodes were found."
        )

    make_feed(all_episodes)

    print(
        f"\nCreated {OUTPUT_FILE} "
        f"with {len(all_episodes)} audio items."
    )


if __name__ == "__main__":
    main()
