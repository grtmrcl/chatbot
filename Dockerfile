FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip config set global.index-url https://pypi.flatt.tech/simple/
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .
COPY lib/ ./lib/
COPY batch/ ./batch/
COPY template.yml .

CMD ["python", "bot.py"]
