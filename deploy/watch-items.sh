#!/bin/sh
set -eu
set -a
. /etc/buyback.env
set +a
cd /srv/buyback/app
while :; do
    if /usr/sbin/runuser -u buyback -- /srv/buyback/venv/bin/python -c 'import os, django; django.setup(); from buyback.models import EveItemTax; raise SystemExit(0 if EveItemTax.objects.filter(needs_update=True).exists() else 1)'; then
        printf '%s Pending items detected; fetching metadata\n' "$(date -u +%FT%TZ)"
        /usr/local/sbin/buyback-update-items || printf '%s Update failed or another run is active\n' "$(date -u +%FT%TZ)"
    fi
    sleep 30
done
