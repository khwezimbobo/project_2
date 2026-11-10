# Everything under /api/. Each app owns its routes in its own urls.py; this file only mounts them,
# plus the endpoints that do not belong to one app (login and docs).
#
# The dashboard is an HTML page, not part of the API, so it is mounted in project/urls.py.
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.utils import extend_schema, extend_schema_view

# The docs must open without a login (so the Authorize button can be used) and must not use up the
# anonymous throttle, so these two views are public and unthrottled.
PUBLIC = {"permission_classes": [AllowAny], "authentication_classes": [], "throttle_classes": []}

# Swagger: put the two JWT endpoints in their own "Auth" section with clear summaries.
TokenObtainView = extend_schema_view(post=extend_schema(
    tags=["Auth"], summary="Log in: get an access and a refresh token",
    description="Public. Send username and password. Use the access token with the Authorize button."))(
    TokenObtainPairView)
TokenRefreshDocView = extend_schema_view(post=extend_schema(
    tags=["Auth"], summary="Get a new access token using the refresh token"))(TokenRefreshView)

urlpatterns = [
    path("", include("customers.urls")),             # /api/customers/               ISP-6
    path("", include("packages.urls")),              # /api/packages/                ISP-7
    path("", include("subscriptions.urls")),         # /api/subscriptions/...        ISP-9, ISP-13
    path("", include("alerts.urls")),                # /api/alerts/...               ISP-21
    path("reports/", include("reports.urls")),   # /api/reports/...              ISP-28, ISP-29
    path("auth/token/", TokenObtainView.as_view(), name="token_obtain_pair"),                # ISP-11
    path("auth/token/refresh/", TokenRefreshDocView.as_view(), name="token_refresh"),        # ISP-11
    path("schema/", SpectacularAPIView.as_view(**PUBLIC), name="schema"),                    # ISP-15
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema", **PUBLIC), name="docs"),
]