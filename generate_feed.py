import json
import urllib.request
import uuid
from urllib.parse import urlencode


BROADCAST_ID = "1028051"

API_URL = (
    "https://audioapi-v2.orf.at/fm4/api/json/5.0/broadcast/"
    f"{BROADCAST_ID}?items=true&_o=fm4.orf.at"
)


def main():
    print("Testing FM4 direct audio URL")
    print()

    # Get broadcast information
    request = urllib.request.Request(
        API_URL,
        headers={
            "User-Agent": "Mozilla/5.0 FM4-Podcast-Test/1.0"
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    payload = data["payload"]
    stream = payload["streams"][0]

    # Get the actual MP3 ID from the API
    progressive_url = stream["urls"]["progressive"]

    print("FM4 progressive URL:")
    print(progressive_url)
    print()

    # Extract the audio ID from the URL
    audio_id = progressive_url.split("id=")[1].split("&")[0]

    print("Audio ID:")
    print(audio_id)
    print()

    # Build the URL ourselves
    params = {
        "channel": "fm4",
        "id": audio_id,
        "offset": "0",
        "offsetende": str(payload["duration"]),
        "shoutcast": "0",
        "referer": "fm4.orf.at",
        "userid": str(uuid.uuid4()),
    }

    audio_url = (
        "https://loopstreamfm4.apa.at/?"
        + urlencode(params)
    )

    print("Constructed audio URL:")
    print(audio_url)
    print()

    print("Checking URL...")
    print()

    audio_request = urllib.request.Request(
        audio_url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://fm4.orf.at/",
        },
    )

    with urllib.request.urlopen(audio_request, timeout=30) as response:
        print("HTTP STATUS:")
        print(response.status)
        print()

        print("CONTENT TYPE:")
        print(response.headers.get("Content-Type"))
        print()

        print("CONTENT LENGTH:")
        print(response.headers.get("Content-Length"))
        print()

        print("FINAL URL:")
        print(response.geturl())


if __name__ == "__main__":
    main()
