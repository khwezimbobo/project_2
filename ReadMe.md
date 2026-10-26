# Project Setup & Command Guide

ISP Subscription Management Platform: Django, DRF, MySQL, RabbitMQ, Celery, all run through Docker Compose.

You do **not** need Python, MySQL or RabbitMQ installed on your machine. Docker runs all of it.

All `docker compose` commands below are run from the **project root**, the folder that contains `docker-compose.yml` (not the inner `project/` folder).

---

## 1. Prerequisites

- [Git](https://git-scm.com/downloads)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/), running (on Windows, use the WSL 2 backend)
- A code editor such as VS Code

Check the installs:

```
git --version
docker --version
docker compose version
```

---

## 2. First-time setup (after cloning)

### 2.1 Clone the repository

```
git clone https://github.com/khwezimbobo/project_2
cd /project_2
```

### 2.2 Create your `.env` file

The `.env` file holds secrets and is **never committed to Git**. It must sit next to `docker-compose.yml` and be named exactly `.env`.

If the repo has a `.env.example`, copy it and fill in the values:

```
# Windows PowerShell
Copy-Item .env.example .env

# macOS / Linux / Git Bash
cp .env.example .env
```

If there is no `.env.example`, ask a teammate for the `.env` file and share it privately, never in a public chat or repo.

Variables the project expects:

| Variable | Example | Notes |
| --- | --- | --- |
| `DEBUG` | `1` | Must be exactly `1` for debug mode |
| `SECRET_KEY` | long random string | Generate your own, never reuse |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma separated, no spaces or quotes |
| `DB_NAME` | `isp_subscription_system` | |
| `DB_USER` | `root` | Used for development |
| `DB_PASSWORD` | your password | Set before the first start (see Section 6) |
| `DB_HOST` | `db` | The MySQL service name, **not** `localhost` |
| `DB_PORT` | `3306` | |
| `RABBITMQ_USER` | your username | Case-sensitive |
| `RABBITMQ_PASSWORD` | your password | Avoid `@`, `/` and `#` |
| `CELERY_BROKER_URL` | `amqp://USER:PASSWORD@rabbitmq:5672//` | User and password must match the two lines above |

Generate a secret key (any one of these):

```
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### 2.3 Check the configuration

```
docker compose config
```

If it prints a warning like `The "RABBITMQ_USER" variable is not set`, that variable is missing from `.env`.

### 2.4 Build and start everything

```
docker compose up --build
```

The first build takes a few minutes. MySQL needs roughly 30 seconds to become healthy, and the other services wait for it. Add `-d` to run in the background.

### 2.5 Create the database tables (in a second terminal)

```
docker compose exec django python manage.py migrate
docker compose exec django python manage.py createsuperuser
```

Load the seed data (4 packages, 3 contract terms, 3 add-ons). It is safe to run more than once, and re-running resets those rows to their seed values:

```
docker compose exec django python manage.py seed_data
```

### 2.6 Check it works

| What | Where |
| --- | --- |
| Django app | http://localhost:8000 |
| Django Admin | http://localhost:8000/admin/ |
| RabbitMQ management UI | http://localhost:15672 (log in with your RabbitMQ user and password) |
| MySQL (for MySQL Workbench) | host `localhost`, port `3307`, user and password from `.env` |

The worker is healthy when `docker compose logs celery_worker` shows a "ready" line.

---

## 3. Every time you pull changes

```
git pull
```

Then, depending on what changed:

| If the pull included... | Run |
| --- | --- |
| Changes to `requirements.txt` or the `Dockerfile` | `docker compose up --build` |
| New migration files | `docker compose exec django python manage.py migrate` |
| Changes to Celery tasks | `docker compose restart celery_worker celery_beat` |
| Changes to `docker-compose.yml` or `.env` | `docker compose up -d --force-recreate` |
| Only Python code in views, serializers, etc. | Nothing. The dev server reloads by itself. |

---

## 4. Everyday commands

| Task | Command |
| --- | --- |
| Start everything | `docker compose up` (add `-d` for background) |
| Stop everything (keeps data) | `docker compose down` |
| Show running containers | `docker compose ps` |
| Follow logs | `docker compose logs -f` |
| Logs for one service | `docker compose logs -f django` (also `celery_worker`, `celery_beat`, `db`, `rabbitmq`) |
| Restart one service | `docker compose restart celery_worker` |
| Open a shell inside Django | `docker compose exec django sh` |
| Django shell | `docker compose exec django python manage.py shell` |
| Create a new app | `docker compose exec django python manage.py startapp <name>` |
| Check settings and models | `docker compose exec django python manage.py check` |

### Models and migrations

After you change a model:

```
docker compose exec django python manage.py makemigrations
docker compose exec django python manage.py migrate
```

Then commit the new migration files together with the model change.

- New apps must be listed in `INSTALLED_APPS` in `project/project/settings/base.py`, or Django reports "No changes detected".
- Never edit a migration that has already been shared. Change the model and create a new one instead.
- Preview without writing anything: `makemigrations --dry-run`.
- If two branches create conflicting migrations: `makemigrations --merge`.

### Tests

```
docker compose exec django pytest --ds=project.settings.test
```

This needs `pytest` and `pytest-django` in `requirements.txt`. The test settings use SQLite, so they don't depend on MySQL.

---

## 5. Working with Git

One short-lived branch per sprint board story, merged to `main` by pull request:

```
git switch main
git pull
git switch -c customers
git add .
git commit -m "added customer serializer and viewset"
git push -u origin customers
```

Open a pull request into `main` on GitHub. Before opening it, bring your branch up to date:

```
git fetch
git merge origin/main
```

Never commit `.env`. Check with `git status` before every commit.

---

## 6. Resetting things

| Goal | Command | Effect |
| --- | --- | --- |
| Stop and remove containers | `docker compose down` | Data kept |
| Wipe the **database** and RabbitMQ data | `docker compose down -v` | **Deletes the MySQL volume** |
| Reset only RabbitMQ | `docker compose down`, then `docker volume ls`, then `docker volume rm <name ending in rabbitmq_data>` | MySQL data kept |
| Rebuild from scratch | `docker compose build --no-cache` then `docker compose up` | Slower, fixes stale builds |

MySQL and RabbitMQ read their passwords from `.env` only when their volume is **first created**. If you change a password later, reset that service's volume (or change the password inside the service).

---

## 7. Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| `exec /usr/src/app/entrypoint.sh: no such file or directory` | `entrypoint.sh` has Windows (CRLF) line endings. In VS Code, click `CRLF` in the status bar, choose `LF`, save. A `.gitattributes` line `*.sh text eol=lf` prevents it coming back. |
| `variable is not set` warning from compose | `.env` is missing a variable, is in the wrong folder, or is named `.env.txt`. |
| RabbitMQ `ACCESS_REFUSED` / `invalid credentials` | The user or password in `CELERY_BROKER_URL` doesn't match what RabbitMQ was created with. Make them match, or reset the RabbitMQ volume (Section 6). |
| `Unable to load celery application` | Wrong app name in the compose command. It must be `-A project`, and `project/project/celery.py` plus the import in `__init__.py` must exist. |
| `KeyError: 'CELERY_BROKER_URL'` | Variable missing from `.env`. Recreate the containers after adding it. |
| `You must set settings.ALLOWED_HOSTS if DEBUG is False` | `DEBUG` isn't exactly `1`, or `ALLOWED_HOSTS` is empty or defined twice in `settings`. |
| `'list' object has no attribute 'lower'` | `ALLOWED_HOSTS` is a list inside a list. Keep one flat list. |
| Django can't connect to MySQL | `DB_HOST` must be `db`. Wait until `docker compose ps` shows `mysql` as healthy. |
| `MYSQL_USER="root"` error from the MySQL container | Don't pass `MYSQL_USER` or `MYSQL_PASSWORD` for the root user. Only `MYSQL_ROOT_PASSWORD` and `MYSQL_DATABASE` are needed. |
| `No changes detected` from `makemigrations` | The app isn't in `INSTALLED_APPS`, or the app has no models yet. |
| `port is already allocated` | Something else uses 8000, 3307 or 15672. Change the left-hand number of that port mapping in a local override. Don't commit the change. |
| Settings changes not applying | Containers read `.env` only when created. Run `docker compose up -d --force-recreate`. |

---

## 8. Project layout

```
<repo root>/
├── docker-compose.yml      # db, rabbitmq, django, celery_worker, celery_beat
├── .env                    # your secrets (never committed)
├── .env.example            # variable names for teammates
└── project/
    ├── Dockerfile
    ├── entrypoint.sh       # must keep LF line endings
    ├── requirements.txt
    ├── manage.py
    └── project/            # Django package
        ├── settings/       # base.py, development.py, test.py
        ├── celery.py
        ├── urls.py
        └── wsgi.py / asgi.py
```

Docker services: `db` (MySQL 8.4), `rabbitmq`, `django`, `celery_worker`, `celery_beat`. The worker and beat reuse the same image as Django.
