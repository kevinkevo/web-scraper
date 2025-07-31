import os
import re
import tempfile
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def extract_intent_from_text(text):
    filters = {
        "location": None,
        "typology": None,
        "max_price": None,
    }

    # Typology (e.g., T1, T2, T2+1)
    typology_match = re.search(r"\bT[1-9](?:\+[0-1])?\b", text.upper())
    if typology_match:
        filters["typology"] = typology_match.group()

    # Location (with or without "in"/"at")
    location_match = re.search(r"\b(?:in|at)\s+([A-Za-zÀ-ÿ\s]+?)(?:,| up to| upto|$)", text, re.IGNORECASE)
    if not location_match:
        location_match = re.search(r"\b([A-Za-zÀ-ÿ\s]+?)(?:,| up to| upto|$)", text, re.IGNORECASE)
    if location_match:
        filters["location"] = location_match.group(1).strip()

    # Max price (handle €250,000, 250k, up to/upto)
    price_match = re.search(r"(?:up\s*to|upto)\s*€?([\d\s.,]+)(k)?", text, re.IGNORECASE)
    if price_match:
        price_text = price_match.group(1).replace(",", "").replace(".", "").replace(" ", "")
        multiplier = 1000 if price_match.group(2) else 1
        try:
            filters["max_price"] = int(price_text) * multiplier
        except ValueError:
            pass

    return filters

def parse_price(price_text):
    price_digits = re.sub(r"[^\d]", "", price_text)
    return int(price_digits) if price_digits else 0

def generate_fallback_txt(data, filename=None):
    if not filename:
        filename = os.path.join(tempfile.gettempdir(), f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("CasaYes Real Estate Report\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for item in data:
                f.write(f"Title: {item['title']}\nPrice: {item['price']}\nLocation: {item['location']}\n\n")
        logger.info(f"Text report generated successfully at: {filename}")
        return filename
    except Exception as e:
        logger.error(f"Text report generation failed: {str(e)}")
        raise

def format_filters(filters):
    parts = []
    if filters["typology"]:
        parts.append(filters["typology"])
    if filters["location"]:
        parts.append(filters["location"])
    if filters["max_price"]:
        parts.append(f"up to €{filters['max_price']:,}")
    return ", ".join(parts) if parts else "None"