# ISP Subscription Management Platform

Django REST Framework API for managing ISP customers, packages, subscriptions, renewal alerts, and reports.

The project uses:

- Django 6.1
- Django REST Framework
- MySQL 8.4
- RabbitMQ
- Celery
- Gunicorn
- WhiteNoise
- Docker Compose

The Django application, database, RabbitMQ, Celery worker, and Celery Beat can all be run through Docker.

---

## 1. Prerequisites

You do **not** need Python, MySQL, RabbitMQ, or Celery installed directly on your machine when running the project through Docker.

You need:

- [Git](https://git-scm.com/downloads)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- WSL 2 on Windows
- A code editor such as VS Code

Check your installations:

```bash
git --version
docker --version
docker compose version
```

Make sure Docker Desktop is running before continuing.

---

# 2. Project Structure

The repository is structured around the Django project and its domain-specific applications.

```text
<repo root>/
├── compose.yml
├── compose.production.yml
├── .env
├── .env.example
│
└── project/
    ├── Dockerfile
    ├── entrypoint.sh
    ├── requirements.txt
    ├── manage.py
    │
    ├── customers/
    ├── packages/
    ├── subscriptions/
    ├── alerts/
    ├── reports/
    │
    └── project/
        ├── settings/
        │   ├── base.py
        │   ├── development.py
        │   └── production.py
        ├── celery.py
        ├── urls.py
        ├── wsgi.py
        └── asgi.py
```

### Django applications

| App | Responsibility |
|---|---|
| `customers` | Customers, users, authentication and staff-related functionality |
| `packages` | ISP packages and related package information |
| `subscriptions` | Customer subscriptions and subscription lifecycle |
| `alerts` | Subscription renewal/expiry alerts and Celery tasks |
| `reports` | Reporting functionality |

The applications remain separate Django apps at the same level rather than being placed inside an additional `apps/` package.

The `project/project/` package contains the Django project configuration, including settings, URL routing, Celery configuration, WSGI and ASGI.

---

# 3. First-Time Setup

## 3.1 Clone the repository

```bash
git clone https://github.com/khwezimbobo/project_2
cd project_2
```

All Docker Compose commands below should be run from the **repository root**, where the Compose files and `.env` file are located.

---

## 3.2 Create the `.env` file

The `.env` file contains environment variables and secrets and must **never be committed to Git**.

It should be located next to the Compose files:

```text
<repo root>/
├── .env
├── docker-compose.yml
├── docker-compose.production.yml
└── project/
```

If `.env.example` is provided:

### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

### macOS / Linux / Git Bash

```bash
cp .env.example .env
```

Then fill in the required values.

### Environment variables

| Variable | Example | Purpose |
|---|---|---|
| `DEBUG` | `1` | Enables Django debug mode in development |
| `SECRET_KEY` | long random string | Django secret key |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Hosts Django will accept |
| `DB_NAME` | `isp_subscription_system` | MySQL database name |
| `DB_USER` | `root` | MySQL username |
| `DB_PASSWORD` | your password | MySQL password |
| `DB_HOST` | `db` | MySQL Docker service name |
| `DB_PORT` | `3306` | MySQL container port |
| `RABBITMQ_USER` | your username | RabbitMQ username |
| `RABBITMQ_PASSWORD` | your password | RabbitMQ password |
| `CELERY_BROKER_URL` | `amqp://USER:PASSWORD@rabbitmq:5672//` | Celery RabbitMQ connection |

Inside Docker, `DB_HOST` must be:

```text
db
```

and not:

```text
localhost
```

because Django connects to the MySQL service over the Docker network.

---

## 3.3 Generate a secret key

A secret key can be generated using the Python Docker image without installing Python locally:

```bash
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Put the generated value into `.env`:

```text
SECRET_KEY=your-generated-secret
```

---

# 4. Development Environment

The normal development environment uses:

```text
docker-compose.yml
```

The Django development settings are selected through:

```text
DJANGO_SETTINGS_MODULE=project.settings.development
```

The development environment uses Django's development server and mounts the source code into the container so changes are reflected without rebuilding the image.

---

## 4.1 Check the Compose configuration

From the repository root:

```bash
docker compose config
```

If Docker reports that an environment variable is missing, check the `.env` file.

---

## 4.2 Build and start the project

```bash
docker compose up --build
```

To run in the background:

```bash
docker compose up --build -d
```

The main services are:

- `db` — MySQL
- `rabbitmq` — RabbitMQ
- `django` — Django development server
- `celery_worker` — Celery worker
- `celery_beat` — scheduled Celery tasks

MySQL and RabbitMQ use health checks, so the Django and Celery services wait for those dependencies to become healthy.

---

# 5. Database and Seed Data

Django migrations can be run with:

```bash
docker compose exec django python manage.py migrate
```

The project contains three custom management commands:

```bash
docker compose exec django python manage.py seed_data
docker compose exec django python manage.py seed_customers
docker compose exec django python manage.py create_groups
```

### `seed_data`

Creates the project's base ISP/package data.

### `seed_customers`

Creates the required customer/user seed data.

### `create_groups`

Creates the staff groups and their associated permissions.

The seed commands are designed to be safe to run repeatedly.

---

## 5.1 Create a superuser

If you need a separate Django superuser for development:

```bash
docker compose exec django python manage.py createsuperuser
```

---

# 6. Static Files

The project uses **WhiteNoise** to serve static files.

Collect static files with:

```bash
docker compose exec django python manage.py collectstatic --noinput
```

In the production container, `collectstatic` is run automatically by the entrypoint when Gunicorn starts.

WhiteNoise means a separate Nginx container is not required for the current deployment architecture.

---

# 7. Check That Everything Works

Once the development environment is running:

| Service | Address |
|---|---|
| Django | http://localhost:8000 |
| Django Admin | http://localhost:8000/admin/ |
| RabbitMQ Management | http://localhost:15672 |
| MySQL | `localhost:3307` |

RabbitMQ's management interface uses the RabbitMQ username and password from `.env`.

MySQL can be accessed from the host using:

```text
Host: localhost
Port: 3307
```

Inside Docker, Django connects using:

```text
Host: db
Port: 3306
```

---

# 8. API

The API is organised by application:

```text
/api/customers/
/api/packages/
/api/subscriptions/
/api/alerts/
/api/reports/
```

The application structure and HTTP routing are separate concepts. The Django apps are named according to their domain while the API paths remain under `/api/`.

Authentication uses JWT through Django REST Framework SimpleJWT.

---

# 9. Celery and RabbitMQ

RabbitMQ acts as the Celery message broker.

The project contains two Celery services:

```text
celery_worker
celery_beat
```

The worker executes asynchronous tasks.

Celery Beat schedules periodic tasks.

Current scheduled tasks include:

| Time | Task |
|---|---|
| 07:00 | Check expiring subscriptions |
| 07:15 | Automatically suspend overdue subscriptions |

The schedule uses the project's configured timezone.

Check the worker:

```bash
docker compose logs celery_worker
```

Check Beat:

```bash
docker compose logs celery_beat
```

You can also test worker connectivity with:

```bash
docker compose exec celery_worker celery -A project inspect ping
```

A successful response indicates that the worker is responding.

---

# 10. Production Configuration

The project also contains a production Compose configuration:

```text
docker-compose.production.yml
```

The production environment uses:

```text
DJANGO_SETTINGS_MODULE=project.settings.production
```

and runs Django through Gunicorn rather than Django's development server.

Start the production configuration with:

```bash
docker compose -f compose.production.yml up --build
```

Or in the background:

```bash
docker compose -f compose.production.yml up --build -d
```

The production Django service runs:

```text
Gunicorn → 0.0.0.0:8000
```

The production image does not bind-mount the source code into the container.

---

## 10.1 Production startup

When the production Django container starts, the entrypoint performs the required startup operations before launching Gunicorn:

```text
migrate
seed_data
seed_customers
create_groups
collectstatic
Gunicorn
```

This means a separate manual migration/seed step is normally not required when starting the production Compose environment.

---

## 10.2 Production checks

Run Django's deployment checks with:

```bash
docker compose -f docker-compose.production.yml exec django python manage.py check --deploy
```

Some deployment warnings may be expected when testing the production configuration locally over plain HTTP.

For an actual public deployment, HTTPS and the appropriate production security configuration must be provided.

---

# 11. Everyday Docker Commands

### Start everything

```bash
docker compose up
```

Use `-d` to run in the background:

```bash
docker compose up -d
```

### Stop everything

```bash
docker compose down
```

This removes the containers but keeps persistent volumes.

### Show running services

```bash
docker compose ps
```

### Follow all logs

```bash
docker compose logs -f
```

### Follow Django logs

```bash
docker compose logs -f django
```

### Follow Celery worker logs

```bash
docker compose logs -f celery_worker
```

### Follow Celery Beat logs

```bash
docker compose logs -f celery_beat
```

### Restart a service

```bash
docker compose restart celery_worker
```

### Open a shell inside Django

```bash
docker compose exec django sh
```

### Open the Django shell

```bash
docker compose exec django python manage.py shell
```

### Run Django checks

```bash
docker compose exec django python manage.py check
```

---

# 12. Models and Migrations

After changing a Django model:

```bash
docker compose exec django python manage.py makemigrations
docker compose exec django python manage.py migrate
```

Commit migration files together with the model changes.

### Migration guidelines

- Never delete shared migrations simply to resolve a migration problem.
- Do not manually edit migrations that have already been shared.
- Change the model and create a new migration instead.
- New Django applications must be added to `INSTALLED_APPS`.
- If two branches create conflicting migrations, Django can generate a merge migration:

```bash
docker compose exec django python manage.py makemigrations --merge
```

Preview migrations without creating files:

```bash
docker compose exec django python manage.py makemigrations --dry-run
```

---

# 13. Testing

Run the project's test suite using the appropriate test settings:

```bash
docker compose exec django python manage.py test --settings=project.settings.test
```

If the project does not contain a separate test settings module, use the settings configuration provided by the current test setup.

Tests should be run before submitting changes for review.

---

# 14. Working With Git

Development work should normally be done on a feature/story branch rather than directly on `main`.

Example:

```bash
git switch main
git pull
git switch -c customers
```

Make your changes, then:

```bash
git add .
git commit -m "added customer serializer and viewset"
git push -u origin customers
```

Open a pull request into `main`.

Before opening or updating a pull request, bring your branch up to date:

```bash
git fetch
git merge origin/main
```

Resolve any conflicts, test the project, and then push the updated branch.

### Important

Never commit `.env`.

Check before committing:

```bash
git status
```

---

# 15. Pulling Changes From the Repository

After pulling changes:

```bash
git pull
```

The required Docker action depends on what changed.

| Change | Action |
|---|---|
| Python application code | Development server normally reloads automatically |
| `requirements.txt` | `docker compose up --build` |
| `Dockerfile` | `docker compose up --build` |
| New migrations | `docker compose exec django python manage.py migrate` |
| Celery tasks/configuration | Restart the Celery services |
| Compose configuration | Recreate the affected services |
| `.env` values | Recreate the affected containers |

For example:

```bash
docker compose up -d --build
```

or:

```bash
docker compose up -d --force-recreate
```

---

# 16. Resetting Docker Data

### Stop and remove containers

```bash
docker compose down
```

Persistent data is retained.

### Remove containers and volumes

```bash
docker compose down -v
```

**Warning:** this removes the project's persistent MySQL and RabbitMQ volumes and therefore deletes their stored data.

Do not use this command unless you intentionally want to reset the persistent data.

### Rebuild without using the Docker build cache

```bash
docker compose build --no-cache
docker compose up
```

This can help when troubleshooting stale Docker images or dependency changes.

---

# 17. Important Docker Notes

## MySQL credentials

MySQL reads its initialization credentials when the database volume is first created.

Changing the values in `.env` does not automatically change the credentials of an already-initialized MySQL volume.

If credentials need to be changed, either update them inside MySQL or intentionally recreate the database volume.

Do **not** use:

```bash
docker compose down -v
```

unless deleting the existing database is acceptable.

---

## RabbitMQ credentials

The same principle applies to RabbitMQ.

If RabbitMQ was initialized with one username/password, changing `.env` does not automatically recreate the RabbitMQ user.

If the credentials no longer match, check the existing RabbitMQ configuration or intentionally reset its volume.

---

# 18. Troubleshooting

| Problem | Possible solution |
|---|---|
| `exec /usr/src/app/entrypoint.sh: no such file or directory` | Check that `entrypoint.sh` uses LF line endings rather than CRLF |
| Compose says a variable is not set | Check `.env` exists in the repository root and contains the required variable |
| RabbitMQ `ACCESS_REFUSED` | Check that the RabbitMQ credentials and `CELERY_BROKER_URL` match |
| `Unable to load celery application` | Check that Celery uses `-A project` and that `project/celery.py` is configured correctly |
| `KeyError: 'CELERY_BROKER_URL'` | Add `CELERY_BROKER_URL` to `.env` and recreate the container |
| `settings.ALLOWED_HOSTS` error | Check `DEBUG`, `ALLOWED_HOSTS`, and the active settings module |
| Django cannot connect to MySQL | Use `DB_HOST=db` inside Docker and wait for MySQL to become healthy |
| `No changes detected` from `makemigrations` | Check that the Django application is included in `INSTALLED_APPS` and that the model has changed |
| Port already allocated | Another process is using the required host port; stop it or change the host-side mapping |
| Settings changes are not applying | Recreate the containers after changing environment variables |
| Static files are missing | Run `collectstatic` and check that WhiteNoise is enabled |
| Celery tasks are not executing | Check RabbitMQ, the Celery worker logs, and the Celery Beat logs |

For the entrypoint, make sure the file uses Unix line endings:

```text
LF
```

rather than:

```text
CRLF
```

A `.gitattributes` entry can help prevent this from happening again:

```text
*.sh text eol=lf
```

---

# 19. Service Overview

The complete Docker environment consists of five services:

```text
                    ┌──────────────────┐
                    │      Django      │
                    │  Gunicorn /      │
                    │  development     │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐   ┌───────────┐   ┌────────────┐
        │  MySQL   │   │ RabbitMQ  │   │   Celery   │
        │   db     │   │           │   │   Worker   │
        └──────────┘   └─────┬─────┘   └────────────┘
                             │
                             ▼
                       ┌────────────┐
                       │   Celery   │
                       │    Beat    │
                       └────────────┘
```

### Services

| Service | Purpose |
|---|---|
| `django` | Runs the Django application |
| `db` | MySQL database |
| `rabbitmq` | Celery message broker |
| `celery_worker` | Executes asynchronous Celery tasks |
| `celery_beat` | Schedules periodic Celery tasks |

The Django, Celery Worker, and Celery Beat services use the same application image.

---

# 20. Application Overview

The project is divided into domain-specific Django applications:

```text
customers
    │
    ├── Customer/user management
    └── Authentication and staff functionality

packages
    │
    └── ISP package management

subscriptions
    │
    └── Customer subscription lifecycle

alerts
    │
    └── Renewal and expiry alerts

reports
    │
    └── Reporting functionality
```

The applications communicate through Django's models, serializers, views, URLs, and Celery tasks while remaining separated according to their domain responsibilities.

The public API routes remain:

```text
/api/customers/
/api/packages/
/api/subscriptions/
/api/alerts/
/api/reports/
```

This structure keeps the project's domain boundaries clear while keeping the Django project configuration separate from the individual applications.
