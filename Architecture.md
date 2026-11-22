# System Architecture: ISP Subscription Management Platform

Five Docker Compose containers behind one public port. Django serves the HTML pages and the REST API, MySQL stores the data, and Celery (with RabbitMQ) runs the scheduled work in the background.

## 1. System overview

```mermaid
flowchart LR
    subgraph clients["Clients"]
        agent["Support Agent<br/>API client or Swagger"]
        admin["Admin<br/>browser and API"]
    end

    subgraph compose["Docker Compose stack"]
        subgraph web["django container: Gunicorn + WhiteNoise, port 8000"]
            pages["HTML pages<br/>/admin/  /dashboard/  /accounts/"]
            api["REST API under /api/<br/>customers, packages, subscriptions,<br/>alerts, reports, auth/token"]
            docs["Swagger docs<br/>/api/docs/  /api/schema/"]
            guards["On every API request:<br/>JWT or session login, role rules,<br/>throttling, JSON error handler"]
            svc["Service layer<br/>pricing, status changes,<br/>raw SQL revenue report"]
        end
        mysql[("MySQL 8.4<br/>customers, packages, subscriptions,<br/>audit logs, renewal alerts, users")]
        rabbit["RabbitMQ<br/>queue: celery<br/>management UI on port 15672"]
        beat["celery_beat<br/>07:00 renewal alerts<br/>07:15 auto-suspend"]
        worker["celery_worker<br/>runs the two tasks"]
    end

    ci["GitHub Actions<br/>flake8 + pytest on SQLite"]

    admin -->|"session login"| pages
    admin -->|"JWT Bearer token"| api
    agent -->|"JWT Bearer token"| api
    agent --> docs
    pages --> svc
    api --> guards --> svc
    svc -->|"SQL"| mysql
    beat -->|"sends task messages"| rabbit
    rabbit -->|"delivers tasks"| worker
    worker -->|"creates alerts, suspends subscriptions,<br/>writes audit log"| mysql
    ci -.->|"runs on every push and pull request"| web
```

## 2. Login and an API request (JWT)

```mermaid
sequenceDiagram
    autonumber
    actor C as Client (agent or admin)
    participant A as Django API (Gunicorn)
    participant D as MySQL

    C->>A: POST /api/auth/token/ (username, password)
    A->>D: check the user and password
    A-->>C: access token (60 minutes) and refresh token (7 days)

    C->>A: GET /api/subscriptions/ with header Authorization: Bearer access-token
    A->>A: verify the token signature and expiry, load the user
    A->>A: throttle check (20 per hour anonymous, 1000 per day signed in)
    A->>D: query, limited to the agent's own customers (Admins see all)
    D-->>A: rows
    A-->>C: 200 with JSON

    Note over C,A: When the access token expires the API answers 401 "Token is expired"
    C->>A: POST /api/auth/token/refresh/ (refresh token)
    A-->>C: a new access token
```

## 3. Scheduled tasks and alerts

```mermaid
sequenceDiagram
    autonumber
    participant B as celery_beat
    participant R as RabbitMQ
    participant W as celery_worker
    participant D as MySQL
    actor U as Agent
    participant A as Django API

    B->>R: 07:00 send check_expiring_subscriptions
    R->>W: deliver the task
    W->>D: Active subscriptions ending within 7 days get one RenewalAlert each

    B->>R: 07:15 send auto_suspend_overdue_subscriptions
    R->>W: deliver the task
    W->>D: Active subscriptions over 30 days past their end date become Suspended, with an audit log entry by "System"

    U->>A: GET /api/alerts/ then PATCH /api/alerts/{id}/acknowledge/
    A->>D: read the alerts, then mark one Acknowledged
```

## 4. Components

| Container | Image | Port | Job |
| --- | --- | --- | --- |
| `django` | built from `project/Dockerfile` | 8000 | Gunicorn runs the Django app. On start it migrates, loads seed data on first run, and collects static files. |
| `mysql` | `mysql:8.4` | none (3307 in dev) | All application data, stored in the `mysql_data` volume. |
| `rabbitmq` | `rabbitmq:3-management` | 15672 (UI) | Message broker. The `celery` queue carries task messages. |
| `celery_worker` | same image as `django` | none | Runs `alerts.tasks.check_expiring_subscriptions` and `subscriptions.tasks.auto_suspend_overdue_subscriptions`. |
| `celery_beat` | same image as `django` | none | Sends those two tasks to RabbitMQ on the schedule in settings (South African time). |

## 5. How the code is organised

| Layer | Where | Responsibility |
| --- | --- | --- |
| Routing | `project/urls.py`, `api/urls.py`, each app's `urls.py` | Web pages at the root, the whole API under `/api/` |
| Cross-cutting | `api/` (exceptions, docs), settings | JWT and session login, throttling, one JSON error shape, Swagger |
| Apps | `customers`, `packages`, `subscriptions`, `alerts`, `reports` | Models, serializers, viewsets, permissions |
| Business rules | `subscriptions/services.py` | Pricing, contract dates, status changes and the audit log |
| Reporting | `reports/queries.py` | The one raw SQL query, parameterised |
| Background work | `alerts/tasks.py`, `subscriptions/tasks.py` | The two Celery tasks |

## 6. Design decisions worth knowing

- **One image, three roles.** The web server, worker and beat run the same image with different commands, so they always run the same code.
- **Role scoping at the query.** Agents only ever get rows for their own customers. Admins (role `admin` or superuser) see everything.
- **Prices are frozen on the subscription.** Later changes to package or add-on prices do not alter existing contracts.
- **Tokens are stateless.** Nothing about a login is stored on the server. The `SECRET_KEY` signs the tokens, so it stays in `.env` and out of Git.
- **Tasks write straight to the database.** Celery uses the same Django models, so alerts created by the worker are what the API reads later. No HTTP call is involved.
- **Production and development modes.** `docker-compose.yml` runs Gunicorn with no code mounted. `docker-compose.dev.yml` adds `runserver`, a mounted code folder and the MySQL port.
