## Use BuildKit syntax for better caching & features
# syntax=docker/dockerfile:1

########################
## Builder image
########################
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies required to build some Python wheels (e.g. psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a relocatable prefix so we can copy them
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


########################
## Runtime image
########################
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

WORKDIR /app

# Install only the PostgreSQL client libraries needed at runtime for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
 && rm -rf /var/lib/apt/lists/*

# Copy installed dependencies from the builder image only (no build tools)
COPY --from=builder /install /usr/local

# Copy project code (rely on .dockerignore to avoid unnecessary files)
COPY . .

# Generate a random Django secret key and save it into .env at build time
RUN python -c "from django.core.management.utils import get_random_secret_key; print(f'SECRET_KEY={get_random_secret_key()}')" >> .env

# Expose port for Gunicorn
EXPOSE 8000

# Copy and prepare entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Entrypoint
CMD ["/entrypoint.sh"]