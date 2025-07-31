FROM python:3.10
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install
COPY . .
CMD ["python", "main.py"]