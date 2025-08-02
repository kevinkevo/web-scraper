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
                for _ in range(5):
                    page.mouse.wheel(0, 1500)
                    page.wait_for_timeout(1000)

                cards = page.locator("div[data-id='listing-card-container']")
                count = cards.count()
                logger.info(f"Cards found: {count}")

                for i in range(count):
                    card = cards.nth(i)
                    try:
                        title = card.locator("h2.text-base.font-extrabold").inner_text().strip()
                        price_text = card.locator("h3.text-2xl.font-extrabold span").inner_text().strip()
                        location = card.locator("p.text-dark-neutral").inner_text().strip()
                        link_suffix = card.locator("a[data-id='listing-card-link']").get_attribute("href")
                        link = f"https://casayes.pt{link_suffix}" if link_suffix else None

                        # Area
                        area_text = card.locator("div.mt-5 span").nth(0).inner_text().strip()
                        area = int(''.join(filter(str.isdigit, area_text))) if "m" in area_text.lower() else None

                        # Bedrooms
                        bed_text = card.locator("div.mt-5 span").nth(1).inner_text().strip()
                        bedrooms = int(bed_text) if bed_text.isdigit() else None

                        # Bathrooms
                        bath_text = card.locator("div.mt-5 span").nth(2).inner_text().strip()
                        bathrooms = int(bath_text) if bath_text.isdigit() else None

                        price = parse_price(price_text)

                        # Apply filters
                        if filters:
                            if filters.get("typology") and filters["typology"].lower() not in title.lower():
                                continue
                            if filters.get("location") and filters["location"].lower() not in location.lower():
                                continue
                            if filters.get("max_price") and price > filters["max_price"]:
                                continue
                            if filters.get("min_area") and (not area or area < filters["min_area"]):
                                continue
                            if filters.get("bedrooms") is not None and (bedrooms is None or bedrooms != filters["bedrooms"]):
                                continue
                            if filters.get("bathrooms") is not None and (bathrooms is None or bathrooms != filters["bathrooms"]):
                                continue

                        listings.append({
                            "title": title,
                            "price": price_text,
                            "location": location,
                            "link": link,
                            "area": area,
                            "bedrooms": bedrooms,
                            "bathrooms": bathrooms
                        })
                    except Exception as e:
                        logger.warning(f"Error on card {i+1}: {e}")
                break
            except Exception as e:
                logger.error(f"Failed to load page: {e}")
                if attempt == 2:
                    return listings
        browser.close()
    return listings
