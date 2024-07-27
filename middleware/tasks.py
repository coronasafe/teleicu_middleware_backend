from typing import Optional
from uuid import UUID
from celery import shared_task
import requests
from django.conf import settings
import logging

from middleware.models import Asset, AssetClasses
from middleware.observation.types import (
    DailyRoundObservation,
)

from middleware.observation.utils import get_vitals_from_observations
from middleware.utils import (
    _get_headers,
    file_automated_daily_rounds,
    get_patient_id,
)

logger = logging.getLogger(__name__)

@shared_task
def retrieve_asset_config():
    logger.info("Started Retrieving Assets Task")
    response = requests.get(
        f"{settings.CARE_URL}asset_config/?middleware_hostname={settings.HOST_NAME}",
        headers=_get_headers(),
    )

    response.raise_for_status()
    data = response.json()
    existing_asset_ids = list(
        Asset.objects.filter(deleted=False).values_list("id", flat=True)
    )
    logger.info("Existing  Asset ids: %s", existing_asset_ids)
    missing_asset_ids = [
        asset["id"] for asset in data if UUID(asset["id"]) not in existing_asset_ids
    ]

    logger.info("Missing  Asset ids: %s", missing_asset_ids)

    # Mark missing assets as deleted
    deleted_count = Asset.objects.filter(id__in=missing_asset_ids).update(deleted=True)

    logger.info("Deleted assets count: %s ", deleted_count)

    for asset in data:
        # Implement logic to create or update assets based on your model
        new_asset, _ = Asset.objects.update_or_create(
            id=str(asset["id"]), defaults=asset
        )


@shared_task
def automated_daily_rounds():
    logger.info("Started Automated daily rounds")
    monitors = Asset.objects.filter(type=AssetClasses.HL7MONITOR.name, deleted=False)
    logger.info("Found %s monitors", len(monitors))
    for monitor in monitors:
        logger.info("Processing Monitor having id: %s", monitor.id)
        consultation_id, patient_id, bed_id, asset_beds = get_patient_id(
            external_id=monitor.id
        )
        if not consultation_id or not patient_id or not bed_id:
            logger.error("Patient not found for the asset having id: %s", monitor.id)
            return

        vitals: Optional[DailyRoundObservation] = get_vitals_from_observations(
            ip_address=monitor.ip_address
        )
        logger.info("Vitals for Monitor having id:%s  is: %s", monitor.id, vitals)

        file_automated_daily_rounds(
            consultation_id=consultation_id, asset_id=monitor.id, vitals=vitals
        )
