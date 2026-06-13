#!/bin/bash
set -e
echo "Resetting database..."
python reset_db_prod.py
echo "Running database migrations..."
python manage.py migrate --noinput
echo "Running superuser creation script..."
python create_superuser_prod.py
echo "Done!"
