#!/bin/bash
set -e # Exit immediately if a command fails

# 1. Wait for MySQL to be ready
./wait-for-it.sh db:3306 -- echo "Database is up"

# 2. Apply database migrations
python manage.py migrate

# 3. Gather static files into the folder Nginx is watching
python manage.py collectstatic

# 4. Run the command specified in the command argument (Gunicorn or Celery)
exec "$@"
