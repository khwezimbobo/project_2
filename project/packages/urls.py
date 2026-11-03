from rest_framework.routers import DefaultRouter
from .views import PackageViewSet

# The router creates both URLs from the ViewSet:
#   packages/        -> list
#   packages/<id>/   -> retrieve
router = DefaultRouter()
router.register("packages", PackageViewSet, basename="package")

urlpatterns = router.urls