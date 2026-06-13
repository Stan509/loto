#!/bin/bash
set -e
echo "Running database migrations..."
python manage.py migrate --noinput
echo "Running partner seeding script..."
python create_partners_prod.py
echo "Done!"
