import logging
from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

import requests
from celery import shared_task
from django.conf import settings

from middleware.camera.onvif_zeep_camera_controller import OnvifZeepCameraController
from middleware.camera.types import CameraAsset
from middleware.models import Asset, AssetClasses
from middleware.observation.types import (
    DailyRoundObservation,
    DataDumpRequest,
    DeviceID,
    MonitorOptions,
)
from middleware.observation.utils import (
    get_data_for_s3_dump,
    get_vitals_from_observations,
    make_data_dump_to_s3,
)
from middleware.redis_manager import redis_manager
from middleware.utils import _get_headers, file_automated_daily_rounds, get_patient_id

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

    logger.info("Fetched  Asset ids: %s", data)
    fetched_ids = [UUID(asset["id"]) for asset in data]
    existing_asset_ids = list(
        Asset.objects.filter(deleted=False).values_list("id", flat=True)
    )
    logger.info("Existing  Asset ids: %s", existing_asset_ids)

    missing_asset_ids = [
        asset_id for asset_id in existing_asset_ids if asset_id not in fetched_ids
    ]

    logger.info("Missing  Asset ids: %s", missing_asset_ids)

    # Mark missing assets as deleted
    deleted_count = Asset.objects.filter(id__in=missing_asset_ids).delete()

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
        if not vitals:
            logger.info(
                "Not filing Automated daily rounds for Monitor having id:%s  as vitals is : %s",
                monitor.id,
                vitals,
            )
            return
        file_automated_daily_rounds(
            consultation_id=consultation_id,
            asset_id=monitor.id,
            vitals=vitals.model_dump(mode="json", exclude_none=True),
        )


@shared_task
def observations_s3_dump():
    data = get_data_for_s3_dump()
    make_data_dump_to_s3(
        req=DataDumpRequest(
            data=data,
            key=f"{settings.HOST_NAME}/{datetime.now()}.json",
            monitor_options=MonitorOptions(
                slug="s3_observations_dump",
                options={
                    "schedule": {
                        "type": "crontab",
                        "value": "30 * * * *",
                    },
                },
            ),
        )
    )


@shared_task
def store_camera_statuses():
    cameras = Asset.objects.filter(type=AssetClasses.ONVIF.name, deleted=False)
    device_data: Dict[DeviceID, str] = {}
    for camera in cameras:
        cam_request = CameraAsset(
            hostname=str(camera.ip_address),
            port=int(camera.port),
            username=str(camera.username),
            password=str(camera.password),
        )
        cam = OnvifZeepCameraController(req=cam_request)
        response = cam.get_status()
        if response and response.get("error") == "NO error":
            device_data[camera.ip_address] = "up"
        else:
            device_data[camera.ip_address] = "down"

    redis_manager.push_to_redis(settings.CAMERA_STATUS_KEY, device_data)
