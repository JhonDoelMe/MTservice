FROM python:3.11-slim

# Встановлення системних залежностей
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копіювання та встановлення залежностей Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копіювання коду проєкту
COPY . .

# Порт для Telegram Mini App
EXPOSE 8080

CMD ["python", "-m", "bot.main"]
