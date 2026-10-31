# ======================================================================
# CUSTOMERS APP URL CONFIGURATION
# ======================================================================
# Every route for the customers app lives in this file:
#   1. HTML pages        (login, customers, dashboard)
#   2. Password reset    (Django's built-in views)
#   3. Health check      (Docker / monitoring)
#   4. REST API          (JWT login + customer CRUD)
#
# The project-level urls.py must include this file, for example:
#   path("", include("customers.urls"))
# ======================================================================

from django.contrib.auth import views as auth_views
from django.urls import include, path, reverse_lazy
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import api, dashboard, health, views


# ----------------------------------------------------------------------
# API ROUTER
# ----------------------------------------------------------------------
# A router builds all the API routes (GET, POST, PUT, PATCH, DELETE) for a
# ViewSet from one line.
router = DefaultRouter()
router.register("customers", api.CustomerViewSet, basename="customer")
# basename "customer" creates the URL names "customer-list" and
# "customer-detail". They use hyphens, so they do not clash with the HTML
# page names "customer_list" and "customer_detail" below.


urlpatterns = [

    # ==================================================================
    # 1. HTML PAGES (server-rendered with Django templates)
    # ==================================================================

    # Home page: public landing page. Shows a login button to visitors and
    # links to customers/dashboard for logged-in agents and admins.
    path("", views.home, name="home"),

    # Login: GET shows the form, POST checks the username and password.
    # After 5 failed attempts (per username + IP) the user is locked out for
    # 15 minutes and receives HTTP 429. Redirects to ?next= or the customer list.
    path("login/", views.login_view, name="login"),

    # Logout: POST only (a GET returns 405). Ends the session and shows the
    # "you have been logged out" page.
    path("logout/", views.logout_view, name="logout"),

    # Customer list: agents see only their own customers, admins see all.
    # Supports ?q= search (name, email, phone) and ?page= (20 per page).
    path("customers/", views.customer_list, name="customer_list"),

    # Add customer: GET shows an empty form, POST saves it. The new customer
    # is assigned to the logged-in agent. This route must stay ABOVE the
    # <uuid:pk> routes so "new" is never mistaken for an id.
    path("customers/new/", views.customer_create, name="customer_create"),

    # Customer detail: one customer. Unknown id gives 404, and another
    # agent's customer gives 403.
    path("customers/<uuid:pk>/", views.customer_detail, name="customer_detail"),

    # Edit customer: GET shows the form filled in, POST saves the changes.
    # Same 404 / 403 rules as the detail page.
    path("customers/<uuid:pk>/edit/", views.customer_edit, name="customer_edit"),


    # ==================================================================
    # 2. PASSWORD RESET (Django's built-in views with our Bootstrap templates)
    # ==================================================================
    # The flow has four steps, one URL each:
    #   request -> "email sent" -> link in the email -> "password changed"

    # Step 1: the user types their email address. If an account exists, a
    # reset email is sent. The same response is given either way, so
    # attackers cannot discover which emails are registered.
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="customers/password_reset_form.html",
            email_template_name="customers/password_reset_email.txt",
            subject_template_name="customers/password_reset_subject.txt",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),

    # Step 2: "check your email" confirmation page.
    path(
        "password-reset/sent/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="customers/password_reset_done.html"
        ),
        name="password_reset_done",
    ),

    # Step 3: the link from the email. uidb64 identifies the user and token
    # proves the link is genuine. A wrong, expired or used link shows the
    # "Link not valid" page instead of the new-password form.
    path(
        "password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="customers/password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),

    # Step 4: "password changed" confirmation with a link back to login.
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="customers/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),


    # ==================================================================
    # 3. STAFF DASHBOARD
    # ==================================================================

    # Dashboard: KPI cards (total, new this week, new today, active agents)
    # and the five newest customers. Requires login, staff access and the
    # Agent or Admin role; anyone else gets 403. Agents see only their own
    # numbers, admins see everything.
    path("dashboard/", dashboard.dashboard, name="dashboard"),


    # ==================================================================
    # 4. HEALTH CHECK (public; used by Docker and monitoring)
    # ==================================================================

    # Health check: no login needed. Returns 200 {"status": "ok"} when the
    # app and database respond, or 503 when the database is unreachable.
    path("health/", health.health, name="health"),


    # ==================================================================
    # 5. REST API: JWT LOGIN AND REFRESH
    # ==================================================================
    # API clients log in once, then send the access token on every request:
    #   Authorization: Bearer <access token>

    # API login: POST {"username": "...", "password": "..."} and receive an
    # "access" token (valid 15 minutes) and a "refresh" token (valid 1 day).
    # Wrong details give 401; too many failures give 429.
    path("api/auth/login/", api.LoginView.as_view(), name="api_login"),

    # Token refresh: POST {"refresh": "<refresh token>"} to get a new access
    # token without asking for the password again.
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="api_token_refresh"),


    # ==================================================================
    # 6. REST API: CUSTOMERS
    # ==================================================================
    # The router above generates every customers endpoint. All of them need
    # a valid token from an Agent or Admin (no token = 401, wrong role = 403).
    #
    #   GET    /api/customers/         List customers (20 per page).
    #                                  Extras: ?search=  ?ordering=  ?page_size=
    #                                  Filters: ?first_name= ?last_name= ?email=
    #                                  ?phone= ?agent= ?created_after= ?created_before=
    #   POST   /api/customers/         Create a customer. It is assigned to the
    #                                  logged-in user. Limited to 5 per minute
    #                                  (the 6th gets 429 with a Retry-After header).
    #   GET    /api/customers/<uuid>/  Read one customer.
    #   PUT    /api/customers/<uuid>/  Replace all fields.
    #   PATCH  /api/customers/<uuid>/  Change only the fields you send.
    #   DELETE /api/customers/<uuid>/  Delete a customer.
    #
    # Agents can only use their own customers (another agent's record gives
    # 403); admins can use all of them. Bad data (for example a phone number
    # with fewer than 10 digits or a duplicate email) gives 400 with a clear
    # error message.
    #
    # DefaultRouter also adds an API index page at /api/ that links to the
    # customers endpoint.
    path("api/", include(router.urls)),
]