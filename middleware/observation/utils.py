import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from django.conf import settings
from django.core.cache import cache
from django.utils.timezone import make_aware, now
from sentry_sdk.crons import capture_checkin
from sentry_sdk.crons.consts import MonitorStatus

from middleware.observation.types import (
    DailyRoundObservation,
    DataDumpRequest,
    DeviceID,
    Observation,
    ObservationID,
    StaticObservation,
    Status,
)

logger = logging.getLogger(__name__)

messages = {
    "Leads Off": {
        "description": "ECG leads disconnected",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Asystole": {
        "description": "Arrhythmia - Asystole",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Missed Beat": {
        "description": "Arrhythmia – Missed beat",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Tachy Cardia": {
        "description": "Arrhythmia - Tachycardia",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Brady Cardia": {
        "description": "Arrhythmia – Brady cardia",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "VFIB": {
        "description": "Arrhythmia - Ventricular Fibrillation",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "VTAC": {
        "description": "Arrhythmia - Ventricular Tachycardia",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "R ON T": {
        "description": "Arrhythmia – R on T",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "COUPLET": {
        "description": "Arrhythmia – PVC couplet",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "BIGEMINY": {
        "description": "Arrhythmia - Bigeminy",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "TRIGEMINY": {
        "description": "Arrhythmia - Trigeminy",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "PNC": {
        "description": "Arrhythmia - Premature Nodal contraction",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "PNP": {
        "description": "Arrhythmia - Pace not pacing",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "ARRHYTHMIA": {
        "description": "Arrhythmia present, couldn’t detect the specific arrhythmia",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Run of PVCs": {
        "description": "Arrhythmia – Run of PVCs",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Ventricular Premature Beat": {
        "description": "Arrhythmia – Ventricular Premature Beat",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "PVC High": {
        "description": "Arrhythmia – PVC High",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Non Standard Ventricular Tachycardia": {
        "description": "Arrhythmia – Nonstandard Ventricular Tachycardia",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Extreme Tachycardia": {
        "description": "Arrhythmia – Extreme Tachycardia",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Extreme Bradycardia": {
        "description": "Arrhythmia – Extreme Bradycardia",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Pause": {
        "description": "Arrhythmia – Heart Pause",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Irregular Rhythm": {
        "description": "Arrhythmia – Irregular rhythm",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Ventricular Bradycardia": {
        "description": "Arrhythmia – Ventricular tachycardia",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Ventricular Rhythm": {
        "description": "Arrhythmia – Ventricular rhythm.",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Wrong cuff": {
        "description": "Wrong cuff for the patient (for example paediatric NIBP being measured using ADULT cuff)",
        "validity": "",
        "observationType": "NIBP",
    },
    "Connect Cuff": {
        "description": "No cuff / loose cuff",
        "validity": "",
        "observationType": "NIBP",
    },
    "Measurement error": {
        "description": "Measurement taken is erroneous",
        "validity": "",
        "observationType": "NIBP",
    },
    "No finger in probe": {
        "description": "SpO2 sensor has fallen off the patient finger",
        "validity": "The SpO2, PR value is invalid if this message is present. Value will be set to null.",
        "observationType": "SPO2",
    },
    "Probe unplugged": {
        "description": "The SPO2 sensor probe is disconnected from the patient monitor.",
        "validity": "The SpO2, PR value is invalid if this message is present. Value will be set to null.",
        "observationType": "SPO2",
    },
    "Leads off": {
        "description": "Respiration leads have fallen off / disconnected from the patient",
        "validity": "The value is null if invalid",
        "observationType": "Respiration",
    },
    "Measurement invalid": {
        "description": "The measured value is invalid",
        "validity": "When this message is present, the measured value is invalid.",
        "observationType": "Temperature",
        "invalid": True,
    },
}


def is_valid(observation: Observation):
    if (
        not observation
        or not observation.status
        or (
            observation.observation_id != ObservationID.BLOOD_PRESSURE
            and not isinstance(observation.value, (int, float))
        )
    ):
        logger.info(
            "Observations are not valid for %s Returning False",
            observation.observation_id,
        )
        return False

    if observation.status == Status.FINAL:
        return True

    message = observation.status.replace("Message-", "")
    message_obj = messages.get(message, None)
    if message_obj and message_obj.get("invalid"):
        return False

    return True


def get_vitals_from_observations(ip_address: str):
    logger.info("Getting vitals from observations for the asset: %s", ip_address)

    observation = get_static_observations(device_id=ip_address)

    if not observation:
        logger.info(
            "Returning as observations is stale or empty for device id : %s", ip_address
        )
        return None

    data = observation.observations

    temperature_data = get_value_from_data(
        "body-temperature1", data
    ) or get_value_from_data("body-temperature2", data)
    if temperature_data is None:
        temperature_data = {"temperature": None, "temperature_measured_at": None}

    return DailyRoundObservation(
        taken_at=observation.last_updated,
        spo2=get_value_from_data(ObservationID.SPO2, data),
        ventilator_spo2=get_value_from_data(ObservationID.SPO2, data),
        resp=get_value_from_data(ObservationID.RESPIRATORY_RATE, data),
        pulse=get_value_from_data(ObservationID.HEART_RATE, data)
        or get_value_from_data(ObservationID.PULSE_RATE, data),
        **temperature_data,
        bp=get_value_from_data(ObservationID.BLOOD_PRESSURE, data) or {},
        rounds_type="AUTOMATED",
        is_parsed_by_ocr=False,
    )


def get_value_from_data(
    type: ObservationID,
    data: Dict[
        ObservationID,
        Union[Observation, List[Observation]],
    ],
):
    if not data or type not in data:
        return None

    observation: Observation = (
        data[type][-1] if isinstance(data[type], list) else data[type]
    )

    if not observation.date_time:
        return None

    converted_date_time = make_aware(observation.date_time)

    is_stale = converted_date_time < (
        now() - timedelta(minutes=settings.UPDATE_INTERVAL)
    )

    if is_stale or not is_valid(observation):
        logger.info("Observations are stale or invalid Returning None")
        return None

    if type in [
        ObservationID.BODY_TEMPERATURE1,
        ObservationID.BODY_TEMPERATURE2,
    ]:
        if observation.low_limit < observation.value < observation.high_limit:
            return {
                "temperature": observation.value,
                "temperature_measured_at": converted_date_time.isoformat(),
            }
        return None
    elif type == "blood-pressure":
        if observation.systolic is None or observation.diastolic is None:
            return None
        return {
            "systolic": observation.systolic.value,
            "diastolic": observation.diastolic.value,
        }
    else:
        return observation.value


def extract_datetime(key):
    # Split the string to get the timestamp part
    timestamp_str = key.split("_", 1)[1]
    # Convert the string to a datetime object
    return datetime.fromisoformat(timestamp_str)


def get_observations_from_redis():
    observation_keys = cache.keys(f"{settings.REDIS_OBSERVATIONS_KEY}*")

    sorted_keys = sorted(observation_keys, key=extract_datetime)
    observations = []
    for key in sorted_keys:
        observations.extend(cache.get(key))
    return observations


def get_static_observations(device_id: DeviceID):
    observations = get_observations_from_redis()
    stale_time = now() - timedelta(minutes=settings.UPDATE_INTERVAL)

    # last one hour data matching the device id
    valid_observations: List[Observation] = []
    if not observations:
        logger.info(" No observations for device id : %s stored in redis ", device_id)
        return None
    for observation in observations:
        parsed_observation = Observation.model_validate(observation)

        if (
            parsed_observation.taken_at > stale_time
        ) and parsed_observation.device_id == device_id:
            valid_observations.append(parsed_observation)

    if not valid_observations:
        logger.info(
            " No observations Valid observations for device id : %s stored in redis ",
            device_id,
        )
        return None
    return generate_static_observations(observation_list=valid_observations)


def generate_static_observations(observation_list: List[Observation]):
    observations_dict = {}
    for observation in observation_list:
        observation_type = observation.observation_id
        if observation_type in observations_dict:
            observations_dict[observation_type].append(observation)
        else:
            observations_dict[observation_type] = [observation]

    return StaticObservation(
        observations=observations_dict, last_updated=observation_list[-1].taken_at
    )


def get_data_for_s3_dump():
    observations = get_observations_from_redis()
    stale_time = now() - timedelta(minutes=settings.UPDATE_INTERVAL)

    if not observations:
        return None
    observation_data_to_dump: List[Observation] = []

    # for makimg dumps we just use all the stale data
    for observation in observations:
        parsed_observation = Observation.model_validate(observation)
        if parsed_observation.taken_at < stale_time:
            observation_data_to_dump.append(parsed_observation)

    return observation_data_to_dump


def make_data_dump_to_s3(request: DataDumpRequest):
    check_in_id: Optional[str] = None

    if request.monitor_options:
        check_in_id = capture_checkin(
            monitor_slug=request.monitor_options.slug,
            status=MonitorStatus.IN_PROGRESS,
            monitor_config=request.monitor_options.options,
        )

    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            endpoint_url=settings.S3_ENDPOINT_URL if settings.S3_ENDPOINT_URL else None,
        )
        if not settings.S3_BUCKET_NAME:
            raise Exception("S3 Bucket Name not found")
        data = [
            observation.model_dump(mode="json", by_alias=True)
            for observation in request.data
        ]
        s3.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=request.key,
            Body=data,
            ContentType="application/json",
        )
        logger.info("Successfully uploaded data to S3")

        if request.monitor_options and check_in_id:
            capture_checkin(
                check_in_id=check_in_id,
                monitor_slug=request.monitor_options.slug,
                status=MonitorStatus.OK,
            )
    except (NoCredentialsError, PartialCredentialsError) as e:
        logger.error("Failed to upload data to S3 due to credential issues")
        if request.monitor_options and check_in_id:
            capture_checkin(
                check_in_id=check_in_id,
                monitor_slug=request.monitor_options.slug,
                status=MonitorStatus.ERROR,
            )
        logger.error(e)

    except Exception as e:
        logger.error("Failed to upload data to S3")
        if request.monitor_options and check_in_id:
            capture_checkin(
                check_in_id=check_in_id,
                monitor_slug=request.monitor_options.slug,
                status=MonitorStatus.ERROR,
            )
        logger.error(e)
