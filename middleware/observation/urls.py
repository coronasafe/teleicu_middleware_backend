from django.urls import path

from middleware.observation import views

urlpatterns = [
    path("update_observations", views.update_observations),
    path("devices/status", views.device_statuses),
]
