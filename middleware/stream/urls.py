from django.urls import path, include
from rest_framework.routers import SimpleRouter

from middleware.stream.views import MiddlewareStreamViewSet


router = SimpleRouter(trailing_slash=False)
router.register(r"/api/stream", MiddlewareStreamViewSet, basename="stream")

urlpatterns = [
    path("", include(router.urls)),
]
