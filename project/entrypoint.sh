#!/bin/sh

set -e

if [ "${RUN_SETUP:-0}" = "1" ]; then
    echo "[entrypoint] applying migrations (retrying until MySQL accepts connections)..."
    tries=0
    until python manage.py migrate --noinput; do
        tries=$((tries + 1))
        if [ "$tries" -ge 20 ]; then
            echo "[entrypoint] database never became ready, giving up"
            exit 1
        fi
        echo "[entrypoint] database not ready (attempt $tries/20), retrying in 3s..."
        sleep 3
    done

    echo "[entrypoint] seeding packages, contract terms and add-ons..."
    python manage.py seed_data

    echo "[entrypoint] collecting static files..."
    python manage.py collectstatic --noinput
fi

# Hand over to the real command (gunicorn / celery worker / celery beat)
exec "$@"