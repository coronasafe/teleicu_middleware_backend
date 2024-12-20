import base64
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, TypeVar
from uuid import UUID

import pytz
import requests
from authlib.jose import JsonWebKey, jwt
from django.conf import settings
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)


def generate_jwt(claims=None, exp=60, jwks=None):
    if claims is None:
        claims = {}
    if jwks is None:
        jwks = settings.JWKS
    header = {"alg": "RS256"}
    time = int(datetime.now().timestamp())
    payload = {
        "iat": time,
        "exp": time + exp,
        **claims,
    }
    return jwt.encode(header, payload, jwks).decode("utf-8")


def generate_encoded_jwks():
    key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    key = key.as_dict(key.dumps_private_key(), alg="RS256")

    keys = {"keys": [key]}
    keys_json = json.dumps(keys)
    return base64.b64encode(keys_json.encode()).decode()


def _get_headers(claims: dict = None) -> dict:
    return {
        "Authorization": "Middleware_Bearer " + generate_jwt(claims=claims),
        "Content-Type": "application/json",
        "X-Facility-Id": settings.FACILITY_ID,
    }


def group_by(data: List[T], key: str) -> Dict[Any, List[T]]:
    grouped_data: Dict[Any, List[T]] = {}
    for item in data:
        group_key = getattr(item, key)
        if group_key in grouped_data:
            grouped_data[group_key].append(item)
        else:
            grouped_data[group_key] = [item]
    return grouped_data


def get_patient_id(external_id: UUID):
    response = requests.get(
        f"{settings.CARE_URL}consultation/patient_from_asset/?preset_name=monitor",
        headers=_get_headers(claims={"asset_id": str(external_id)}),
    )
    response.raise_for_status()
    data = response.json()
    return (
        data.get("consultation_id"),
        data.get("patient_id"),
        data.get("bed_id"),
        data.get("asset_beds"),
    )


def file_automated_daily_rounds(consultation_id: UUID, asset_id: UUID, vitals: dict):
    response = requests.post(
        f"{settings.CARE_URL}consultation/{consultation_id}/daily_rounds/",
        json=vitals,
        headers=_get_headers(claims={"asset_id": str(asset_id)}),
    )

    if response.status_code != 201:
        logger.error(
            "Failed to file the daily round for the consultation: %s and asset:%s",
            consultation_id,
            asset_id,
        )
        return
    response.raise_for_status()
    logger.info(
        "Successfully filed automated daily rounds for Monitor having id:%s  as vitals is : %s",
        asset_id,
        vitals,
    )


def get_current_truncated_utc_z():
    current_time = datetime.now(pytz.UTC)
    truncated_time = current_time.replace(second=0, microsecond=0)
    return truncated_time.strftime("%Y-%m-%dT%H:%M:00.000Z")
