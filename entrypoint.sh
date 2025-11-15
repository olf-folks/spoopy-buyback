#!/bin/sh
set -e

# Run migrations
python manage.py migrate

# Create default superuser if it doesn't exist
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'changeme')
END

# Update groups and categorys
python manage.py item-update

# Start Gunicorn
exec gunicorn --bind 0.0.0.0:8000 config.wsgi:application