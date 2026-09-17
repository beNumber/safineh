#!/bin/sh

set -e

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Running migrations..."
python manage.py migrate

echo "Starting Gunicorn..."
gunicorn safineh.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers 4 \
    --timeout 120 &

echo "Starting Nginx..."
nginx -g "daemon off;"
