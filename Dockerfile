FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY *.py ./
COPY static ./static

RUN pip install --no-cache-dir flask==3.1.3 gunicorn>=21.2.0 markdown-it-py>=4.2.0

# Каталог для файлов SQLite-БД и резервных копий (монтируется как volume)
RUN mkdir -p /app/data

EXPOSE 5000

# Один воркер: SQLite - файловая БД, несколько процессов дадут конфликты записи
CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:5000", "--timeout", "60", "main:app"]
