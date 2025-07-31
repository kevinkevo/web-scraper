FROM python:3.10

# Install system dependencies required for Playwright
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk-bridge2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libxkbcommon0 \
    libgtk-3-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libdrm2 \
    libdbus-1-3 \
    libxshmfence1 \
    libnspr4 \
    libxcb1 \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright with all browser dependencies
RUN playwright install --with-deps

COPY . .

CMD ["python", "main.py"]
