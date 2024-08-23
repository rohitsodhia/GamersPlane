#!/bin/sh

echo "Waiting for PostgreSQL..."

while nc -z $POSTGRES_HOST $POSTGRES_PORT; do
    sleep 1
    echo "Waiting"
done

echo "Database started"

python manage.py flush --no-input
python manage.py migrate

exec "$@"
