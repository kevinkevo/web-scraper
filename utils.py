import re
import os
import tempfile
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.colors import black, gray, blue
from reportlab.lib.units import cm

def parse_price(price_str):
    if not price_str:
        return None
    price_str = re.sub(r'[^\d]', '', price_str.strip())
    try:
        return int(price_str)
    except ValueError:
        return None

def extract_intent_from_text(text):
    intent = {
        "typology": None,
        "wc": None,
        "bedrooms": None,
        "min_price": None,
        "max_price": None,
        "area_min": None,
        "area_max": None,
        "location": None,
    }

    text = text.lower().strip()

    # Typology (e.g., T2, T3)
    typology_match = re.search(r"\bt(\d+)\b", text)
    if typology_match:
        intent["typology"] = f"T{typology_match.group(1)}"

    # WC
    wc_match = re.search(r"(\d+)\s*(wc|wcs)", text)
    if wc_match:
        intent["wc"] = int(wc_match.group(1))

    # Bedrooms
    bedrooms_match = re.search(r"(\d+)\s*(quarto|quartos)", text)
    if bedrooms_match:
        intent["bedrooms"] = int(bedrooms_match.group(1))

    # Location
    location_stop_words = r"\b(com|até|mais de|no máximo|wc|wcs|t\d|quartos?)\b"
    location_match = re.search(
        r"\b(?:em|na)\s+([a-zçãáâéêíóõôú\s\-]+?)(?=\s+" + location_stop_words + r"|$)", text
    )
    if location_match:
        intent['location'] = location_match.group(1).strip()

    # Prices
    price_matches = re.findall(r"(\d{2,6})\s*€", text)
    if len(price_matches) >= 2:
        intent["min_price"] = int(price_matches[0])
        intent["max_price"] = int(price_matches[1])
    elif len(price_matches) == 1:
        if "mais de" in text:
            intent["min_price"] = int(price_matches[0])
        elif "até" in text or "no máximo" in text:
            intent["max_price"] = int(price_matches[0])

    # Area
    area_min_match = re.search(r"mais\s+de\s+(\d+)\s*m", text)
    if area_min_match:
        intent["area_min"] = int(area_min_match.group(1))

    area_max_match = re.search(r"até\s+(\d+)\s*m", text)
    if area_max_match:
        intent["area_max"] = int(area_max_match.group(1))

    return intent

def format_filters(filters):
    parts = []
    if filters.get("location"):
        parts.append(f"📍 Localização: {filters['location'].title()}")
    if filters.get("min_price"):
        parts.append(f"💰 Preço mínimo: {filters['min_price']:,} €")
    if filters.get("max_price"):
        parts.append(f"💰 Preço máximo: {filters['max_price']:,} €")
    if filters.get("typology"):
        parts.append(f"🏘 Tipologia: {filters['typology']}")
    if filters.get("wc") is not None:
        parts.append(f"🛁 Casas de banho: {filters['wc']}")
    if filters.get("bedrooms") is not None:
        parts.append(f"🛏️ Quartos: {filters['bedrooms']}")
    if filters.get("area_min"):
        parts.append(f"📐 Área mínima: {filters['area_min']} m²")
    if filters.get("area_max"):
        parts.append(f"📏 Área máxima: {filters['area_max']} m²")
    return "\n".join(parts)

def generate_fallback_txt(data):
    filename = os.path.join(tempfile.gettempdir(), f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        for item in data:
            f.write(f"{item['title']} — {item['price']}\n")
            f.write(f"{item['location']}")
            if item.get("area"):
                f.write(f" | {item['area']} m²")
            if item.get("bedrooms") is not None:
                f.write(f" | Quartos: {item['bedrooms']}")
            if item.get("bathrooms") is not None:
                f.write(f" | Casas de banho: {item['bathrooms']}")
            f.write(f"\nLink: {item['link']}\n\n")
    return filename

def generate_pdf_report(data, filters=None, filename=None):
    if not filename:
        filename = os.path.join(tempfile.gettempdir(), f"imoveis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=2*cm,
        bottomMargin=1.5*cm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=14,
        leading=18,
        alignment=TA_CENTER,
        spaceAfter=12,
        textColor=black
    )
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        alignment=TA_CENTER,
        spaceAfter=10,
        textColor=gray
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        alignment=TA_LEFT,
        spaceAfter=6,
        spaceBefore=6
    )
    wrap_style = ParagraphStyle(
        'Wrap',
        parent=body_style,
        fontSize=8,
        leading=10,
        alignment=TA_LEFT,
        spaceAfter=6,
        spaceBefore=6,
        wordWrap='LTR'
    )

    elements = []
    elements.append(Spacer(1, 24))
    elements.append(Paragraph("Relatório de Imóveis - CasaYes", title_style))
    elements.append(Paragraph(f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", subtitle_style))
    if filters:
        elements.append(Paragraph("Filtros Aplicados:", subtitle_style))
        elements.append(Paragraph(format_filters(filters).replace('\n', '<br/>'), body_style))
    elements.append(Spacer(1, 12))

    table_data = [['Título', 'Localização', 'Preço', 'Área', 'Quartos', 'WC', 'Link']]
    for item in data:
        title = item['title'] or '-'
        location = item['location'] or '-'
        price = item['price'] or '-'
        area = f"{item['area']} m²" if item.get('area') else '-'
        bedrooms = str(item['bedrooms']) if item.get('bedrooms') is not None else '-'
        bathrooms = str(item['bathrooms']) if item.get('bathrooms') is not None else '-'
        link = f"<link href='{item['link']}' color='blue'>Ver imóvel</link>" if item.get('link') else '-'

        table_data.append([
            Paragraph(title, wrap_style),
            Paragraph(location, wrap_style),
            price,
            area,
            bedrooms,
            bathrooms,
            Paragraph(link, wrap_style)
        ])

    table = Table(table_data, colWidths=[8*cm, 3*cm, 2.2*cm, 2*cm, 1.5*cm, 1.5*cm, 2.5*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), gray),
        ('TEXTCOLOR', (0, 0), (-1, 0), black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, black),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(table)

    doc.build(elements)
    return filename
