#!/bin/bash

# Run migrations
python manage.py migrate

# Start Celery worker
celery -A middleware.celery worker -B --loglevel=info
