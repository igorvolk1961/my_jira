FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY static ./static

RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn[standard]>=0.30" "sqlalchemy>=2.0" "alembic>=1.13" "jinja2>=3.1" "python-multipart>=0.0.9" "itsdangerous>=2.2" "markdown-it-py>=4.2.0"

# Каталог для файлов SQLite-БД и резервных копий (монтируется как volume)
RUN mkdir -p /app/data

EXPOSE 5000

# Один воркер: SQLite - файловая БД, несколько процессов дадут конфликты записи
CMD ["uvicorn", "app.main:app", "--workers", "1", "--host", "0.0.0.0", "--port", "5000", "--timeout-keep-alive", "60"]
