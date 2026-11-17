#!/bin/sh
set -eu
set -a
. /etc/buyback.env
set +a
cd /srv/buyback/app
exec /usr/bin/flock -n /run/lock/buyback-item-update.lock /usr/bin/timeout 50m /usr/sbin/runuser -u buyback -- /srv/buyback/venv/bin/python -c 'import logging; logging.basicConfig(level=logging.INFO); from django.core.management import execute_from_command_line; execute_from_command_line(["manage.py", "item-update"])'
