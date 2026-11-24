# Sprint Board

ISP Subscription Management Platform (Project 2), Backspace Technologies. Team: Cassidy Bekker, Siseko Mtebele, Khwezilomso Mbobo.

Six one-week sprints from 19 October to 25 November 2026. The live board was kept in Jira (project ISP_PROJECT_2); this file is the written copy required by BRD section 17, with the final status of every story. Each story lists its acceptance criteria, story points (Fibonacci) and the BRD section it covers.

## Definition of Done

A story is Done when all of these are true:

1. The acceptance criteria are met.
2. Tests are written and pass (`pytest`), and flake8 passes (`--max-line-length 120`).
3. The code was reviewed and merged to `main` through a pull request.
4. Swagger at `/api/docs/` is updated for any new or changed endpoint.
5. It works in the Docker stack (`docker compose up`).
6. Any change to a model is reflected in `docs/erd.md`.

## Epics

| Epic | Name | Scope |
|------|------|-------|
| E1 | Project Setup & Data Model | Repo, Django skeleton, models, migrations, seed data, Django Admin. (Module 2) |
| E2 | Customers & Security | Customer API, JWT, roles, IDOR prevention, throttling, error handling. (Modules 3, 6) |
| E3 | Subscriptions & Pricing | Packages API, PricingService, subscriptions, status transitions, audit log, Swagger. (Module 3) |
| E4 | Async Processing | Celery, RabbitMQ, renewal alerts, auto-suspension, beat schedule. (Module 8) |
| E5 | Reports & Dashboard | Raw SQL revenue report, expiring report, MTV dashboard. (Modules 2, 4) |
| E6 | DevOps | Docker Compose (5 services), Gunicorn, GitHub Actions CI. (Module 7) |
| E7 | Documentation & Submission | ERD, architecture diagram, README, sprint board, demo evidence. (Module 5) |

## Summary

| Sprint | Focus | Stories | Points |
|--------|-------|---------|--------|
| Week 1 | Setup, data model, Docker (MySQL, RabbitMQ) | 9 | 21 | ✅ Done |
| Week 2 | Customer, package and subscription APIs, pricing, Celery set-up | 6 | 23 | ✅ Done |
| Week 3 | JWT, roles and IDOR, status changes, filters, Swagger, alert task | 7 | 26 | ✅ Done |
| Week 4 | Auto-suspend, beat schedule, alerts API, dashboard, tests | 6 | 20 | ✅ Done |
| Week 5 | Gunicorn stack, CI, reports, task tests | 5 | 16 | ✅ Done |
| Week 6 | ERD, architecture, README, demo, cross-testing | 5 | 11 |
| **Total** | | **38** | **117** |

Status on 23 November 2026: 30 of 38 stories Done (94 of 117 points).

## Sprint 1 (Week 1)

| ID | Story | Epic | Owner | Points | Status |
|----|-------|------|-------|--------|--------|
| ISP-1 | Create repo and Django project skeleton | Project Setup & Data Model | Siseko | 3 | ✅ Done |
| ISP-2 | Agree data model and record decisions in docs/erd.md | Project Setup & Data Model | Cassidy | 2 | ✅ Done |
| ISP-3 | Customer model, migration and admin | Project Setup & Data Model | Siseko | 2 | ✅ Done |
| ISP-4 | Package, ContractTerm and AddOn models with seed command | Project Setup & Data Model | Cassidy | 3 | ✅ Done |
| ISP-5 | Subscription, SubscriptionAddOn and audit log models | Project Setup & Data Model | Cassidy | 3 | ✅ Done |
| ISP-6 | RenewalAlert model | Project Setup & Data Model | Khwezi | 1 | ✅ Done |
| ISP-7 | Docker Compose for MySQL and RabbitMQ | DevOps | Khwezi | 3 | ✅ Done |
| ISP-8 | Django Admin customisation | Project Setup & Data Model | Cassidy | 2 | ✅ Done |
| ISP-9 | Basic MTV dashboard page | Reports & Dashboard | Cassidy | 2 | ✅ Done |

### ISP-1: Create repo and Django project skeleton

*As a developer, I want a shared repo with the agreed Django structure so that the team can work in parallel.*

**Owner:** Siseko | **Points:** 3 | **Status:** ✅ Done | **BRD:** BRD 11.2

**Acceptance criteria**

- Repo created; main branch protected (PR + 1 approval to merge)
- Django 4.2 project `config/` with apps customers, packages, subscriptions, alerts, reports under `apps/`
- Settings split: base, development, test (SQLite), production
- requirements.txt pinned; .env.example committed; .env in .gitignore
- Every teammate can clone and run `python manage.py check` with no errors

**Notes:** As built: the config package is named `project/` (settings split into base/development/test, root URLs, Celery app) and the apps sit at the top level of `project/`.

### ISP-2: Agree data model and record decisions in docs/erd.md

*As the team, we want one agreed data model so that nobody changes a model and breaks another app.*

**Owner:** Cassidy | **Points:** 2 | **Status:** ✅ Done | **BRD:** BRD 13, 13.1

**Acceptance criteria**

- All 8 tables from BRD section 13 agreed, with field types and relationships
- Gap decisions (discounts, alert uniqueness, table names, dates) written in docs/erd.md
- Mermaid ERD committed

### ISP-3: Customer model, migration and admin

*As an admin, I want customer records stored in MySQL so that staff can manage subscribers.*

**Owner:** Siseko | **Points:** 2 | **Status:** ✅ Done | **BRD:** BRD 13, FR-02

**Acceptance criteria**

- Customer model per docs/erd.md (UUID PK, assigned_agent FK, unique email)
- Migration applies cleanly on MySQL 8
- Customer registered in Django Admin with search on name, email and phone

**Notes:** As built: custom `customers.User` with a `role` field (admin/agent); customer has first_name/last_name.

### ISP-4: Package, ContractTerm and AddOn models with seed command

*As an admin, I want the package catalogue loaded automatically so that pricing always uses the official rates.*

**Owner:** Cassidy | **Points:** 3 | **Status:** ✅ Done | **BRD:** BRD 8.1, 19

**Acceptance criteria**

- Package, ContractTerm, AddOn models + migrations
- `python manage.py seed_catalogue` loads 4 packages, 3 terms, 3 add-ons with BRD rates
- Seed command is idempotent (running twice creates no duplicates)

**Notes:** As built: the command is `python manage.py seed_data`.

### ISP-5: Subscription, SubscriptionAddOn and audit log models

*As a developer, I want the subscription tables in place so that the pricing and status work can build on them.*

**Owner:** Cassidy | **Points:** 3 | **Status:** ✅ Done | **BRD:** BRD 13, 13.1

**Acceptance criteria**

- Subscription, SubscriptionAddOn, SubscriptionAuditLog models per docs/erd.md
- SubscriptionStatus TextChoices defined once and imported elsewhere
- Indexes on status, contract_end_date and (status, contract_end_date)

### ISP-6: RenewalAlert model

*As a developer, I want the alert table in place so that the Celery task has somewhere to write alerts.*

**Owner:** Khwezi | **Points:** 1 | **Status:** ✅ Done | **BRD:** BRD 13

**Acceptance criteria**

- RenewalAlert model with unique (subscription, contract_end_date)
- Index on status; migration applies cleanly

**Notes:** As built: one alert per subscription (`OneToOneField`), matching the BRD's UNIQUE subscription_id.

### ISP-7: Docker Compose for MySQL and RabbitMQ

*As a developer, I want MySQL and RabbitMQ running with one command so that all three of us use the same setup.*

**Owner:** Khwezi | **Points:** 3 | **Status:** ✅ Done | **BRD:** BRD 16.1

**Acceptance criteria**

- docker-compose.yml with db (mysql:8.0, named volume) and rabbitmq (3-management)
- Credentials read from .env
- RabbitMQ UI reachable on :15672; Django connects to MySQL on all 3 laptops

### ISP-8: Django Admin customisation

*As an admin, I want a usable Admin panel so that I can manage packages, add-ons, terms and users.*

**Owner:** Cassidy | **Points:** 2 | **Status:** ✅ Done | **BRD:** FR-02

**Acceptance criteria**

- Packages, terms, add-ons, subscriptions registered with list_display, filters and search
- Subscription admin shows pricing fields read-only and add-ons inline
- Admin can create staff users and put them in Admin / Support Agent groups

### ISP-9: Basic MTV dashboard page

*As an operations manager, I want a /dashboard/ page so that I have a browser view of the system.*

**Owner:** Cassidy | **Points:** 2 | **Status:** ✅ Done | **BRD:** BRD 20 (Week 1)

**Acceptance criteria**

- base.html + index.html using Bootstrap 5 CDN
- /dashboard/ requires a logged-in staff session
- Placeholder KPI cards render

**Notes:** Reassigned from Siseko to Cassidy (frontend taken over).

## Sprint 2 (Week 2)

| ID | Story | Epic | Owner | Points | Status |
|----|-------|------|-------|--------|--------|
| ISP-10 | Customer CRUD API with search, filter and pagination | Customers & Security | Siseko | 5 | ✅ Done |
| ISP-11 | Packages read-only API | Subscriptions & Pricing | Cassidy | 2 | ✅ Done |
| ISP-12 | PricingService with discount rules | Subscriptions & Pricing | Cassidy | 5 | ✅ Done |
| ISP-13 | Create subscription endpoint with server-side pricing and dates | Subscriptions & Pricing | Cassidy | 5 | ✅ Done |
| ISP-14 | Configure the Celery app with RabbitMQ | Async Processing | Khwezi | 3 | ✅ Done |
| ISP-15 | Add web service to Docker Compose | DevOps | Khwezi | 3 | ✅ Done |

### ISP-10: Customer CRUD API with search, filter and pagination

*As a support agent, I want to create and search customers through the API so that I can capture new subscribers.*

**Owner:** Siseko | **Points:** 5 | **Status:** ✅ Done | **BRD:** FR-03, FR-04, BRD 18

**Acceptance criteria**

- GET/POST /api/customers/ and GET/PUT/PATCH /api/customers/{id}/ via ViewSet + Router
- Search by name/email/phone; ordering supported; 20 per page
- Phone needs at least 10 digits and email must be valid; otherwise 400 with a clear message
- assigned_agent defaults to the requesting user

### ISP-11: Packages read-only API

*As an agent, I want to list packages with their terms and add-ons so that I can quote a customer.*

**Owner:** Cassidy | **Points:** 2 | **Status:** ✅ Done | **BRD:** BRD 12

**Acceptance criteria**

- GET /api/packages/ and /api/packages/{id}/ return active packages only
- Detail includes available contract terms and add-ons
- POST/PUT/DELETE return 405

### ISP-12: PricingService with discount rules

*As the business, I want prices calculated by one service so that every subscription is priced the same way.*

**Owner:** Cassidy | **Points:** 5 | **Status:** ✅ Done | **BRD:** BRD 8.1, NFR Maintainability

**Acceptance criteria**

- apps/subscriptions/services.py: calculate_pricing() returns full breakdown using Decimal
- Applies multiplier, add-on total, highest eligible discount only (no stacking), R500 fee
- Unit tests cover the worked example in docs/erd.md and each discount type

### ISP-13: Create subscription endpoint with server-side pricing and dates

*As an agent, I want to create a subscription and get the price back so that I can confirm it with the customer.*

**Owner:** Cassidy | **Points:** 5 | **Status:** ✅ Done | **BRD:** FR-05, FR-06, FR-07, TC-02

**Acceptance criteria**

- POST /api/subscriptions/ accepts customer, package, contract_term, add_ons, installation_date
- Any pricing fields or dates sent by the client are ignored
- contract_start_date = installation_date; contract_end_date = start + duration_days
- Returns 201 with full pricing breakdown; creation audit log entry written

### ISP-14: Configure the Celery app with RabbitMQ

*As a developer, I want Celery connected to RabbitMQ so that background tasks can run outside the request cycle.*

**Owner:** Khwezi | **Points:** 3 | **Status:** ✅ Done | **BRD:** BRD 14, Module 8

**Acceptance criteria**

- config/celery.py with autodiscover_tasks; broker URL from .env
- A test task runs in a local worker and shows up in the RabbitMQ UI
- CELERY_TASK_ALWAYS_EAGER enabled in test settings

### ISP-15: Add web service to Docker Compose

*As a developer, I want Django running in Docker so that nobody needs MySQL client libraries installed locally.*

**Owner:** Khwezi | **Points:** 3 | **Status:** ✅ Done | **BRD:** BRD 16.1

**Acceptance criteria**

- Dockerfile (python:3.11-slim) builds the app
- web service on :8000 depends on db (with healthcheck) and rabbitmq
- `docker compose up` then migrate + seed works from a fresh clone

## Sprint 3 (Week 3)

| ID | Story | Epic | Owner | Points | Status |
|----|-------|------|-------|--------|--------|
| ISP-16 | JWT authentication | Customers & Security | Siseko | 3 | ✅ Done |
| ISP-17 | Role-based permissions and IDOR prevention | Customers & Security | Siseko | 5 | ✅ Done |
| ISP-18 | Throttling, custom exception handler and secrets | Customers & Security | Siseko | 3 | ✅ Done |
| ISP-19 | Subscription status changes with audit log | Subscriptions & Pricing | Cassidy | 5 | ✅ Done |
| ISP-20 | Subscription list filters and audit log endpoint | Subscriptions & Pricing | Cassidy | 3 | ✅ Done |
| ISP-21 | Swagger documentation | Subscriptions & Pricing | Cassidy | 2 | ✅ Done |
| ISP-22 | check_expiring_subscriptions task | Async Processing | Khwezi | 5 | ✅ Done |

### ISP-16: JWT authentication

*As a staff member, I want to log in and receive a token so that I can use the API securely.*

**Owner:** Siseko | **Points:** 3 | **Status:** ✅ Done | **BRD:** FR-01, FR-16, TC-01, TC-05

**Acceptance criteria**

- POST /api/auth/token/ and /api/auth/token/refresh/ via simplejwt
- Access 60 min, refresh 7 days
- IsAuthenticated is the default permission; missing, invalid or expired token returns 401

### ISP-17: Role-based permissions and IDOR prevention

*As an admin, I want agents to see only their own customers so that customer data stays private.*

**Owner:** Siseko | **Points:** 5 | **Status:** ✅ Done | **BRD:** BRD 8.2, 15, TC-04

**Acceptance criteria**

- Admin and Support Agent groups; custom permission classes
- get_queryset() filters customers and subscriptions by assigned_agent for agents; admins see all
- Agent requesting another agent's customer returns 403
- Agents cannot delete; status PATCH is admin-only

**Notes:** As built: Admin = role admin or superuser (`user.can_view_all`); agents get 403 (customers, alerts) or 404 (subscriptions) for another agent's record.

### ISP-18: Throttling, custom exception handler and secrets

*As the business, I want safe error handling so that the API never leaks internals.*

**Owner:** Siseko | **Points:** 3 | **Status:** ✅ Done | **BRD:** BRD 15, 18

**Acceptance criteria**

- AnonRateThrottle 20/hour, UserRateThrottle 1000/day
- Custom exception handler returns consistent JSON; IntegrityError becomes 400, not 500
- DEBUG=False in production settings; no secrets in Git

### ISP-19: Subscription status changes with audit log

*As an admin, I want to change a subscription's status so that I can activate, suspend or cancel service.*

**Owner:** Cassidy | **Points:** 5 | **Status:** ✅ Done | **BRD:** FR-08, FR-09, BRD 18, TC-03

**Acceptance criteria**

- PATCH /api/subscriptions/{id}/status/ (admin only)
- Allowed transitions enforced per docs/erd.md; Cancelled is final
- Invalid transition returns 400 with a descriptive message
- Every change writes an audit log entry (old, new, changed_by, notes)

### ISP-20: Subscription list filters and audit log endpoint

*As an agent, I want to filter subscriptions and see their history so that I can answer customer queries.*

**Owner:** Cassidy | **Points:** 3 | **Status:** ✅ Done | **BRD:** FR-15, TC-08

**Acceptance criteria**

- GET /api/subscriptions/?status=&package=&contract_term= via django-filter, 20 per page
- Invalid filter values return 400
- GET /api/subscriptions/{id}/logs/ returns the audit history

### ISP-21: Swagger documentation

*As a developer, I want auto-generated API docs so that endpoints are easy to test and assess.*

**Owner:** Cassidy | **Points:** 2 | **Status:** ✅ Done | **BRD:** FR-17

**Acceptance criteria**

- drf-spectacular installed; Swagger UI at /api/docs/
- JWT bearer auth works from the Swagger 'Authorize' button
- All endpoints have descriptions and example requests

### ISP-22: check_expiring_subscriptions task

*As an agent, I want alerts for contracts ending soon so that I can contact customers before they lapse.*

**Owner:** Khwezi | **Points:** 5 | **Status:** ✅ Done | **BRD:** FR-10, BRD 14.1, TC-06

**Acceptance criteria**

- alerts.tasks.check_expiring_subscriptions finds Active subs with end date within 7 days
- Creates one RenewalAlert per subscription per cycle; a second run creates no duplicates
- Logs count at INFO; exceptions logged at ERROR

## Sprint 4 (Week 4)

| ID | Story | Epic | Owner | Points | Status |
|----|-------|------|-------|--------|--------|
| ISP-23 | auto_suspend_overdue_subscriptions task | Async Processing | Khwezi | 5 | ✅ Done |
| ISP-24 | Celery beat schedule plus worker and beat services | Async Processing | Khwezi | 3 | ✅ Done |
| ISP-25 | Alerts list and acknowledge endpoint | Async Processing | Khwezi | 3 | ✅ Done |
| ISP-26 | Dashboard KPIs | Reports & Dashboard | Cassidy | 3 | ✅ Done |
| ISP-27 | Auth, customer and IDOR tests | Customers & Security | Siseko | 3 | ✅ Done |
| ISP-28 | Pricing and subscription tests | Subscriptions & Pricing | Cassidy | 3 | ✅ Done |

### ISP-23: auto_suspend_overdue_subscriptions task

*As the business, I want overdue contracts suspended automatically so that service stops after the grace period.*

**Owner:** Khwezi | **Points:** 5 | **Status:** ✅ Done | **BRD:** FR-11, BRD 14.2, TC-07

**Acceptance criteria**

- Active subs with end date more than 30 days ago are set to Suspended
- Audit log entry: Active to Suspended, changed_by null, note 'Auto-suspended: contract expired beyond grace period'
- Each record processed in try/except; failures logged individually and the task continues

**Notes:** Built with the 30-day grace period from BRD 14.2 (verified 18 Nov).

### ISP-24: Celery beat schedule plus worker and beat services

*As operations, I want tasks to run every day on their own so that nobody has to trigger them by hand.*

**Owner:** Khwezi | **Points:** 3 | **Status:** ✅ Done | **BRD:** BRD 14, 16.1

**Acceptance criteria**

- CELERY_BEAT_SCHEDULE: alerts at 07:00, suspension at 07:15 (Africa/Johannesburg)
- celery_worker and celery_beat services in docker-compose
- Task runs visible in worker logs and the RabbitMQ UI

### ISP-25: Alerts list and acknowledge endpoint

*As an agent, I want to acknowledge alerts so that the team knows a customer was contacted.*

**Owner:** Khwezi | **Points:** 3 | **Status:** ✅ Done | **BRD:** FR-12

**Acceptance criteria**

- GET /api/alerts/?status= (agents see alerts for own customers only)
- PATCH /api/alerts/{id}/acknowledge/ sets status, acknowledged_by and acknowledged_at
- Acknowledging an already-acknowledged alert returns 400

### ISP-26: Dashboard KPIs

*As an operations manager, I want key numbers at a glance so that I can see how the business is doing.*

**Owner:** Cassidy | **Points:** 3 | **Status:** ✅ Done | **BRD:** FR-13

**Acceptance criteria**

- /dashboard/ shows active subscriber count, total monthly revenue
- Table of subscriptions expiring in the next 30 days
- Pending renewal alerts listed

**Notes:** Pending alerts shown as a count (BRD FR-13 requires subscribers, revenue and the expiring list). Dashboard view lives in `reports/`, templates in `templates/dashboard/` (BRD 6.1, 11.2).

### ISP-27: Auth, customer and IDOR tests

*As the team, we want automated tests on security so that regressions are caught by CI.*

**Owner:** Siseko | **Points:** 3 | **Status:** ✅ Done | **BRD:** BRD 25

**Acceptance criteria**

- Tests: valid login (TC-01), no token gives 401 (TC-05), agent gets 403 on another agent's customer (TC-04)
- Invalid phone/email returns 400
- All pass with `pytest`

### ISP-28: Pricing and subscription tests

*As the team, we want tests on pricing and status rules so that business rules can't silently break.*

**Owner:** Cassidy | **Points:** 3 | **Status:** ✅ Done | **BRD:** BRD 25

**Acceptance criteria**

- Tests: create with server-side pricing (TC-02), invalid transition (TC-03), filters + pagination (TC-08)
- Client-sent pricing is ignored
- All pass with `pytest`

## Sprint 5 (Week 5)

| ID | Story | Epic | Owner | Points | Status |
|----|-------|------|-------|--------|--------|
| ISP-29 | Full five-service stack with Gunicorn | DevOps | Khwezi | 5 | ✅ Done |
| ISP-30 | GitHub Actions CI pipeline | DevOps | Siseko | 3 | ✅ Done |
| ISP-31 | Revenue summary report (raw SQL) | Reports & Dashboard | Khwezi | 3 | ✅ Done |
| ISP-32 | Expiring subscriptions report | Reports & Dashboard | Khwezi | 2 | ✅ Done |
| ISP-33 | Celery task and report tests | Async Processing | Khwezi | 3 | ✅ Done |

### ISP-29: Full five-service stack with Gunicorn

*As an assessor, I want the whole system to start with one command so that I can run the demo.*

**Owner:** Khwezi | **Points:** 5 | **Status:** ✅ Done | **BRD:** BRD 16.1, BRD 21

**Acceptance criteria**

- web runs Gunicorn (not runserver)
- db, rabbitmq, web, celery_worker, celery_beat all start cleanly with `docker compose up`
- Migrations + seed run on startup; API reachable at http://localhost:8000/api/
- pytest runs inside the web container

### ISP-30: GitHub Actions CI pipeline

*As the team, we want every push and PR checked so that broken code can't reach main.*

**Owner:** Siseko | **Points:** 3 | ✅ Done | **BRD:** BRD 16.2, TC-10

**Acceptance criteria**

- .github/workflows/ci.yml on push and PR to main
- Steps: checkout v4, Python 3.11, install, flake8 (max 120, exclude migrations), pytest --ds=config.settings.test
- Branch protection requires CI to pass; pipeline green

### ISP-31: Revenue summary report (raw SQL)

*As an admin, I want revenue by package so that I can see which products earn the most.*

**Owner:** Khwezi | **Points:** 3 | **Status:** ✅ Done | **BRD:** FR-14, BRD 15, TC-09

**Acceptance criteria**

- GET /api/reports/revenue-summary/ (admin only)
- Uses connection.cursor().execute() with %s placeholders in apps/reports/queries.py
- Returns active monthly revenue grouped by package name

### ISP-32: Expiring subscriptions report

*As an agent, I want a list of contracts ending in 30 days so that I can plan renewal calls.*

**Owner:** Khwezi | **Points:** 2 | **Status:** ✅ Done | **BRD:** BRD 12

**Acceptance criteria**

- GET /api/reports/expiring/ returns Active subs ending within 30 days
- Agents see only their own customers' subscriptions
- Paginated, ordered by contract_end_date

**Notes:** Built by Khwezi in the reports app; agents see only their own customers.

### ISP-33: Celery task and report tests

*As the team, we want the async logic tested without a broker so that CI can run it.*

**Owner:** Khwezi | **Points:** 3 | ✅ Done | **BRD:** BRD 25, NFR Testability

**Acceptance criteria**

- TC-06: alert created, second run creates no duplicate
- TC-07: 35-days-overdue sub suspended + audit log entry
- TC-09: revenue summary totals correct; tasks called directly (no broker)

## Sprint 6 (Week 6)

| ID | Story | Epic | Owner | Points | Status |
|----|-------|------|-------|--------|--------|
| ISP-34 | Final ERD and indexing documentation | Documentation & Submission | Cassidy | 2 | ✅ Done |
| ISP-35 | Architecture diagram | Documentation & Submission | Cassidy | 2 | ✅ Done |
| ISP-36 | README and final sprint board | Documentation & Submission | Siseko | 2 | ✅ Done ||
| ISP-37 | Demo evidence | Documentation & Submission | Cassidy | 3 | ✅ Done |
| ISP-38 | Cross-testing and bug fixes | Documentation & Submission | Khwezi | 2 | 🟡 In Progress |

### ISP-34: Final ERD and indexing documentation

*As an assessor, I want an accurate ERD so that I can review the database design.*

**Owner:** Cassidy | **Points:** 2 | **Status:** ✅ Done | **BRD:** BRD 17, Module 4

**Acceptance criteria**

- docs/erd.md (or erd.png) matches the final models
- Indexing strategy explained, including the composite index

### ISP-35: Architecture diagram

*As an assessor, I want to see how the parts connect so that I understand the system flow.*

**Owner:** Cassidy | **Points:** 2 | **Status:** ✅ Done | **BRD:** BRD 17

**Acceptance criteria**

- docs/architecture.md (or .png): client to Gunicorn/Django to MySQL; beat to RabbitMQ to worker to MySQL
- All 5 Docker services shown

**Notes:** Reassigned from Khwezi to Cassidy. `docs/architecture.md` and `docs/architecture.png`.

### ISP-36: README and final sprint board

*As a new developer, I want clear setup steps so that I can run the project in minutes.*

**Owner:** Siseko | **Points:** 2 | **Status:** 🟡 In Progress | **BRD:** BRD 17

**Acceptance criteria**

- README: description, .env setup, docker compose steps, seeding, running tests, Swagger link, sprint board link
- docs/sprint_board.md updated with final status of every story

### ISP-37: Demo evidence

*As an assessor, I want a recorded walkthrough so that I can see the system working end to end.*

**Owner:** Cassidy | **Points:** 3 | ✅ Done | **BRD:** BRD 19

**Acceptance criteria**

- Recording or screenshots: login, create subscription, pricing breakdown, dashboard, Celery task triggered, sub auto-suspended
- Saved in docs/demo/ or linked from the README

### ISP-38: Cross-testing and bug fixes

*As the team, we want each member to test someone else's area so that we find bugs before the assessor does.*

**Owner:** Khwezi | **Points:** 2 | **Status:** 🟡 In Progress | **BRD:** BRD 21

**Acceptance criteria**

- Each member runs through another member's endpoints from a fresh clone
- All bugs found are logged and fixed or documented
- Final commit: CI green, 8+ tests passing in Docker
