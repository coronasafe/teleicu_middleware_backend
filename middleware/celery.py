from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "middleware.settings")

app = Celery("middleware")
app.config_from_object(settings, namespace="CELERY")


app.conf.enable_utc = False
app.conf.beat_schedule = {
    "run-retrieve-asset-config": {
        "task": "middleware.tasks.retrieve_asset_config",
        "schedule": 60.0,
    },
    "run-automated-daily-round": {
        "task": "middleware.tasks.automated_daily_rounds",
        "schedule": crontab(minute=0, hour="*"),
    },
    # "dump-observations-to-s3": {
    #     "task": "middleware.tasks.observations_s3_dump",
    #     "schedule": 30.0,
    # },
    "sotre-camera-statuses": {
        "task": "middleware.tasks.store_camera_statuses",
        "schedule": 60.0,
    },
}


app.autodiscover_tasks()
