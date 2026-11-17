#!/bin/sh
set -eu
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.production}"
exec gunicorn --bind 127.0.0.1:8000 config.wsgi:application
