import logging

from django.contrib import messages
from django.contrib.auth import login, logout
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import lockout
from .forms import BootstrapAuthenticationForm, CustomerForm
from .models import Customer
from .permissions import agent_or_admin_required, customers_for, owns

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# HOME PAGE
# ----------------------------------------------------------------------
def home(request):
    # Public landing page, so no login required.
    return render(request, "customers/home.html")


# ----------------------------------------------------------------------
# HELPER: FETCH ONE CUSTOMER THE USER MAY ACCESS
# ----------------------------------------------------------------------
def _get_customer_or_403(request, pk):
    """
    Find a customer by id; refuse with 403 when it belongs to another agent.

    Matches the API: unknown ids give 404, other agents' records give 403.
    """
    customer = get_object_or_404(
        Customer.objects.select_related("assigned_agent"), pk=pk
    )

    if not owns(request.user, customer):
        logger.warning(
            "User id %s was blocked from customer page %s.", request.user.pk, customer.pk
        )
        raise PermissionDenied("You do not have access to this customer.")

    return customer


# ----------------------------------------------------------------------
# CUSTOMER LIST, DETAIL, CREATE AND EDIT PAGES
# ----------------------------------------------------------------------
@agent_or_admin_required
def customer_list(request):
    q = request.GET.get("q", "").strip()

    # Each user only receives the customers they are allowed to see.
    customers = customers_for(request.user).order_by("last_name", "first_name")

    # Search across name, email and phone.
    if q:
        customers = customers.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
            | Q(phone__icontains=q)
        )

    # 20 per page; get_page() handles bad page numbers safely.
    page_obj = Paginator(customers, 20).get_page(request.GET.get("page"))
    return render(
        request, "customers/customer_list.html", {"page_obj": page_obj, "q": q}
    )


@agent_or_admin_required
def customer_detail(request, pk):
    customer = _get_customer_or_403(request, pk)
    return render(request, "customers/customer_detail.html", {"customer": customer})


@agent_or_admin_required
def customer_create(request):
    # request.POST or None: an empty form on GET, a bound form on POST.
    form = CustomerForm(request.POST or None, user=request.user)

    if request.method == "POST" and form.is_valid():
        customer = form.save()
        logger.info("Customer %s created by user id %s (web).", customer.pk, request.user.pk)
        messages.success(request, "Customer created.")
        return redirect("customer_detail", pk=customer.pk)

    return render(
        request,
        "customers/customer_form.html",
        {"form": form, "heading": "Add customer"},
    )


@agent_or_admin_required
def customer_edit(request, pk):
    customer = _get_customer_or_403(request, pk)
    form = CustomerForm(request.POST or None, instance=customer, user=request.user)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Customer updated.")
        return redirect("customer_detail", pk=customer.pk)

    return render(
        request,
        "customers/customer_form.html",
        {"form": form, "heading": "Edit customer"},
    )


# ----------------------------------------------------------------------
# LOGIN AND LOGOUT
# ----------------------------------------------------------------------
def _safe_next_url(request):
    """Return the ?next= target only if it points at THIS site, else ''.

    @login_required sends users to /login/?next=/customers/ so they can
    land where they were going. Redirecting to an unchecked `next` is an
    "open redirect": an attacker could email a link like
    /login/?next=https://evil.com and send the user to a fake site right
    after a real login. url_has_allowed_host_and_scheme blocks that.
    """
    # The value comes from the hidden field (POST) or the URL (GET).
    candidate = request.POST.get("next") or request.GET.get("next") or ""
    is_safe = url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},   # only this site's own host
        require_https=request.is_secure(),    # keep https if we are on https
    )
    return candidate if candidate and is_safe else ""


def login_view(request):
    # Already logged in? There is nothing to do here, so skip the form.
    if request.user.is_authenticated:
        return redirect("customer_list")

    next_url = _safe_next_url(request)

    if request.method == "POST":
        username = request.POST.get("username", "")

        # Too many recent failures: refuse before checking the password.
        if lockout.is_locked(request, username):
            logger.warning("Web login refused (locked) for username '%s'.", username)
            form = BootstrapAuthenticationForm(request)
            form.add_error(None, lockout.lockout_message())
            return render(
                request,
                "customers/login.html",
                {"form": form, "next": next_url},
                status=429,
            )

        # AuthenticationForm checks the username and password (and that the
        # account is active) and builds the error message for you.
        form = BootstrapAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            # A good login wipes the failure counter.
            lockout.clear_failures(request, username)

            # login() creates the session and also changes the session key,
            # which protects against session fixation.
            login(request, form.get_user())
            logger.info("Web login succeeded for user id %s.", form.get_user().pk)
            return redirect(next_url or "customer_list")

        # Invalid credentials: count and log the failure, then show the form with errors.
        lockout.record_failure(request, username)
        logger.warning("Failed web login for username '%s'.", username)
    else:
        form = BootstrapAuthenticationForm(request)

    return render(request, "customers/login.html", {"form": form, "next": next_url})


@require_POST  # logging out changes state, so GET gets 405 (the nav uses a POST form)
def logout_view(request):
    # Ends the session and deletes its data on the server.
    logout(request)
    return render(request, "customers/logout.html")
