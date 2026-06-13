#!/bin/bash
set -e
echo "Running database migrations..."
python manage.py migrate --noinput
echo "Done!"
