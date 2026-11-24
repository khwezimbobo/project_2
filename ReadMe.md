# ISP Subscription Management Platform

A staff-facing Django REST API for an internet service provider (Project 2, redAcademy / Backspace Technologies).
It extends the Project 1 console tool into a multi-user web platform: JWT security, role-based access, a MySQL
database, Celery + RabbitMQ background jobs, a staff dashboard, Docker Compose and a GitHub Actions pipeline.

**Stack:** Python 3.12, Django 6.1, Django REST Framework, MySQL 8.4, Celery + RabbitMQ, Gunicorn,
drf-spectacular (Swagger), pytest-django, flake8, Docker Compose, GitHub Actions.

**Team:** Siseko Mtebele, Khwezi Mbobo, Cassidy.

## Features

- JWT login (access 60 minutes, refresh 7 days) with two roles: **Admin** (full access) and **Support Agent**
  (creates and views their own customers and subscriptions, cannot delete)
- Customers, packages, subscriptions, renewal alerts and reports, with search, filtering, ordering and
  pagination (20 per page)
- Pricing is calculated on the server (package rate x term multiplier, add-ons, best single discount,
  R500 installation fee); contract end dates are calculated from the term. Client-sent values are ignored.
- Status rules: Pending, Active, Suspended or Cancelled; a Cancelled subscription cannot be reactivated;
  every change is written to an audit log
- Agents can only reach their own customers (checked in `get_queryset()`); another agent's record returns 403
- Two daily Celery tasks: renewal alerts (07:00) and auto-suspension after the 30-day grace period (07:15)
- Staff dashboard at `/dashboard/` and Swagger documentation at `/api/docs/`

## Project structure

```
project_2/
  docker-compose.yml        five services: db, rabbitmq, web, celery_worker, celery_beat
  .env.example              placeholder settings (copy to .env)
  .github/workflows/ci.yml  flake8 + pytest on every push and pull request to main
  docs/                     ERD, sprint board, architecture diagram, test output, demo evidence
  project/
    manage.py, Dockerfile, entrypoint.sh, pytest.ini, requirements.txt
    project/                Django settings (base, development, test), URLs, Celery app
    customers/              custom User model, Customer API, permissions
    packages/               packages, contract terms, add-ons (read-only API), seed_data command
    subscriptions/          subscriptions, pricing and status services, audit log, auto-suspend task
    alerts/                 renewal alerts, acknowledge endpoint, expiry-check task
    reports/                revenue summary (raw SQL), expiring report, staff dashboard
    api/                    shared API code (custom error handler)
```

## 1. Environment setup

You only need **Docker Desktop** and **Git**. You do not need Python, MySQL or RabbitMQ installed.

```bash
git clone https://github.com/khwezimbobo/project_2.git
cd project_2
cp .env.example .env          # Windows PowerShell: Copy-Item .env.example .env
```

Open `.env` and replace every placeholder value. `.env` is listed in `.gitignore` and must never be committed.

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Django secret key. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DEBUG` | `1` turns debug on for local development; anything else (or unset) means off |
| `ALLOWED_HOSTS` | Comma-separated hosts, for example `localhost,127.0.0.1` |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | MySQL connection (`DB_HOST` is `db` inside Docker) |
| `RABBITMQ_USER`, `RABBITMQ_PASSWORD` | RabbitMQ login |

## 2. Start with Docker

Run all Docker commands from the `project_2` folder (the one that contains `docker-compose.yml`).

```bash
docker compose up -d --build
docker compose ps
```

All five services should be running: `mysql`, `rabbitmq`, `web` (healthy), `celery_worker` and `celery_beat`.
On startup the `web` service waits for MySQL, applies migrations, loads the seed data, collects static files
and starts Gunicorn. No manual steps are needed.

| What | Address |
| --- | --- |
| API root | http://localhost:8000/api/ |
| Swagger docs | http://localhost:8000/api/docs/ |
| Django Admin | http://localhost:8000/admin/ |
| Staff dashboard | http://localhost:8000/dashboard/ |
| RabbitMQ management UI | http://localhost:15672 (sign in with `RABBITMQ_USER` / `RABBITMQ_PASSWORD`) |
| MySQL from your machine | `localhost:3307` (for tools such as DBeaver) |

Stop everything with `docker compose down`. Add `-v` to also delete the database and queue volumes
(a full reset).

### Create the first Admin user

```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; u = get_user_model().objects.get(username='YOUR_USERNAME'); u.role = 'admin'; u.save()"
```

The second command gives the account the `admin` role, which the API checks. Without a role, API calls return 403.
Support Agents are created in the Django Admin with the `agent` role.

## 3. Seed data

Seeding runs automatically on startup and is safe to repeat (no duplicates). To run it by hand:

```bash
docker compose exec web python manage.py seed_data
```

It loads 4 packages (Home Basic R399, Home Standard R699, Home Premium R999, Business Fibre R1,499),
3 contract terms (Month-to-Month x1.15, 12-Month x1.00, 24-Month x0.90) and 3 add-ons
(Static IP R100, Router Rental R150, LTE Failover SIM R250).

## 4. Run the tests and lint

```bash
docker compose exec web pytest -v
docker compose exec web flake8 . --max-line-length 120 --exclude migrations
```

There are 120 automated tests covering authentication, CRUD, IDOR protection, pricing, status changes,
filtering, the Celery tasks, the dashboard, reports and the Swagger schema. They run on SQLite with Celery tasks
executed in-process, so no database server or broker is needed. The saved result is in
[`docs/test_output.txt`](docs/test_output.txt).

CI (GitHub Actions) runs the same flake8 and pytest commands on every push and pull request to `main`.

## 5. Swagger and authentication

1. Open http://localhost:8000/api/docs/
2. Run `POST /api/auth/token/` with your username and password and copy the `access` token.
3. Click **Authorize** and paste the token (Swagger adds the `Bearer` prefix for you if the scheme asks for
   a token only; otherwise enter `Bearer <token>`).
4. Try any endpoint. When the access token expires (60 minutes), use `POST /api/auth/token/refresh/`.

Every endpoint except the token routes and the docs requires a valid token. Missing or expired tokens return 401.

### Main endpoints

| Method | Endpoint | Who |
| --- | --- | --- |
| POST | `/api/auth/token/`, `/api/auth/token/refresh/` | Public |
| GET, POST | `/api/customers/` | Agent, Admin |
| GET, PUT, PATCH, DELETE | `/api/customers/{id}/` | Agent (own, no delete), Admin |
| GET | `/api/packages/`, `/api/packages/{id}/` | Agent, Admin |
| GET, POST | `/api/subscriptions/` | Agent, Admin |
| PATCH | `/api/subscriptions/{id}/status/` | Admin |
| GET | `/api/subscriptions/{id}/logs/` | Agent, Admin |
| GET | `/api/alerts/` | Agent, Admin |
| PATCH | `/api/alerts/{id}/acknowledge/` | Agent, Admin |
| GET | `/api/reports/revenue-summary/` | Admin |
| GET | `/api/reports/expiring/` | Agent, Admin |

## 6. Background tasks (Celery and RabbitMQ)

| Task | Schedule | What it does |
| --- | --- | --- |
| `alerts.tasks.check_expiring_subscriptions` | daily 07:00 | Creates one renewal alert for each Active subscription that ends within 7 days; never duplicates |
| `subscriptions.tasks.auto_suspend_overdue_subscriptions` | daily 07:15 | Suspends Active subscriptions more than 30 days past their end date and writes an audit log entry |

Watch the worker: `docker compose logs -f celery_worker`. Queues are visible in the RabbitMQ UI
(http://localhost:15672). To run a task by hand, open a shell with
`docker compose exec web python manage.py shell` and call `check_expiring_subscriptions.delay()`.

## 7. Documentation

- Sprint board: [`docs/sprint_board.md`](docs/sprint_board.md)
- ERD and indexes: [`docs/erd.md`](docs/erd.md)
- Architecture diagram: [`docs/architecture.md`](docs/architecture.md)
- Demo evidence: [`docs/demo/`](docs/demo/)

## 8. Troubleshooting

| Problem | Fix |
| --- | --- |
| `failed to connect to the docker API` | Start Docker Desktop and wait for "Engine running" |
| `service "web" is not running` | Run `docker compose up -d --build`, then `docker compose logs web` to see why it stopped |
| `entrypoint.sh: not found` | Windows line endings. Run `git add --renormalize .` and rebuild (`.gitattributes` forces LF for `.sh` files) |
| Migration or database errors after pulling changes | Full reset: `docker compose down -v`, then `docker compose up -d --build` |
| API returns 403 for a new superuser | Give the user the `admin` role (see section 2) |

## 9. Assumptions

- Staff-facing only: no customer portal, email or SMS, payments or invoices (BRD section 6.2).
- Renewal alerts are database records only; nothing is sent.
- A custom user model (`customers.User`) with a `role` field (`admin` or `agent`) is used instead of the
  default Django user, and role changes keep the matching permission group in sync.
- The project runs on Python 3.12, Django 6.1 and MySQL 8.4; the BRD lists Django 4.2 LTS, Python 3.11+ and
  MySQL 8.0. All tests pass on the newer versions.
- CI uses SQLite for the test database; Docker uses MySQL.
- A subscription is auto-suspended when its contract end date is more than 30 days in the past
  (31 days overdue is suspended, 30 is not).

## 10. Git workflow

Work is done on feature branches and merged to `main` through pull requests. The CI check
(`lint-and-test`) must pass before a pull request is merged.