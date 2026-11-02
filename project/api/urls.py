# Everything under /api/. Each app owns its routes in its own urls.py; this file only mounts them,
# plus the endpoints that do not belong to one app (login and docs).
#
# The dashboard is an HTML page, not part of the API, so it is mounted in project/urls.py.
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

# The docs must open without a login (so the Authorize button can be used) and must not use up the
# anonymous throttle, so these two views are public and unthrottled.
PUBLIC = {"permission_classes": [AllowAny], "authentication_classes": [], "throttle_classes": []}

urlpatterns = [
    path("", include("customers.urls")),             # /api/customers/               ISP-6
    path("", include("packages.urls")),              # /api/packages/                ISP-7
    path("", include("subscriptions.urls")),         # /api/subscriptions/...        ISP-9, ISP-13
    path("", include("alerts.urls")),                # /api/alerts/...               ISP-21
    path("reports/", include("reports.api_urls")),   # /api/reports/...              ISP-28, ISP-29
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),            # ISP-11
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),           # ISP-11
    path("schema/", SpectacularAPIView.as_view(**PUBLIC), name="schema"),                    # ISP-15
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema", **PUBLIC), name="docs"),
]