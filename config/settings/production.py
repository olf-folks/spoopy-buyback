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

# Nginx overwrites this header and Gunicorn listens on loopback only.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
JANICE_API_KEY = config("JANICE_API_KEY", default="")

# Activate only after the EVE developer app and alliance policy are configured.
EVE_LOGIN_ENABLED = config("EVE_LOGIN_ENABLED", default=False, cast=bool)
EVE_SSO_CLIENT_ID = config("EVE_SSO_CLIENT_ID", default="")
EVE_SSO_CALLBACK_URL = config("EVE_SSO_CALLBACK_URL", default="https://buyback.spoopy.net/buyback/auth/eve/callback/")
EVE_ALLIANCE_IDS = config("EVE_ALLIANCE_IDS", default="", cast=lambda value: [int(v.strip()) for v in value.split(",") if v.strip()])
EVE_REQUIRE_LOGIN = config("EVE_REQUIRE_LOGIN", default=False, cast=bool)

EVE_SPECIAL_CORPORATION_ID = config("EVE_SPECIAL_CORPORATION_ID", default=98472700, cast=int)

EVE_BUYBACK_CORPORATION_ID = config("EVE_BUYBACK_CORPORATION_ID", default=98475239, cast=int)
EVE_TOKEN_ENCRYPTION_KEY = config("EVE_TOKEN_ENCRYPTION_KEY", default="")

EVE_STAFF_AUTH_ENABLED = config("EVE_STAFF_AUTH_ENABLED", default=True, cast=bool)
