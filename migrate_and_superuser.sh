#!/bin/bash
set -e
echo "Running database migrations..."
python manage.py migrate --noinput
echo "Running superuser creation script..."
python create_superuser_prod.py
echo "Done!"
