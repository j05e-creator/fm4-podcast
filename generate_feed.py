import json
import urllib.request
import uuid
from urllib.parse import urlparse


BROADCAST_ID = "1028051"

API_URL = (
    "https://audioapi-v2.orf.at/fm4/api/json/5.0/broadcast/"
    f"{BROADCAST_ID}?items=true&_o=fm4.orf.at"
)


def main():
    print("Testing FM4 direct audio URL")
    print()

    request = urllib.request.Request(
        API_URL,
        headers={"User-Agent": "Mozilla/5.0 FM4-Podcast-Test/1.0"},
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    payload = data["payload"]

    stream = payload["streams"][0]
    template = stream["uriTemplates"]["progressive"]

    print("Broadcast:")
    print(payload["title"])
    print()

    print("Template:")
    print(template)
    print()

    userid = str(uuid.uuid4())

    audio_url = (
        template
        .replace("{offset}", "offset=0")
        .replace("{offsetende}", f"offsetende={payload['duration']}")
        .replace("{shoutcast}", "shoutcast=0")
        .replace("{player}", "player=web")
        .replace("{referer}", "referer=fm4.orf.at")
        .replace("{userid}", f"userid={userid}")
    )

    print("Constructed audio URL:")
    print(audio_url)
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
