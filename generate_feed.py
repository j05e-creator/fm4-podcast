import json
import urllib.request

BROADCAST_ID = "1028051"

URL = (
    "https://audioapi-v2.orf.at/fm4/api/json/5.0/broadcast/"
    f"{BROADCAST_ID}?items=true&_o=fm4.orf.at"
)


def main():

    print("Testing current FM4 API")
    print(URL)
    print()

    request = urllib.request.Request(
        URL,
        headers={
            "User-Agent":
                "Mozilla/5.0 FM4-Podcast-Test/1.0"
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        data = json.loads(
            response.read().decode(
                "utf-8"
            )
        )

    print(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
