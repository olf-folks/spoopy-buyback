from .base import *

import os

# --- Core ---
DEBUG = config("DEBUG", default=False, cast=bool)

# --- Media & Static Files ---
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "../", "mediafiles")

# Allow overriding STATIC_URL via environment
STATIC_URL = config(
    "STATIC_URL",
    default="/static/"  # fallback if not provided
)

# If you're serving static files via a CDN or Nginx alias, use:
# STATIC_ROOT = os.path.join(BASE_DIR, "../", "staticfiles")

# --- Security ---
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
    cast=lambda v: [s.strip() for s in v.split(",")]
)

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="",
    cast=lambda v: [s.strip() for s in v.split(",")] if v else []
)

# --- Optional HTTPS Proxy Handling ---
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

print("✅ Django production settings loaded successfully")
