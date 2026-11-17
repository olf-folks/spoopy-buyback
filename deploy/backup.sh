#!/bin/sh
set -eu
umask 077
install -d -m 700 /var/backups/buyback
backup_file="/var/backups/buyback/buyback-$(date -u +%Y%m%dT%H%M%SZ).dump"
runuser -u postgres -- pg_dump -Fc buyback > "$backup_file.tmp"
mv "$backup_file.tmp" "$backup_file"
find /var/backups/buyback -name 'buyback-*.dump' -type f -mtime +14 -delete
