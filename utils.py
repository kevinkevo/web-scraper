import os
import re
import tempfile
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def extract_intent_from_text(text):
    text = text.lower()
    filters = {
        "location": None,
        "typology": None,
        "max_price": None,
        "min_area": None,
        "bedrooms": None,
        "bathrooms": None
    }

    # Typology (T1, T2, etc.)
    typology_match = re.search(r"\bt[1-9](?:\+[0-9])?\b", text)
    if typology_match:
        filters["typology"] = typology_match.group().upper()

    # Price (até 300.000€)
    price_match = re.search(r"(?:até|up to|upto)\s*€?\s*([\d\s.,]+)", text)
    if price_match:
        try:
            filters["max_price"] = int(price_match.group(1).replace(" ", "").replace(".", "").replace(",", ""))
        except ValueError:
            pass

    # Area (acima de 100m²)
    area_match = re.search(r"(?:mais de|acima de|over)\s*([\d\s]+)\s*(?:m2|m²)", text)
    if area_match:
        try:
            filters["min_area"] = int(area_match.group(1).strip())
        except ValueError:
            pass

    # Bedrooms
    bed_match = re.search(r"(\d+)\s+(?:quartos|quarto|bedroom|bedrooms)", text)
    if bed_match:
        filters["bedrooms"] = int(bed_match.group(1))

    # Bathrooms
    bath_match = re.search(r"(\d+)\s+(?:wc|banheiros|casas de banho|bathroom|bathrooms)", text)
    if bath_match:
        filters["bathrooms"] = int(bath_match.group(1))

    # Location (em Amadora / in Lisbon)
    loc_match = re.search(r"(?:em|in)\s+([a-zçãõáéíóúàèìòùâêîôûäëïöü\s]+)", text)
    if loc_match:
        filters["location"] = loc_match.group(1).strip().title()
    else:
        loc_fallback = re.search(r"(lisboa|amadora|queluz|porto|santarém|coimbra|aveiro|setúbal)", text)
        if loc_fallback:
            filters["location"] = loc_fallback.group(1).title()

    return filters

def parse_price(price_text):
    digits = re.sub(r"[^\d]", "", price_text)
    return int(digits) if digits else 0

def generate_fallback_txt(data, filename=None):
    if not filename:
        filename = os.path.join(tempfile.gettempdir(), f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    with open(filename, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(f"{item['title']} — {item['price']}\n")
            f.write(f"{item['location']}")
            if item.get("area"):
                f.write(f" | {item['area']} m²")
            if item.get("bedrooms") is not None:
                f.write(f" | Quartos: {item['bedrooms']}")
            if item.get("bathrooms") is not None:
                f.write(f" | Casas de banho: {item['bathrooms']}")
            if item.get("link"):
                f.write(f"\n{item['link']}")
            f.write("\n\n")
    return filename

def format_filters(filters):
    parts = []
    if filters.get("typology"): parts.append(filters["typology"])
    if filters.get("location"): parts.append(filters["location"])
    if filters.get("max_price"): parts.append(f"até €{filters['max_price']:,}")
    if filters.get("min_area"): parts.append(f"mais de {filters['min_area']}m²")
    if filters.get("bedrooms") is not None: parts.append(f"{filters['bedrooms']} quartos")
    if filters.get("bathrooms") is not None: parts.append(f"{filters['bathrooms']} WC")
    return ", ".join(parts) if parts else "Nenhum"
