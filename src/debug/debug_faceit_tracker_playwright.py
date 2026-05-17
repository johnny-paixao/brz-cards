import re
import asyncio
from playwright.async_api import async_playwright


async def main():
    nickname = "mHc"
    url = f"https://faceittracker.net/players/{nickname}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        print("Abrindo:", url)

        await page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # espera a renderização do frontend
        await page.wait_for_timeout(8000)

        text = await page.locator("body").inner_text(timeout=10000)

        print("=" * 80)
        print(text[:5000])
        print("=" * 80)

        match = re.search(
            r"Highest\s+ELO:\s*([0-9]{3,5})",
            text,
            flags=re.IGNORECASE,
        )

        if match:
            print("Highest ELO encontrado:", match.group(1))
        else:
            print("Highest ELO não encontrado")

        await browser.close()


asyncio.run(main())