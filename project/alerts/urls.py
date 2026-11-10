# api/urls.py
from rest_framework.routers import SimpleRouter
 
from .views import AlertViewSet
 
router = SimpleRouter()
router.register("alerts", AlertViewSet, basename="alert")  # ISP-21
 
urlpatterns = router.urls