import json
import urllib.request
import uuid


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

    print("Template:")
    print(template)
    print()

    userid = str(uuid.uuid4())

    audio_url = template

    audio_url = audio_url.replace("{offset}", "offset=0")
    audio_url = audio_url.replace("{offsetende}", f"offsetende={payload['duration']}")
    audio_url = audio_url.replace("{shoutcast}", "shoutcast=0")
    audio_url = audio_url.replace("{player}", "player=web")
    audio_url = audio_url.replace("{referer}", "referer=fm4.orf.at")
    audio_url = audio_url.replace("{userid}", f"userid={userid}")

    print("Constructed audio URL:")
    print(audio_url)
    print()

    if "{" in audio_url or "}" in audio_url:
        print("ERROR: URL still contains placeholders!")
        return

    print("No placeholders remain.")
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
