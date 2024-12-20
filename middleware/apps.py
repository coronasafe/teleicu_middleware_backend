from django.apps import AppConfig
from django.core.cache import cache


class MiddlewareConfig(AppConfig):
    name = "middleware"
    verbose_name = "Middleware"

    def ready(self):
        cache.clear()
