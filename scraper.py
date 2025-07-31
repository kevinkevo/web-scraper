from playwright.sync_api import sync_playwright, TimeoutError
from utils import parse_price
import logging

logger = logging.getLogger(__name__)

def scrape_casayes(filters=None):
    logger.info(f"Scraping CasaYes with filters: {filters}")
    listings = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for attempt in range(3):
            try:
                page.goto("https://casayes.pt/pt/comprar/casaseapartamentos", timeout=30000)
                page.wait_for_selector("div[data-id='listing-card-container']", timeout=30000)

                # Scroll to load more listings
                for _ in range(5):
                    page.mouse.wheel(0, 1500)
                    page.wait_for_timeout(1000)

                cards = page.locator("div[data-id='listing-card-container']")
                count = cards.count()
                logger.info(f"Cards found: {count}")

                for i in range(count):
                    card = cards.nth(i)
                    try:
                        card.locator("h2.text-base.font-extrabold").wait_for(timeout=5000)

                        title = card.locator("h2.text-base.font-extrabold").inner_text().strip()
                        price_text = card.locator("h3.text-2xl.font-extrabold").inner_text().strip()
                        location = card.locator("p.text-dark-neutral").inner_text().strip()

                        price = parse_price(price_text)

                        # Apply filters if provided
                        if filters:
                            # Case-insensitive typology matching
                            if filters.get("typology") and filters["typology"].lower() not in title.lower():
                                continue
                            # Partial location matching
                            if filters.get("location"):
                                location_parts = [part.strip() for part in location.lower().split(",")]
                                logger.debug(f"Checking location {filters['location']} in {location_parts}")
                                if not any(filters["location"].lower() in part for part in location_parts):
                                    continue
                            if filters.get("max_price") and price > filters["max_price"]:
                                continue

                        listings.append({
                            "title": title,
                            "price": price_text,
                            "location": location
                        })

                        page.wait_for_timeout(100)
                    except TimeoutError as e:
                        logger.warning(f"Timeout on card {i+1}: {e}")
                    except Exception as e:
                        logger.warning(f"Error on card {i+1}: {e}")

                break
            except Exception as e:
                logger.error(f"Failed to load page (attempt {attempt+1}): {e}")
                if attempt == 2:
                    return listings
        browser.close()

    logger.info(f"Filtered Listings: {len(listings)}")
    return listings