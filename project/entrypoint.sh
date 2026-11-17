#!/bin/sh
set -e

# Only the web container (the one running gunicorn) prepares the database and the static files.
# The Celery worker and beat share this image but must not run migrations at the same time.
if [ "$1" = "gunicorn" ]; then
    python manage.py migrate --noinput
    # python manage.py seed_data --if-empty      # first start only: never overwrites edits made in Admin
    python manage.py collectstatic --noinput   # Django Admin and the browsable API styles, served by WhiteNoise

    # # Optional first login for a fresh install: set these three in .env (see .env.example).
    # if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    #     python manage.py createsuperuser --noinput || echo "Superuser already exists, nothing to do."
    # fi
fi

exec "$@"