from playwright.sync_api import sync_playwright

TEST_URL = "https://fm4.orf.at/sendung/1028051/swound-sound"


def main():

    print("Starting FM4 browser test...")
    print(f"Opening: {TEST_URL}")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1000
            }
        )

        audio_requests = []
        audio_responses = []

        def on_request(request):

            url = request.url

            interesting = (
                "loopstream" in url.lower()
                or ".mp3" in url.lower()
                or "audioapi" in url.lower()
                or "sound.orf.at" in url.lower()
            )

            if interesting:

                if url not in audio_requests:

                    audio_requests.append(url)

                    print(
                        "\nREQUEST:"
                    )
                    print(url)

        def on_response(response):

            try:
                content_type = (
                    response.headers
                    .get("content-type", "")
                    .lower()
                )
            except Exception:
                content_type = ""

            url = response.url

            if (
                "audio" in content_type
                or "mpeg" in content_type
                or "mp3" in content_type
                or "loopstream" in url.lower()
            ):

                if url not in audio_responses:

                    audio_responses.append(url)

                    print(
                        "\nAUDIO RESPONSE:"
                    )
                    print(
                        "Content-Type:",
                        content_type
                    )
                    print(url)

        page.on(
            "request",
            on_request
        )

        page.on(
            "response",
            on_response
        )

        page.goto(
            TEST_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        print(
            "\nPage loaded."
        )

        page.wait_for_timeout(
            5000
        )

        print(
            "\nLooking for audio elements..."
        )

        audio_elements = page.locator(
            "audio"
        )

        count = audio_elements.count()

        print(
            f"Found {count} audio element(s)."
        )

        for i in range(count):

            try:

                element = (
                    audio_elements.nth(i)
                )

                print(
                    "Audio element:",
                    element.get_attribute("src")
                )

            except Exception:
                pass

        print(
            "\nLooking for play buttons..."
        )

        buttons = page.locator(
            "button"
        )

        button_count = buttons.count()

        print(
            f"Found {button_count} button(s)."
        )

        for i in range(
            min(button_count, 50)
        ):

            try:

                button = buttons.nth(i)

                text = (
                    button.inner_text(
                        timeout=1000
                    )
                    .strip()
                )

                aria = (
                    button.get_attribute(
                        "aria-label"
                    )
                    or ""
                )

                title = (
                    button.get_attribute(
                        "title"
                    )
                    or ""
                )

                if (
                    text
                    or aria
                    or title
                ):

                    print(
                        f"BUTTON {i}: "
                        f"text={text!r} "
                        f"aria={aria!r} "
                        f"title={title!r}"
                    )

            except Exception:
                pass

        print(
            "\nTrying to start playback..."
        )

        # Try common FM4/ORF play controls.
        selectors = [
            "button[aria-label*='Anhören']",
            "button[aria-label*='Wiedergabe']",
            "button[aria-label*='Play']",
            "[title*='Anhören']",
            "[title*='Wiedergabe']",
            "text=Anhören",
            "text=Wiedergabe starten",
        ]

        clicked = False

        for selector in selectors:

            try:

                locator = (
                    page.locator(selector)
                    .first
                )

                if locator.count() > 0:

                    print(
                        "Trying:",
                        selector
                    )

                    locator.click(
                        timeout=3000
                    )

                    clicked = True

                    print(
                        "Clicked successfully."
                    )

                    break

            except Exception as e:

                print(
                    "Could not click:",
                    selector,
                    str(e)[:150]
                )

        if not clicked:

            print(
                "\nNo known play button "
                "could be clicked."
            )

        print(
            "\nWaiting for the player..."
        )

        page.wait_for_timeout(
            10000
        )

        print(
            "\nChecking audio elements again..."
        )

        count = audio_elements.count()

        print(
            f"Found {count} audio element(s)."
        )

        for i in range(count):

            try:

                element = (
                    audio_elements.nth(i)
                )

                print(
                    "Audio element:",
                    element.get_attribute("src")
                )

            except Exception:
                pass

        print(
            "\n=========================="
        )

        print(
            "Audio requests found:",
            len(audio_requests)
        )

        print(
            "Audio responses found:",
            len(audio_responses)
        )

        print(
            "=========================="
        )

        browser.close()


if __name__ == "__main__":
    main()
