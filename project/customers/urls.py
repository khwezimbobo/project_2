# Customers URLs (BRD s12: /api/customers/ and /api/customers/{id}/).
# api/urls.py mounts this file, so the routes end up under /api/.
# Login, token refresh and Swagger are mounted in api/urls.py, not here.
from rest_framework.routers import DefaultRouter

from .views import CustomerViewSet

# The router creates:
#   /customers/       GET (list), POST (create)
#   /customers/<id>/  GET, PUT, PATCH, DELETE
router = DefaultRouter()
router.register("customers", CustomerViewSet, basename="customer")

urlpatterns = router.urls
