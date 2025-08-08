from playwright.sync_api import sync_playwright, TimeoutError
from utils import parse_price
import logging
import time

logger = logging.getLogger(__name__)

def scrape_casayes(filters=None):
    logger.info(f"Scraping CasaYes with filters: {filters}")
    listings = []

    MAX_PAGES = 50
    MAX_LISTINGS = 100  # Stop after collecting 100 matching listings
    current_page = 1
    start_time = time.time()
    MAX_SCRAPE_TIME = 900  # 15 minutes max scrape time

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto("https://casayes.pt/pt/comprar/casaseapartamentos", timeout=30000)
            page.wait_for_selector("div[data-id='listing-card-container']", timeout=30000)

            while True:
                # Check for max scrape time
                if time.time() - start_time > MAX_SCRAPE_TIME:
                    logger.warning(f"Scraping stopped: exceeded max scrape time of {MAX_SCRAPE_TIME} seconds")
                    break

                # Check for max listings
                if len(listings) >= MAX_LISTINGS:
                    logger.info(f"Reached max listings limit: {MAX_LISTINGS}")
                    break

                logger.info(f"Scraping page {current_page}")

                # Scroll to bottom
                for _ in range(5):
                    page.mouse.wheel(0, 1500)
                    page.wait_for_timeout(1000)

                cards = page.locator("div[data-id='listing-card-container']")
                count = cards.count()
                logger.info(f"Cards found on page: {count}")

                for i in range(count):
                    card = cards.nth(i)
                    try:
                        if not card.is_visible():
                            continue

                        title_el = card.locator("h2.text-base.font-extrabold")
                        title = title_el.inner_text(timeout=5000).strip() if title_el.count() else None
                        if not title:
                            logger.debug(f"Card #{i+1} has no title, skipping.")
                            continue

                        price_el = card.locator("h3.text-2xl.font-extrabold span")
                        price_text = price_el.inner_text(timeout=5000).strip() if price_el.count() else None
                        if not price_text:
                            logger.warning(f"Card #{i+1} has no price text, skipping.")
                            continue

                        location_el = card.locator("p.text-dark-neutral")
                        location = location_el.inner_text(timeout=5000).strip() if location_el.count() else None

                        link_suffix = card.locator("a[data-id='listing-card-link']").get_attribute("href")
                        link = f"https://casayes.pt{link_suffix}" if link_suffix else None

                        spans = card.locator("div.mt-5 span")
                        area = bedrooms = bathrooms = None

                        if spans.count() >= 1:
                            area_text = spans.nth(0).inner_text(timeout=3000).strip()
                            if "m" in area_text.lower():
                                area = int(''.join(filter(str.isdigit, area_text)))
                        if spans.count() >= 2:
                            bed_text = spans.nth(1).inner_text(timeout=3000).strip()
                            bedrooms = int(bed_text) if bed_text.isdigit() else None
                        if spans.count() >= 3:
                            bath_text = spans.nth(2).inner_text(timeout=3000).strip()
                            bathrooms = int(bath_text) if bath_text.isdigit() else None

                        price = parse_price(price_text)
                        if price is None:
                            logger.warning(f"Failed to parse price '{price_text}' for card #{i+1}, skipping.")
                            continue

                        # Log listing details before filtering
                        logger.debug(f"Processing listing #{i+1}: title={title}, price={price}, location={location}, area={area}, bedrooms={bedrooms}, bathrooms={bathrooms}")

                        # Apply filters
                        if filters:
                            if filters.get("typology") and filters["typology"].lower() not in title.lower():
                                logger.debug(f"Filtered out #{i+1}: typology {filters['typology']} not in {title}")
                                continue
                            if filters.get("location") and location and filters["location"].lower() not in location.lower():
                                logger.debug(f"Filtered out #{i+1}: location {filters['location']} not in {location}")
                                continue
                            if filters.get("min_price") and price < filters["min_price"]:
                                logger.debug(f"Filtered out #{i+1}: price {price} < {filters['min_price']}")
                                continue
                            if filters.get("max_price") and price > filters["max_price"]:
                                logger.debug(f"Filtered out #{i+1}: price {price} > {filters['max_price']}")
                                continue
                            if filters.get("area_min") and (not area or area < filters["area_min"]):
                                logger.debug(f"Filtered out #{i+1}: area {area} < {filters['area_min']}")
                                continue
                            if filters.get("area_max") and area and area > filters["area_max"]:
                                logger.debug(f"Filtered out #{i+1}: area {area} > {filters['area_max']}")
                                continue
                            if filters.get("bedrooms") is not None and bedrooms is not None and bedrooms != filters["bedrooms"]:
                                logger.debug(f"Filtered out #{i+1}: bedrooms {bedrooms} != {filters['bedrooms']}")
                                continue
                            if filters.get("wc") is not None and bathrooms is not None and bathrooms != filters["wc"]:
                                logger.debug(f"Filtered out #{i+1}: bathrooms {bathrooms} != {filters['wc']}")
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
                        logger.warning(f"Error on card #{i+1}: {str(e)}")

                if current_page >= MAX_PAGES:
                    logger.info(f"Reached max pages limit: {MAX_PAGES}")
                    break

                try:
                    next_btn = page.locator('button[data-id="search-pagination-arrow-right-button"]')
                    if next_btn.count() and next_btn.is_enabled():
                        logger.info("➡️ Clicking Next page...")
                        next_btn.click()
                        current_page += 1
                        page.wait_for_timeout(3000)
                        time.sleep(0.5)  # Reduced delay to speed up scraping
                        page.wait_for_selector("div[data-id='listing-card-container']", timeout=10000)
                    else:
                        logger.info("No Next button or it's disabled. Stopping pagination.")
                        break
                except Exception as e:
                    logger.warning(f"Pagination error or end reached: {e}")
                    break

        except Exception as e:
            logger.error(f"Failed to load page: {str(e)}", exc_info=True)
            raise
        finally:
            browser.close()

    total_time = time.time() - start_time
    logger.info(f"Scraping completed: {len(listings)} listings found across {current_page - 1} pages in {total_time:.2f} seconds")
    return listings