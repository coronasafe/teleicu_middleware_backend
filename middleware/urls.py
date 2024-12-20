"""
URL configuration for middleware project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import SimpleRouter

from middleware import consumers, views
from middleware.open_id import PublicJWKsView
from middleware.views import MiddlewareHealthViewSet, home

router = SimpleRouter(trailing_slash=False)
router.register(r"health", MiddlewareHealthViewSet, basename="health")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("", include(router.urls)),
    path(".well-known/openid-configuration/", PublicJWKsView.as_view()),
    path("", include("middleware.observation.urls")),
    path("", include("middleware.camera.urls")),
    path("", include("middleware.stream.urls")),
    path("verify_token/", views.verify_token),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]


websocket_urlpatterns = [
    path(r"logger", consumers.LoggerConsumer.as_asgi()),
    path(
        r"observations/<str:ip_address>",
        consumers.observations.as_asgi(),
    ),
]
