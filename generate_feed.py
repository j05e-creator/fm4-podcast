import json
import urllib.request

BROADCAST_ID = "1028051"

URL = (
    "https://audioapi-v2.orf.at/fm4/api/json/5.0/broadcast/"
    f"{BROADCAST_ID}?items=true&_o=fm4.orf.at"
)


def find_urls(obj, path=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from find_urls(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from find_urls(value, f"{path}[{i}]")
    elif isinstance(obj, str):
        if "http://" in obj or "https://" in obj:
            yield path, obj


def main():
    print("Testing FM4 API for audio information")
    print(URL)
    print()

    request = urllib.request.Request(
        URL,
        headers={"User-Agent": "Mozilla/5.0 FM4-Podcast-Test/1.0"},
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    payload = data.get("payload", {})

    print("TITLE:")
    print(payload.get("title"))
    print()

    print("BROADCAST DAY:")
    print(payload.get("broadcastDay"))
    print()

    print("DURATION:")
    print(payload.get("duration"))
    print()

    print("TOP-LEVEL PAYLOAD KEYS:")
    print(", ".join(payload.keys()))
    print()

    print("ALL URLS FOUND IN RESPONSE:")
    print("-" * 80)

    urls = list(find_urls(data))

    for path, url in urls:
        print(path)
        print(url)
        print()

    print(f"Total URLs found: {len(urls)}")


if __name__ == "__main__":
    main()
